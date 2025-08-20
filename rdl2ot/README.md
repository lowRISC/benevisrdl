# rdl2ot cli tool
<!--
# SPDX-FileCopyrightText: lowRISC contributors.
# SPDX-License-Identifier: Apache-2.0
-->

A PeakRDL extension to generate OpenTitan register block SystemVerilog from SystemRDL files.

## Using as a standalone tool
### How to generate the OpenTitan register interfaces from a RDL file
```sh
rdl2ot export-rtl <input_rdl> <output_dir>
```

Example:
```sh
mkdir -p /tmp/lc_ctrl
rdl2ot export-rtl tests/snapshots/lc_ctrl.rdl /tmp/lc_ctrl/
```

## Using as a PeakRDL pluggin 
### Installing
```sh
pip install peakrdl rdl2ot
```
### Running
```sh
mkdir -p /tmp/lc_ctrl
peakrdl rdl2ot tests/snapshots/lc_ctrl.rdl -o /tmp/lc_ctrl/
```

## Contributing
### How to run tests
```sh
cd rdl2ot
pytest
```

