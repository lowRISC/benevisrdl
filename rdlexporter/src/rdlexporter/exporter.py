# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Exports rdl files."""

from dataclasses import dataclass, field
from pathlib import Path

from systemrdl import RDLCompiler
from systemrdl.ast.cast import AssignmentCast
from systemrdl.ast.literals import BoolLiteral, BuiltinEnumLiteral, IntLiteral, StringLiteral
from systemrdl.ast.references import InstRef
from systemrdl.component import AddressableComponent, Addrmap, Field, Mem, Reg
from systemrdl.rdltypes import AccessType, OnReadType, OnWriteType
from systemrdl.rdltypes.user_enum import UserEnumMeta


@dataclass
class RdlExporter:
    """Exports rdl files from AST."""

    rdlc: RDLCompiler
    stream: str = ""
    indent_pos = 0
    indent_width = 4
    indent_str = " "
    dynamic_assignment: dict[str, list[dict]] = field(default_factory=dict)
    ast_path: list[str] = field(default_factory=list)

    def _raise_type_error(self, type_name: str) -> None:
        print(f"Error: Unsupported type: {type_name} at this level only supports")
        raise RuntimeError

    def _indent(self) -> str:
        return f"{self.indent_str:>{self.indent_pos}}" if self.indent_pos else ""

    def _is_nested(self) -> bool:
        return self.indent_pos > 0

    def _get_field_limits(self, field: Field) -> (int, int):
        return (
            (field.msb, field.lsb)
            if isinstance(field.msb, int)
            else (field.msb.get_value(), field.lsb.get_value())
        )

    def _get_offset(self, comp: AddressableComponent) -> str:
        if isinstance(comp.addr_offset, AssignmentCast):
            return f" @ 0x{comp.addr_offset.get_value():X}"
        if isinstance(comp.addr_offset, int):
            return f" @ 0x{comp.addr_offset:X}"
        return ""

    def _get_register_array_dim(self, reg: Reg) -> int:
        return (
            reg.array_dimensions[0]
            if isinstance(reg.array_dimensions[0], int)
            else reg.array_dimensions[0].get_value()
        )

    def _emit_dynamic_assignment(self) -> None:
        # Nothing to be emited
        current_scope = self.ast_path[-1].lower()
        if current_scope not in self.dynamic_assignment:
            return
        for scope in self.dynamic_assignment.pop(current_scope):
            left_expr = (
                ".".join(scope["ast_path"]).removeprefix(".".join(self.ast_path)).lstrip(".")
            )
            left_expr = f"{left_expr} -> {scope['property']}"

            right_expr = "".join([f"{elem[0]}." for elem in scope["ref"].ref_elements]).rstrip(".")
            expr = f"{left_expr} = {right_expr};\n"
            self.stream += self._indent() + expr

    def _emit_property(self, properties: dict) -> None:
        for name, obj in properties.items():
            if isinstance(obj, UserEnumMeta):
                val = obj.type_name
            elif isinstance(obj, BuiltinEnumLiteral):
                val = obj.val.name
            elif isinstance(obj, AccessType | OnReadType | OnWriteType):
                val = obj.name
            elif isinstance(obj, StringLiteral):
                val = f'''"{obj.get_value()}"'''
            elif isinstance(obj, BoolLiteral):
                val = str(obj.get_value()).lower()
            elif isinstance(obj, IntLiteral):
                val = f"0x{obj.get_value():x}"
            elif isinstance(obj, str):
                val = f'''"{obj}"'''
            elif isinstance(obj, bool):
                val = str(obj).lower()
            elif isinstance(obj, int):
                val = f"0x{obj:x}"
            elif isinstance(obj, InstRef):
                # This should be emited at a higher scope indicated by `ref_root._scope_name`.
                ref = obj.get_value()
                scope = ref.ref_root._scope_name or ref.ref_root.type_name  # noqa: SLF001
                self.dynamic_assignment.setdefault(scope.lower(), []).append(
                    {
                        "property": name,
                        "ast_path": self.ast_path.copy(),
                        "ref": ref,
                    }
                )
                continue
            else:
                print(f"Warning: Type {type(obj)} not implemented, skipping it.")
                continue

            self.stream += self._indent() + f"{name} = {val};\n"

    def _arrays(self, component: Reg) -> str:
        if not component.is_array:
            return ""

        if len(component.array_dimensions) > 1:
            print("Error: Unsupported multidimentional arrays.")
            raise RuntimeError

        dim = self._get_register_array_dim(component)
        return f"[{dim}]"

    def _emit_parameters(self, parameters: list) -> None:
        if not len(parameters):
            return

        self.stream += "#(\n"
        self.indent_pos += self.indent_width
        for index, param in enumerate(parameters):
            val = param.get_value()
            if isinstance(val, int) or param.param_type.is_integer:
                type_ = "longint"
            else:
                self._raise_type_error(type(param.param_type))

            self.stream += self._indent() + f"{type_} {param.name} = {val}"
            last = index == (len(parameters) - 1)
            self.stream += ",\n" if not last else "\n"

        self.indent_pos -= self.indent_width
        self.stream += ")"

    def _emit_mem(self, mem: Mem) -> None:
        self.ast_path.append(mem.inst_name)
        external_str = "external " if mem.external else ""
        self.stream += self._indent() + external_str + "mem "
        self._emit_parameters(mem.parameters)
        self.stream += "{\n"
        self.indent_pos += self.indent_width
        self._emit_property(mem.properties)
        self.indent_pos -= self.indent_width
        self.stream += self._indent() + f"}} {mem.inst_name}" + self._arrays(mem)
        offset = self._get_offset(mem)
        self.stream += f"{offset};\n"
        self.ast_path.pop()

    def _emit_field(self, field: Field) -> None:
        self.ast_path.append(field.inst_name)
        self.stream += self._indent() + "field "
        self._emit_parameters(field.parameters)
        self.stream += "{\n"
        self.indent_pos += self.indent_width
        self._emit_property(field.properties)
        self.indent_pos -= self.indent_width
        msb, lsb = self._get_field_limits(field)
        self.stream += self._indent() + f"}} {field.inst_name}[{msb}:{lsb}];\n"
        self.ast_path.pop()

    def _emit_register(self, register: Reg) -> None:
        self.ast_path.append(register.inst_name)
        external_str = "external " if register.external else ""
        self.stream += self._indent() + external_str + "reg "
        self._emit_parameters(register.parameters)
        self.stream += "{\n"
        self.indent_pos += self.indent_width
        self._emit_property(register.properties)
        for child in register.children:
            if isinstance(child, Field):
                self._emit_field(child)
            else:
                self._raise_type_error(type(child))
        self.indent_pos -= self.indent_width
        self.stream += self._indent() + f"}} {register.inst_name}" + self._arrays(register)
        offset = self._get_offset(register)
        self.stream += f"{offset};\n"
        self.ast_path.pop()

    def _emit_addrmap(self, name: str, addrmap: Addrmap) -> None:
        self.ast_path.append(name)
        self.stream += self._indent() + "addrmap "
        self.stream += f"{name} " if not self._is_nested() else ""
        self._emit_parameters(addrmap.parameters)
        self.stream += "{\n"
        self.indent_pos += self.indent_width
        for child in addrmap.children:
            if isinstance(child, Reg):
                self._emit_register(child)
            elif isinstance(child, Addrmap):
                self._emit_addrmap(child.inst_name, child)
            elif isinstance(child, Mem):
                self._emit_mem(child)
            else:
                self._raise_type_error(type(child))
            self._emit_dynamic_assignment()
            self.stream += "\n"

        self.indent_pos -= self.indent_width
        self.stream += self._indent() + "}"
        self.stream += f" {name};\n" if self._is_nested() else ";\n"
        self.ast_path.pop()

    def export(self, outfile: Path) -> None:
        """Export the SystemRDL ast to an RDL file."""
        self.ast_path.append(str(self.rdlc.root.inst_name))
        for name, component in self.rdlc.root.comp_defs.items():
            if isinstance(component, Addrmap):
                self._emit_addrmap(name, component)
            else:
                self._raise_type_error(type(component))

        self.stream.lstrip("\n ")
        with outfile.open("a") as f:
            f.write(self.stream)
