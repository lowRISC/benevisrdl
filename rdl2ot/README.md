# rdl2ot cli tool
A PeakRDL extension to generate Opentitan style source files from SystemRDL files.

## How to generate the Opentitan register interfaces from a RDL file
```sh
rdl2ot export-rtl <input_rdl> <output_dir>
```

Example:
```sh
mkdir -p /tmp/lc_ctrl
rdl2ot export-rtl tests/snapshots/lc_ctrl.rdl /tmp/lc_ctrl/
```

## Contributing
### How to run tests
```sh
cd rdl2ot
pytest
```

