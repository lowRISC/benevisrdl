# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path
from systemrdl import RDLCompiler, RDLCompileError, RDLImporter
from systemrdl import rdltypes
from systemrdl.core.parameter import Parameter
from systemrdl.messages import FileSourceRef
from systemrdl.rdltypes import AccessType, OnReadType, OnWriteType
from rdlexporter import RdlExporter

SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


def run_ip_test_from_file(tmp_path: Path, ip_block: str):
    input_rdl = SNAPSHOTS_DIR / f"{ip_block}.rdl"
    snapshot_file = input_rdl
    snapshot_content = snapshot_file.read_text(encoding="utf-8")
    output_file = tmp_path / f"{ip_block}.rdl"

    rdlc = RDLCompiler()
    try:
        rdlc.compile_file(input_rdl)
    except RDLCompileError:
        sys.exit(1)

    # Include the user defined enums and properties.
    with output_file.open("w") as f:
        f.write('`include "user_defined.rdl"\n\n')

    RdlExporter(rdlc).export(output_file)

    actual_output_content = output_file.read_text(encoding="utf-8")

    assert actual_output_content == snapshot_content, (
        f"Output mismatch, to debug, run:\nmeld {output_file} {snapshot_file}\n"
    )


def test_cli_uart_from_file(tmp_path: Path):
    run_ip_test_from_file(tmp_path, "uart")


def test_cli_lc_ctrl_from_file(tmp_path: Path):
    run_ip_test_from_file(tmp_path, "lc_ctrl")


def test_importer(tmp_path: Path):
    input_rdl = SNAPSHOTS_DIR / "generic.rdl"
    snapshot_file = input_rdl
    snapshot_content = snapshot_file.read_text(encoding="utf-8")
    output_file = tmp_path / "generic.rdl"

    rdlc = RDLCompiler()

    imp = RDLImporter(rdlc)
    imp.default_src_ref = FileSourceRef(tmp_path)

    field_en = imp.create_field_definition("EN")
    field_en = imp.instantiate_field(field_en, "EN", 0, 1)
    imp.assign_property(field_en, "reset", 0x00)
    imp.assign_property(field_en, "swmod", True)
    imp.assign_property(field_en, "desc", "Enable the ip")

    field_mode = imp.create_field_definition("MODE")
    field_mode = imp.instantiate_field(field_mode, "MODE", 2, 8)
    imp.assign_property(field_mode, "reset", 0x7)
    imp.assign_property(field_mode, "swmod", False)
    imp.assign_property(field_mode, "desc", "Define the mode.")
    imp.assign_property(field_mode, "sw", AccessType.rw)
    imp.assign_property(field_mode, "onread", OnReadType.rclr)
    imp.assign_property(field_mode, "onwrite", OnWriteType.woset)
    imp.assign_property(field_mode, "hw", AccessType.rw)

    reg = imp.create_reg_definition("CTRL")
    imp.add_child(reg, field_en)
    imp.add_child(reg, field_mode)

    reg = imp.instantiate_reg(reg, "CTRL", 0x00, [4], 0x04)
    addrmap = imp.create_addrmap_definition("generic")

    value = 0x56
    param = Parameter(rdltypes.get_rdltype(value), "Width")
    param._value = value
    addrmap.parameters.append(param)

    imp.add_child(addrmap, reg)
    imp.register_root_component(addrmap)

    RdlExporter(rdlc).export(output_file)

    actual_output_content = output_file.read_text(encoding="utf-8")
    assert actual_output_content == snapshot_content, (
        f"Output mismatch, to debug, run:\nmeld {output_file} {snapshot_file}\n"
    )
