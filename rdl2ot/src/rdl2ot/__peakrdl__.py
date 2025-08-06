#!/usr/bin/env python3
# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Generates OpenTitan regblock RTL."""

from pathlib import Path
from typing import TYPE_CHECKING

from peakrdl.plugins.exporter import ExporterSubcommandPlugin  # pylint: disable=import-error

from rdl2ot import rtl_exporter

if TYPE_CHECKING:
    import argparse

    from systemrdl.node import AddrmapNode


class Exporter(ExporterSubcommandPlugin):
    """Generates OpenTitan regblock RTL."""

    short_desc = "Generates OpenTitan register block RTL."

    def add_exporter_arguments(self, arg_group: "argparse.ArgumentParser") -> None:
        """No extra arguments."""

    def do_export(self, top_node: "AddrmapNode", options: "argparse.Namespace") -> None:
        """Plugin entry function."""
        rtl_exporter.run(top_node, Path(options.output))
