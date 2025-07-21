# BenevisRdl
This repository will house PeakRdl plugins, named after Ben Nevis, the UK's tallest peak.

## rdl2ot
A PeakRDL extension to generate Opentitan style source files from SystemRDL files.


### How to generate the install dependencies
#### Using uv on macOS and Linux

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv
uv sync --all-extras 
. .venv/bin/activate
```
#### Using nix on Any OS
```sh 
nix develop
```

### How to run tests
```sh
cd rdl2ot
pytest
```

### How to generate the Opentitan register interfaces from a RDL file
```sh
cd rdl2ot
python src/rdl2ot export-rtl tests/snapshots/lc_ctrl.rdl /tmp/
```

## Rdl-exporter
A library to generate SystemRDL files from the Hierarchical Register Model.

### How to run tests
```sh
cd rdl-exporter
pytest
```
