# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path
from systemrdl import RDLCompiler, RDLCompileError
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
