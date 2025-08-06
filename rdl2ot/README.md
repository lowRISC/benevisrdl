# rdl2ot cli tool
A PeakRDL extension to generate Opentitan style source files from SystemRDL files.

## Using as a standalone tool
### How to generate the Opentitan register interfaces from a RDL file
```sh
rdl2ot export-rtl <input_rdl> <output_dir>
```

Example:
```sh
mkdir -p /tmp/lc_ctrl
rdl2ot export-rtl tests/snapshots/lc_ctrl.rdl /tmp/lc_ctrl/
```

## Using as a Peakrdl pluggin 
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

