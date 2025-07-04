#!/usr/bin/env python3

import click
import sys


@click.group()
def main():
    pass


@main.command()
@click.argument(
    "input_file",
    type=click.Path(writable=True),
    # help="The input RDL.",
)
@click.argument(
    "out_dir",
    default="./result",
    type=click.Path(writable=True),
    # help="The destination dir to generate the output.",
)
def export_rtl(input_file: str, out_dir: str):
    from systemrdl import RDLCompiler, RDLCompileError

    rdlc = RDLCompiler()
    try:
        rdlc.compile_file(input_file)
        root = rdlc.elaborate()
    except RDLCompileError:
        sys.exit(1)

    import export_rtl

    try:
        export_rtl.run(rdlc, root, out_dir)
    except RDLCompileError:
        sys.exit(1)

    print("Successfully finished!")
