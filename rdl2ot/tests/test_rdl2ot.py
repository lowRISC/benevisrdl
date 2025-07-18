# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import sys
import subprocess

CLI_TOOL_PATH = Path(__file__).parent.parent / "src/rdl2ot"
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


def run_cli_tool(input_file_path: Path, output_dir_path: Path):
    command = [
        sys.executable,  # Use the current Python interpreter
        str(CLI_TOOL_PATH),
        "export-rtl",
        str(input_file_path),
        str(output_dir_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result


def run_ip_test(tmp_path: Path, ip_block: str):
    for outfile in ["reg_pkg.sv", "reg_top.sv"]:
        input_rdl = SNAPSHOTS_DIR / f"{ip_block}.rdl"
        snapshot_file = SNAPSHOTS_DIR / f"{ip_block}_{outfile}"
        snapshot_content = snapshot_file.read_text(encoding="utf-8")
        output_file = tmp_path / f"{ip_block}_{outfile}"
        cli_result = run_cli_tool(input_rdl, tmp_path)
        assert cli_result.returncode == 0, f"CLI exited with error: {cli_result.stderr}"
        assert "Successfully finished!" in cli_result.stdout  # Check for success message

        actual_output_content = output_file.read_text(encoding="utf-8")

        assert actual_output_content == snapshot_content, (
            f"Output mismatch, to debug, run:\nmeld {output_file} {snapshot_file}\n"
        )


def test_cli_lc_ctrl(tmp_path: Path):
    run_ip_test(tmp_path, "lc_ctrl")


def test_cli_uart(tmp_path: Path):
    run_ip_test(tmp_path, "uart")
