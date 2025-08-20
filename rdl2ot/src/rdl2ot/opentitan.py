# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Functions with opentitan specific logic."""

import re

from systemrdl import node
from systemrdl.rdltypes import AccessType, OnReadType, OnWriteType


def register_permit_mask(reg: dict) -> int:
    """One bit presents one byte in the register, so in total 4 bits are used."""
    w = reg["msb"] + 1
    if w > 24:  # noqa: PLR2004
        return 0b1111
    if w > 16:  # noqa: PLR2004
        return 0b0111
    if w > 8:  # noqa: PLR2004
        return 0b0011
    return 0b0001


def needs_read_en(reg: dict) -> bool:
    """Return true if at least one field needs a read-enable.

    This is true if any of the following are true:

      - The register is shadowed, because the read has a side effect.
        I.e., this puts the register back into Phase 0 (next write will
        go to the staged register). This is useful for software in case
        it lost track of the current phase. See comportability spec for
        more details:
        https://docs.opentitan.org/doc/rm/register_tool/#shadow-registers

      - There's an RC field (where we'll attach the read-enable signal to
        the subreg's we port)

      - The register is hwext and allows reads (in which case the hardware
        side might need the re signal)
    """
    return reg["shadowed"] or any(
        (field["clear_onread"] or (reg["external"] and field["sw_readable"]))
        for field in reg["fields"]
    )


def needs_write_en(reg: dict) -> bool:
    """Return register for this field should have a write-enable signal.

    This is almost the same as allows_write(), but doesn't return true for
    RC registers, which should use a read-enable signal (connected to their
    prim_subreg's we port).
    """
    return any((not field["clear_onread"] and field["sw_writable"]) for field in reg["fields"])


def needs_qe(reg: dict) -> bool:
    """Return true if the register or at least one field needs a q-enable."""
    return any(field["swmod"] for field in reg["fields"])


def needs_int_qe(reg: dict) -> bool:
    """Return true if the register or at least one field needs an internal q-enable.

    An internal q-enable means the net may be consumed by other reg logic but will
    not be exposed in the package file.
    """
    return (bool(reg["async_clk"]) and reg["hw_writable"]) or needs_qe(reg)


def get_bit_width(offset: int) -> int:
    """Calculate the number of bits to address every byte of the block."""
    return (offset - 1).bit_length()


def get_sw_access_enum(field: node.FieldNode) -> str:
    """Map the rdl access permissions to reggen SwAccess enum."""
    sw = field.get_property("sw")
    onwrite = field.get_property("onwrite")
    onread = field.get_property("onread")
    if onwrite == OnWriteType.woclr:
        return "W1C"
    if onwrite == OnWriteType.woset:
        return "W1S"
    if onwrite == OnWriteType.wzc:
        return "W0C"
    if onread == OnReadType.rclr:
        return "RC"
    if sw == AccessType.r:
        return "RO"
    if sw == AccessType.w:
        return "WO"
    if sw == AccessType.rw:
        return "RW"

    return "NONE"


def fields_no_write_en(reg: dict) -> int:
    """Count how many fields has write enable."""
    res = 0
    for idx, field in enumerate(reg["fields"]):
        res |= (not needs_we(field)) << idx
    return res


def needs_we(field: dict) -> bool:
    """True if the register for this field should have a write-enable signal.

    This is almost the same as allows_write(), but doesn't return true for
    RC registers, which should use a read-enable signal (connected to their
    prim_subreg's we port).
    """
    return field["opentitan"]["reggen_sw_access"] != "RC" and field["sw_writable"]


def is_homogeneous(reg: dict) -> bool:
    """Return true if all fields of a register are equal.

    The offset are excluded from the comparison.
    """
    exclude = ["name", "msb", "lsb", "bitmask", "type"]
    unamed_fields = [
        {key: value for key, value in f.items() if key not in exclude} for f in reg["fields"]
    ]
    names = {re.sub(r"_\d+$", "", f["name"]) for f in reg["fields"]}
    return all(f == unamed_fields[0] for f in unamed_fields[1:]) and len(names) == 1
