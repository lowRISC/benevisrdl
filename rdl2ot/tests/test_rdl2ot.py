# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Tests."""

import subprocess
import sys
from pathlib import Path

import pytest

CLI_TOOL_PATH = Path(__file__).parent.parent / "src/rdl2ot"
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


def _run_cli_tool(input_file_path: Path, output_dir_path: Path) -> subprocess.CompletedProcess:
    command = [
        sys.executable,  # Use the current Python interpreter
        str(CLI_TOOL_PATH),
        "export-rtl",
        str(input_file_path),
        str(output_dir_path),
    ]
    if "soc" in input_file_path.name:
        command.append("--soc")

    return subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603


test_ips = ["lc_ctrl", "uart", "soc_strawberry"]


@pytest.mark.parametrize("ip_block", test_ips)
def test_export_ip(tmp_path: Path, ip_block: str) -> None:
    """Test an given ip block."""
    input_rdl = SNAPSHOTS_DIR / f"{ip_block}.rdl"
    cli_result = _run_cli_tool(input_rdl, tmp_path)
    assert cli_result.returncode == 0, f"CLI exited with error: {cli_result.stderr}"
    assert "Successfully finished!" in cli_result.stdout  # Check for success message

    files = list(tmp_path.glob(f"*{ip_block}*.sv"))
    for outfile in files:
        snapshot_file = SNAPSHOTS_DIR / outfile.name
        snapshot_content = snapshot_file.read_text(encoding="utf-8")
        actual_output_content = outfile.read_text(encoding="utf-8")
        assert actual_output_content == snapshot_content, (
            f"Output mismatch, to debug, run:\nmeld {outfile} {snapshot_file}\n"
        )
