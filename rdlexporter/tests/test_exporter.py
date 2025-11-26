# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Unittests."""

from pathlib import Path

import systemrdl
from systemrdl import RDLCompiler, RDLImporter, rdltypes
from systemrdl.ast.references import InstRef
from systemrdl.core.parameter import Parameter
from systemrdl.messages import FileSourceRef
from systemrdl.rdltypes import AccessType, OnReadType, OnWriteType

from rdlexporter import RdlExporter

SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


def _run_ip_test_from_file(tmp_path: Path, ip_block: str) -> None:
    input_rdl = SNAPSHOTS_DIR / f"{ip_block}.rdl"
    snapshot_file = input_rdl
    snapshot_content = snapshot_file.read_text(encoding="utf-8")
    output_file = tmp_path / f"{ip_block}.rdl"

    rdlc = RDLCompiler()
    rdlc.compile_file(input_rdl)
    rdlc.elaborate()

    # Include the user defined enums and properties.
    with output_file.open("w") as f:
        f.write('`include "user_defined.rdl"\n\n')

    RdlExporter(rdlc).export(output_file)

    actual_output_content = output_file.read_text(encoding="utf-8")

    assert actual_output_content == snapshot_content, (
        f"Output mismatch, to debug, run:\nmeld {output_file} {snapshot_file}\n"
    )


def test_cli_uart_from_file(tmp_path: Path) -> None:
    """Test the uart."""
    _run_ip_test_from_file(tmp_path, "uart")


def test_cli_lc_ctrl_from_file(tmp_path: Path) -> None:
    """Test the lc_ctrl."""
    _run_ip_test_from_file(tmp_path, "lc_ctrl")


def test_importer(tmp_path: Path) -> None:
    """Test with the SystemRDL importer."""
    input_rdl = SNAPSHOTS_DIR / "generic.rdl"
    snapshot_file = input_rdl
    snapshot_content = snapshot_file.read_text(encoding="utf-8")
    output_file = tmp_path / "generic.rdl"

    rdlc = RDLCompiler()
    rdlc.compile_file(SNAPSHOTS_DIR / "user_defined.rdl")
    imp = RDLImporter(rdlc)
    imp.default_src_ref = FileSourceRef(tmp_path)

    root_addrmap = imp.create_addrmap_definition("root")
    addrmap = imp.create_addrmap_definition("generic")
    addrmap = imp.instantiate_addrmap(addrmap, "GENERIC", 0x00)

    field_wen = imp.create_field_definition("EN")
    field_wen = imp.instantiate_field(field_wen, "EN", 0, 1)
    imp.assign_property(field_wen, "desc", "Enable the ip")
    imp.assign_property(field_wen, "sw", AccessType.rw)

    regwen = imp.create_reg_definition("CTRL_WEN")
    imp.add_child(regwen, field_wen)
    regwen = imp.instantiate_reg(regwen, "CTRL_WEN", 0x00)
    imp.add_child(addrmap, regwen)

    field_en = imp.create_field_definition("EN")
    field_en = imp.instantiate_field(field_en, "EN", 0, 1)
    imp.assign_property(field_en, "reset", 0x00)
    imp.assign_property(field_en, "swmod", value=True)
    imp.assign_property(field_en, "desc", "Enable the ip")

    signal_t = imp._create_definition(systemrdl.component.Signal, "interrupt", None)  # noqa: SLF001
    signal = imp._instantiate(signal_t, "FIFO_EMPTY", None)  # noqa: SLF001
    imp.assign_property(signal, "desc", "Fire when fifo is empty.")
    imp.assign_property(signal, "signalwidth", 1)
    enum = imp.compiler.namespace.lookup_type("SigType")
    imp.assign_property(signal, "sigtype", enum["Interrupt"])
    addrmap.children.append(signal)

    field_mode = imp.create_field_definition("MODE")
    field_mode = imp.instantiate_field(field_mode, "MODE", 2, 8)
    imp.assign_property(field_mode, "reset", 0x7)
    imp.assign_property(field_mode, "swmod", value=False)
    imp.assign_property(field_mode, "desc", "Define the mode.")
    imp.assign_property(field_mode, "sw", AccessType.rw)
    imp.assign_property(field_mode, "onread", OnReadType.rclr)
    imp.assign_property(field_mode, "onwrite", OnWriteType.woset)
    imp.assign_property(field_mode, "hw", AccessType.rw)
    imp.assign_property(
        field_mode,
        "swwe",
        InstRef(
            imp.compiler.env,
            addrmap,
            [(regwen.inst_name, [], None), (field_wen.inst_name, [], None)],
        ),
    )

    reg = imp.create_reg_definition("CTRL")
    imp.add_child(reg, field_en)
    imp.add_child(reg, field_mode)

    reg = imp.instantiate_reg(reg, "CTRL", 0x04, [4], 0x04)
    imp.add_child(addrmap, reg)

    imp.assign_property(addrmap, "is_interface", True) # noqa: FBT003
    type_ = imp.compiler.namespace.lookup_type("udp_struct")
    inst = type_({"name": "racl", "enable": True})
    imp.assign_property(addrmap, "udp_config", inst)

    imp.add_child(root_addrmap, addrmap)
    value = 0x56
    param = Parameter(rdltypes.get_rdltype(value), "Width")
    param._value = value  # noqa: SLF001
    root_addrmap.parameters_dict["Width"] = param

    inst = type_({"name": "interface", "enable": True})
    imp.assign_property(root_addrmap, "udp_config", inst)

    imp.register_root_component(root_addrmap)

    RdlExporter(rdlc).export(output_file)

    # Check that the generated file is valid rdl by compiling it.
    rdlc = RDLCompiler()
    rdlc.compile_file(SNAPSHOTS_DIR / "user_defined.rdl")
    rdlc.compile_file(output_file)

    actual_output_content = output_file.read_text(encoding="utf-8")
    assert actual_output_content == snapshot_content, (
        f"Output mismatch, to debug, run:\nmeld {output_file} {snapshot_file}\n"
    )
