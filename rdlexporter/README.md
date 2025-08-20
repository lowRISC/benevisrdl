# rdlexporter
<!--
# SPDX-FileCopyrightText: lowRISC contributors.
# SPDX-License-Identifier: Apache-2.0
-->

A library to generate SystemRDL files from the Hierarchical Register Model.

How to use it: 
```sh
uv pip install rdlexporter
```
Example:
```python
from rdlexporter import RdlExporter
from systemrdl import RDLCompiler, RDLImporter
from systemrdl.rdltypes import AccessType

rdlc = RDLCompiler()

imp = RDLImporter(rdlc)
imp.default_src_ref = None

addrmap = imp.create_addrmap_definition("generic")

field_en = imp.create_field_definition("EN")
field_en = imp.instantiate_field(field_en, "EN", 0, 1)
imp.assign_property(field_en, "reset", 0x00)
imp.assign_property(field_en, "swmod", value=True)
imp.assign_property(field_en, "desc", "Enable the ip")

imp.assign_property(field_mode, "reset", 0x7)
imp.assign_property(field_mode, "desc", "Define the mode.")
imp.assign_property(field_mode, "sw", AccessType.rw)

reg = imp.create_reg_definition("CTRL")
imp.add_child(reg, field_en)
imp.add_child(reg, field_mode)

reg = imp.instantiate_reg(reg, "CTRL", 0x04, [4], 0x04)
imp.add_child(addrmap, reg)

imp.register_root_component(addrmap)
RdlExporter(rdlc).export("./generic.rdl")
```

## Contributing
### How to run tests
```sh
cd rdlexporter
uv run pytest
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
