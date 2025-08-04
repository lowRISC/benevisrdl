# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

import opentitan
from jinja2 import Environment, FileSystemLoader
from systemrdl import RDLCompiler, node
from systemrdl.rdltypes import OnReadType

TEMPLATES_DIR = "./src/templates"
DEFAULT_INTERFACE_NAME = "regs"


def run(rdlc: RDLCompiler, obj: node.RootNode, out_dir: Path):
    factory = OtInterfaceBuilder(rdlc)
    data = factory.parse_root(obj.top)
    with open("/tmp/reg.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    file_loader = FileSystemLoader(TEMPLATES_DIR)
    env = Environment(loader=file_loader)

    ip_name = data["ip_name"]
    reg_pkg_tpl = env.get_template("reg_pkg.sv.tpl")
    # stream = reg_pkg_tpl.stream(data)
    stream = reg_pkg_tpl.render(data)
    path = out_dir / f"{ip_name}_reg_pkg.sv"
    path.open("w").write(stream)
    print(f"Generated {path}.")

    reg_top_tpl = env.get_template("reg_top.sv.tpl")
    for interface in data["interfaces"]:
        name = "_{}".format(interface["name"].lower()) if "name" in interface else ""
        data_ = {"ip_name": ip_name, "interface": interface}
        # stream = reg_top_tpl.stream(data_)
        stream = reg_top_tpl.render(data_).replace(" \n", "\n")
        path = out_dir / f"{ip_name}{name}_reg_top.sv"
        path.open("w").write(stream)
        print(f"Generated {path}.")


class OtInterfaceBuilder:
    num_regs: int = 0  # The number of registers of an interface
    num_windows: int = 0  # The number of registers of an interface
    any_async_clk: bool = False  # Whether is there any register with async clock in the interface
    all_async_clk: bool = True  # Whether all registers have async clock in the interface
    async_registers: list = [(int, str)]  # List of all the (index, register) with async clock
    any_shadowed_reg: bool = False
    reg_index: int = 0
    rdlc: RDLCompiler

    def __init__(self, rdlc: RDLCompiler):
        self.rdlc = rdlc

    def get_field(self, field: node.FieldNode) -> dict:
        """Parse a field and return a dictionary.
        """
        obj = dict()
        obj["name"] = field.inst_name
        obj["type"] = "field"
        obj["desc"] = field.get_property("desc", default="")
        obj["parent_name"] = field.parent.inst_name
        obj["lsb"] = field.lsb
        obj["msb"] = field.msb
        obj["width"] = field.msb - field.lsb + 1
        obj["bitmask"] = (1 << (field.msb + 1)) - (1 << field.lsb)
        if isinstance(field.get_property("reset"), int):
            obj["reset"] = field.get_property("reset")
        obj["hw_readable"] = field.is_hw_readable
        obj["hw_writable"] = field.is_hw_writable
        obj["sw_readable"] = field.is_sw_readable
        obj["sw_writable"] = field.is_sw_writable
        swwe = field.get_property("swwe")
        obj["sw_write_en"] = bool(swwe)
        obj["write_en_signal"] = (
            self.get_field(swwe) if obj["sw_write_en"] and not isinstance(swwe, bool) else None
        )
        obj["hw_write_en"] = bool(field.get_property("we"))
        obj["swmod"] = field.get_property("swmod")
        obj["clear_onread"] = field.get_property("onread") == OnReadType.rclr
        obj["set_onread"] = field.get_property("onread") == OnReadType.rset
        encode = field.get_property("encode", default=None)
        if encode:
            obj["encode"] = encode.type_name
        obj["async"] = field.get_property("async", default=None)
        obj["sync"] = field.get_property("sync", default=None)
        obj["reggen_sw_access"] = opentitan.get_sw_access_enum(field)
        return obj

    def get_mem(self, mem: node.FieldNode) -> dict:
        """Parse a memory and return a dictionary representing a window.
        """
        obj = dict()
        obj["name"] = mem.inst_name
        obj["entries"] = mem.get_property("mementries")
        obj["sw_writable"] = mem.is_sw_writable
        obj["sw_readable"] = mem.is_sw_readable
        obj["width"] = mem.get_property("memwidth")
        obj["offset"] = mem.address_offset
        obj["size"] = obj["width"] * obj["entries"] // 8
        obj["integrity_bypass"] = mem.get_property("integrity_bypass", default=False)
        self.all_async_clk &= bool(mem.get_property("async_clk", default=False))
        self.num_windows += 1
        return obj

    def get_reg(self, reg: node.RegNode) -> dict:
        """Parse a register and return a dictionary.
        """
        obj = dict()
        obj["name"] = reg.inst_name
        obj["type"] = "reg"
        obj["width"] = reg.get_property("regwidth")
        obj["hw_readable"] = reg.has_hw_readable
        obj["hw_writable"] = reg.has_hw_writable
        obj["sw_readable"] = reg.has_sw_readable
        obj["sw_writable"] = reg.has_sw_writable
        obj["swmod"] = reg.get_property("swmod", default=None)
        obj["async_clk"] = reg.get_property("async_clk", default=None)
        obj["external"] = reg.external
        obj["shadowed"] = reg.get_property("shadowed", default=False)
        obj["hwre"] = reg.get_property("hwre", default=False)

        obj["offsets"] = []
        if reg.is_array:
            obj["is_multireg"] = True
            self.num_regs += reg.array_dimensions[0]
            offset = reg.raw_address_offset
            for _idx in range(reg.array_dimensions[0]):
                obj["offsets"].append(offset)
                offset += reg.array_stride
        else:
            self.num_regs += 1
            obj["offsets"].append(reg.address_offset)

        obj["fields"] = []
        sw_write_en = False
        msb = 0
        reset_val = 0
        bitmask = 0
        for field in reg.fields():
            field = self.get_field(field)
            obj["fields"].append(field)
            sw_write_en |= field["sw_write_en"]
            msb = max(msb, field["msb"])
            bitmask |= field["bitmask"]
            reset_val |= field.get("reset", 0) << field["lsb"]

        obj["msb"] = msb
        obj["permit"] = opentitan.register_permit_mask(obj)
        obj["sw_write_en"] = sw_write_en
        obj["bitmask"] = bitmask
        obj["reset"] = reset_val
        obj["async"] = False
        obj["needs_write_en"] = opentitan.needs_write_en(obj)
        obj["needs_read_en"] = opentitan.needs_read_en(obj)
        obj["needs_qe"] = opentitan.needs_qe(obj)
        obj["needs_int_qe"] = opentitan.needs_int_qe(obj)
        obj["fields_no_write_en"] = opentitan.fields_no_write_en(obj)
        obj["is_multifields"] = len(obj["fields"]) > 1
        obj["is_homogeneous"] = opentitan.is_homogeneous(obj)

        self.any_async_clk |= bool(obj["async_clk"])
        self.all_async_clk &= bool(obj["async_clk"])
        self.any_shadowed_reg |= bool(obj["shadowed"])

        array_size = len(obj["offsets"])
        if bool(obj["async_clk"]):
            for index in range(array_size):
                reg_name = reg.inst_name + (f"_{index}" if array_size > 1 else "")
                self.async_registers.append((self.reg_index + index, reg_name))
        self.reg_index += array_size
        return obj

    def get_paramesters(self, obj: node.AddrmapNode | node.RegfileNode) -> [dict]:
        """Parse the custom property localparams and return a list of  dictionaries.
        """
        res = [
            {"name": param.name, "type": "int", "value": param.get_value()}
            for param in obj.inst.parameters
        ]
        return res

    def get_interface(self, addrmap: node.AddrmapNode, defalt_name: None | str = None) -> dict:
        """Parse an interface and return a dictionary.
        """
        self.num_regs = 0
        self.num_windows = 0
        self.any_async_clk = False
        self.all_async_clk = True
        self.any_shadowed_reg = False
        self.async_registers.clear()

        if addrmap.is_array:
            print(f"WARNING: Unsupported array type: {type(addrmap)}, skiping...")

        interface = dict()
        if defalt_name:
            interface["name"] = addrmap.inst_name or defalt_name

        interface["offset"] = addrmap.address_offset
        interface["regs"] = []
        interface["windows"] = []
        for child in addrmap.children():
            if isinstance(child, node.RegNode):
                child_obj = self.get_reg(child)
                interface["regs"].append(child_obj)
            elif isinstance(child, node.MemNode):
                child_obj = self.get_mem(child)
                interface["windows"].append(child_obj)
            else:
                print(f"WARNING: Unsupported type: {type(child)}, skiping...")
                continue

        last_addr = interface["regs"][-1]["offsets"][-1] + 4 if len(interface["regs"]) > 0 else 0
        if len(interface["windows"]) > 0:
            last_addr = max(
                last_addr, interface["windows"][-1]["offset"] + interface["windows"][-1]["size"]
            )
        interface["addr_width"] = (last_addr - 1).bit_length()
        interface["num_regs"] = self.num_regs
        interface["num_windows"] = self.num_windows
        interface["async_registers"] = self.async_registers
        interface["needs_aw"] = (
            interface["num_regs"] > 0
            or interface["num_windows"] > 1
            or interface["windows"][0]["offset"] > 0
            or interface["windows"][0]["size"] != (1 << interface["addr_width"])
        )
        interface["any_async_clk"] = self.any_async_clk
        interface["all_async_clk"] = self.all_async_clk
        interface["any_shadowed_reg"] = self.any_shadowed_reg
        interface["any_integrity_bypass"] = any(
            [win["integrity_bypass"] for win in interface["windows"]]
        )
        return interface

    def parse_root(self, root: node.AddrmapNode) -> dict:
        """Parse the root node and return a dictionary representing a window.
        """
        if root.is_array:
            print("Error: Unsupported array type on the top")
            raise RuntimeError
        if not isinstance(root, node.AddrmapNode):
            print("Error: Top level must be an addrmap")
            raise RuntimeError

        obj = dict()
        params = self.get_paramesters(root)
        if params:
            obj["parameters"] = params
        obj["ip_name"] = root.inst_name
        obj["offset"] = root.address_offset

        obj["interfaces"] = []
        for child in root.children():
            if isinstance(child, node.AddrmapNode):
                child_obj = self.get_interface(child, DEFAULT_INTERFACE_NAME)
                obj["interfaces"].append(child_obj)
            elif isinstance(child, node.RegNode | node.MemNode):
                continue
            else:
                print(
                    f"""Error: Unsupported type: {type(child)}, top level only supports 
                      addrmap and reg components."""
                )
                raise RuntimeError

        # If the root contain imediate registers, use a default interface name
        if len(root.registers()) > 0:
            interface = self.get_interface(root)
            obj["interfaces"].append(interface)

        return obj
