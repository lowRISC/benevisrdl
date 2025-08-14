#!/usr/bin/env python3
# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0


"""Cli."""

from pathlib import Path

import click
from systemrdl import RDLCompiler

from rdl2ot import rtl_exporter


@click.group()
def main() -> None:
    """Cli."""


@main.command()
@click.argument(
    "input_file",
    type=click.Path(writable=True),
)
@click.argument(
    "out_dir",
    default="./result",
    type=click.Path(writable=True),
)
@click.option(
    "--soc",
    is_flag=True,
)
def export_rtl(input_file: str, out_dir: str, soc: bool = False) -> None:
    """Export opentitan rtl.

    INPUT_FILE: The input RDL
    OUT_DIR: The destination dir to generate the output
    SOC: Indicates that the input RDL is a SoC top

    """
    print(f"Compiling file: {input_file}...")
    rdlc = RDLCompiler()
    rdlc.compile_file(input_file)
    root = rdlc.elaborate()

    rtl_exporter.run(root.top, Path(out_dir), soc)

    print("Successfully finished!\n")
