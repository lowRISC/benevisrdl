# BenevisRdl
This repository will house PeakRdl plugins, named after Ben Nevis, the UK's tallest peak.

## Installing dependencies
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

## rdl2ot cli tool
A PeakRDL extension to generate Opentitan style source files from SystemRDL files.

For more details, refer to [rdl2ot](./rdl2ot)

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

For more details, refer to [rdlexporter](./rdlexporter)

### How to run tests
```sh
cd rdl-exporter
pytest
```

### How to build the package and install it locally
Install dev dependencies
```sh
uv sync --all-extras 
```
Build package
```sh
uv build --all
```
Install the package locally
```sh
uv pip install dist/rdlexporter-0.1.0-py3-none-any.whl
```
Testing
```sh
uv run python
```
```python
from rdlexporter import RdlExporter
```

