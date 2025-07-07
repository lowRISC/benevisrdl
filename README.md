# rdl2ot
A PeakRDL extension to generate Opentitan style source files from SystemRDL files.


## How to generate the install dependencies
### Using uv on macOS and Linux

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv
uv sync --all-extras 
. .venv/bin/activate
```
### Using nix on Any OS
```sh 
nix develop
```

## How to run tests
```sh
pytest
```

## How to generate the Opentitan register interfaces from a RDL file
```sh
python src/rdl2ot export-rtl tests/snapshots/lc_ctrl.rdl /tmp/
```
