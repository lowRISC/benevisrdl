# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Export RDL to opentitan RTL."""

import json
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from systemrdl import node
from systemrdl.rdltypes import BuiltinEnum, OnReadType, UserEnum
from systemrdl.rdltypes.user_struct import UserStruct

from rdl2ot import opentitan

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
DEFAULT_INTERFACE_NAME = "regs"


def _camelcase(value: str) -> str:
    words = value.split("_")
    return "".join(word.capitalize() for word in words)


def _reindex(s: str, new_index: int) -> str:
    return re.sub(r"\d+", str(new_index), s)


def run(root_node: node.AddrmapNode, out_dir: Path, is_soc: bool = False) -> None:
    """Export RDL to opentitan RTL.

    IS_SOC: True if the root node is a SoC with peripherals/devices.
    """
    factory = OtInterfaceBuilder()
    data = factory.parse_soc(root_node) if is_soc else factory.parse_ip_block(root_node)

    json_file = Path(out_dir / "rdl.json")
    json_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Generated {json_file}.")

    if not is_soc:
        _export(data, out_dir)
        return

    for ip_block in data["devices"]:
        if ip_block["type"] == "device":
            _export(ip_block, out_dir)


def _export(ip_block: dict, out_dir: Path) -> None:
    file_loader = FileSystemLoader(TEMPLATES_DIR)
    env = Environment(loader=file_loader)
    env.filters["camelcase"] = _camelcase
    env.filters["reindex"] = _reindex

    ip_name = ip_block["name"].lower()
    reg_pkg_tpl = env.get_template("reg_pkg.sv.tpl")
    stream = reg_pkg_tpl.render(ip_block)
    path = out_dir / f"{ip_name}_reg_pkg.sv"
    path.open("w").write(stream)
    print(f"Generated {path}.")

    reg_top_tpl = env.get_template("reg_top.sv.tpl")
    for interface in ip_block["interfaces"]:
        name = "_{}".format(interface["name"].lower()) if "name" in interface else ""
        data_ = {"name": ip_name, "interface": interface, "udps": ip_block.get("udps", {})}
        data_["udps"].update(interface.get("udps", {}))
        stream = reg_top_tpl.render(data_).replace(" \n", "\n")
        path = out_dir / f"{ip_name}{name}_reg_top.sv"
        path.open("w").write(stream)
        print(f"Generated {path}.")


class OtInterfaceBuilder:
    """OpenTitan Interface Builder."""

    num_regs: int = 0  # The number of registers of an interface
    num_windows: int = 0  # The number of registers of an interface
    any_async_clk: bool = False  # Whether is there any register with async clock in the interface
    all_async_clk: bool = True  # Whether all registers have async clock in the interface
    async_registers: list = [(int, str)]  # List of all the (index, register) with async clock
    any_shadowed_reg: bool = False
    any_hw_writable_reg: bool = False
    any_sw_writable_reg: bool = False
    reg_index: int = 0

    def get_signal(self, sig: node.SignalNode) -> dict:
        """Parse a signal and return a dict."""
        obj = {}
        obj["name"] = sig.inst_name
        obj["width"] = sig.get_property("signalwidth")
        obj.update(self.get_udps(sig))
        return obj

    def parse_array(self, node_: node.AddressableNode) -> list:
        """Parse an array node and return a list of offsets."""
        offsets = []
        if node_.is_array:
            offset = node_.raw_address_offset
            for _idx in range(node_.array_dimensions[0]):
                offsets.append(offset)
                offset += node_.array_stride
        else:
            offsets.append(node_.address_offset)
        return offsets

    def get_field(self, field: node.FieldNode) -> dict:
        """Parse a field and return a dictionary."""
        obj = {"name": field.inst_name, "type": "field", "type_name": field.type_name}
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
        obj["opentitan"] = {"reggen_sw_access": opentitan.get_sw_access_enum(field)}
        return obj

    def get_mem(self, mem: node.FieldNode) -> dict:
        """Parse a memory and return a dictionary representing a window."""
        obj = {}
        obj["name"] = mem.inst_name
        obj["type"] = "mem"
        obj["entries"] = mem.get_property("mementries")
        obj["sw_writable"] = mem.is_sw_writable
        obj["sw_readable"] = mem.is_sw_readable
        obj["width"] = mem.get_property("memwidth")
        obj["offset"] = mem.address_offset
        obj["size"] = obj["width"] * obj["entries"] // 8
        obj["integrity_bypass"] = mem.get_property("integrity_bypass", default=False)
        if udps := self.get_udps(mem):
            obj["udps"] = udps

        if properties := self.get_native_properties(mem):
            obj.update(properties)

        self.all_async_clk &= bool(mem.get_property("async_clk", default=False))
        self.num_windows += 1
        return obj

    def get_reg(self, reg: node.RegNode) -> dict:
        """Parse a register and return a dictionary."""
        obj = {"name": reg.inst_name, "type": "reg", "type_name": reg.type_name}
        obj["desc"] = reg.get_property("desc", default="")
        obj["width"] = reg.get_property("regwidth")
        obj["hw_readable"] = reg.has_hw_readable
        obj["hw_writable"] = reg.has_hw_writable
        obj["sw_readable"] = reg.has_sw_readable
        obj["sw_writable"] = reg.has_sw_writable
        obj["swmod"] = reg.get_property("swmod", default=None)
        if async_clk := reg.get_property("async_clk", default=None):
            obj["async_clk"] = async_clk.inst_name
        if async_rst := reg.get_property("async_rst", default=None):
            obj["async_rst"] = async_rst.inst_name
        obj["external"] = reg.external
        obj["shadowed"] = reg.get_property("shadowed", default=False)
        obj["hwre"] = reg.get_property("hwre", default=False)
        obj["compacted"] = reg.get_property("compacted", default=False)

        obj["offsets"] = self.parse_array(reg)
        array_size = len(obj["offsets"])
        self.num_regs += array_size
        obj["is_multireg"] = reg.is_array

        sw_write_en = False
        msb = 0
        reset_val = 0
        bitmask = 0
        obj["fields"] = []
        for f in reg.fields():
            field = self.get_field(f)
            obj["fields"].append(field)
            sw_write_en |= field["sw_write_en"]
            msb = max(msb, field["msb"])
            bitmask |= field["bitmask"]
            reset_val |= field.get("reset", 0) << field["lsb"]

        obj["msb"] = msb
        obj["sw_write_en"] = sw_write_en
        obj["bitmask"] = bitmask
        obj["reset"] = reset_val
        obj["async"] = False
        obj["is_multifields"] = len(obj["fields"]) > 1
        obj["opentitan"] = {
            "permit": opentitan.register_permit_mask(obj),
            "needs_write_en": opentitan.needs_write_en(obj),
            "needs_read_en": opentitan.needs_read_en(obj),
            "needs_qe": opentitan.needs_qe(obj),
            "needs_int_qe": opentitan.needs_int_qe(obj),
            "fields_write_en_mask": opentitan.fields_write_en_mask(obj),
            "fields_write_en_bits": opentitan.fields_write_en_mask(obj).bit_count(),
            "is_homogeneous": opentitan.is_homogeneous(obj),
        }

        self.any_async_clk |= bool(obj.get("async_clk", False))
        self.all_async_clk &= bool(obj.get("async_clk", False))
        self.any_shadowed_reg |= bool(obj["shadowed"])
        self.any_hw_writable_reg |= bool(obj["hw_writable"])
        self.any_sw_writable_reg |= bool(obj["sw_writable"])

        if bool(obj.get("async_clk", False)):
            for index in range(array_size):
                reg_name = reg.inst_name + (f"_{index}" if array_size > 1 else "")
                self.async_registers.append((self.reg_index + index, reg_name))
        self.reg_index += array_size
        return obj

    def parse_signal(self, interface: dict[str, dict], sig: node.SignalNode) -> None:
        """Parse a signal node and return a dictionary."""
        signal = self.get_signal(sig)
        if "sigtype" not in signal:
            interface["signals"].append(signal)
        elif opentitan.SigType(signal["sigtype"]).is_pad():
            interface["pads"].append(signal)
        elif opentitan.SigType(signal["sigtype"]).is_interrupt():
            interface["interrupts"].append(signal["name"])
        elif opentitan.SigType(signal["sigtype"]).is_alert():
            interface["alerts"].append(signal["name"])
        elif opentitan.SigType(signal["sigtype"]).is_inter_module():
            interface["inter_modules"].append(signal)
        elif opentitan.SigType(signal["sigtype"]).is_sync():
            interface["sync_signals"].append(signal)
        else:
            print(f"WARNING: Unsupported signal type: {signal}.")

    def get_paramesters(self, obj: node.AddrmapNode | node.RegfileNode) -> [dict]:
        """Parse the custom property localparams and return a list of  dictionaries."""
        return [
            {"name": param.name, "type": "int", "value": param.get_value()}
            for param in obj.inst.parameters
        ]

    def parse_type(self, key: str, node: dict) -> dict:
        """Parse the custom properties and return a list of dictionaries."""
        if isinstance(node, UserStruct):
            obj = {}
            for k, v in node.members.items():
                obj.update(self.parse_type(k, v))
            return {key: obj}
        if isinstance(node, list):
            vec = [self.parse_type(key, item) for item in node]
            return {key: vec}
        if isinstance(node, UserEnum):
            return {key: node.name}
        if isinstance(node, BuiltinEnum):
            return {key: str(node.name)}

        if not isinstance(node, int | bool | str):
            print(f"WARNING: Type {type(node)} not fully supported")

        return {key: node}

    def get_udps(self, obj: node.AddrmapNode | node.RegfileNode) -> [dict]:
        """Parse the custom properties and return a list of dictionaries."""
        udps = obj.list_properties(include_native=False)
        if len(udps) < 1:
            return None
        res = {}
        for name in udps:
            udp = obj.get_property(name)
            res.update(self.parse_type(name, udp))

        return res

    def get_native_properties(self, obj: node.Node) -> [dict]:
        """Parse the native properties and return a list of dictionaries."""
        properties = obj.list_properties(include_udp=False)
        if len(properties) < 1:
            return None
        res = {}
        for name in properties:
            udp = obj.get_property(name)
            res.update(self.parse_type(name, udp))

        return res

    def get_interface(self, addrmap: node.AddrmapNode, defalt_name: None | str = None) -> dict:
        """Parse an interface and return a dictionary."""
        self.num_regs = 0
        self.num_windows = 0
        self.any_async_clk = False
        self.all_async_clk = True
        self.any_shadowed_reg = False
        self.any_hw_writable_reg = False
        self.any_sw_writable_reg = False
        self.async_registers.clear()

        interface = {}
        if defalt_name:
            interface["name"] = addrmap.inst_name or defalt_name

        if udps := self.get_udps(addrmap):
            interface["udps"] = udps

        if properties := self.get_native_properties(addrmap):
            interface.update(properties)

        interface["regs"] = []
        interface["windows"] = []
        for child in addrmap.children():
            if isinstance(child, node.RegNode):
                child_obj = self.get_reg(child)
                interface["regs"].append(child_obj)
            elif isinstance(child, node.RegfileNode):
                for reg in child.children():
                    child_obj = self.get_reg(reg)
                    interface["regs"].append(child_obj)
            elif isinstance(child, node.MemNode):
                child_obj = self.get_mem(child)
                interface["windows"].append(child_obj)
            elif isinstance(child, node.SignalNode):
                # Ignore: it should have being parsed by `parse_ip_block`
                continue
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
        interface["any_hw_writable_reg"] = self.any_hw_writable_reg
        interface["any_sw_writable_reg"] = self.any_sw_writable_reg
        interface["any_integrity_bypass"] = any(
            win["integrity_bypass"] for win in interface["windows"]
        )
        return interface

    def parse_ip_block(self, ip_block: node.AddrmapNode) -> dict:
        """Parse the ip_block node of an IP block and return a dictionary."""
        obj = {"name": ip_block.inst_name, "type": "device", "type_name": ip_block.type_name}
        if params := self.get_paramesters(ip_block):
            obj["parameters"] = params

        if udps := self.get_udps(ip_block):
            obj["udps"] = udps

        if properties := self.get_native_properties(ip_block):
            obj.update(properties)

        obj["offsets"] = self.parse_array(ip_block)
        obj["size"] = ip_block.array_stride if ip_block.is_array else ip_block.size

        obj["interfaces"] = []
        obj["alerts"] = []
        obj["pads"] = []
        obj["interrupts"] = []
        obj["signals"] = []
        obj["inter_modules"] = []
        obj["sync_signals"] = []
        for child in ip_block.children():
            if isinstance(child, node.AddrmapNode):
                child_obj = self.get_interface(child, DEFAULT_INTERFACE_NAME)
                obj["interfaces"].append(child_obj)
            elif isinstance(child, node.SignalNode):
                self.parse_signal(obj, child)
            elif isinstance(child, node.RegNode | node.MemNode | node.RegfileNode):
                continue
            else:
                print(f"ERROR: Unsupported type: {type(child)} in Ip block {ip_block.inst_name}.")
                raise TypeError

        # If the ip_block contain imediate registers, use a default interface name
        if len(ip_block.registers()) > 0:
            interface = self.get_interface(ip_block)
            obj["interfaces"].append(interface)

        return obj

    def parse_soc(self, root: node.AddrmapNode) -> dict:
        """Parse the SoC root node and return a dictionary."""
        if root.is_array:
            print("Error: Unsupported array type on the top")
            raise RuntimeError
        if not isinstance(root, node.AddrmapNode):
            print("Error: Top level must be an addrmap")
            raise TypeError

        obj = {"name": root.inst_name, "devices": []}
        for child in root.children():
            if isinstance(child, node.AddrmapNode):
                obj["devices"].append(self.parse_ip_block(child))
            elif isinstance(child, node.MemNode):
                obj["devices"].append(self.get_mem(child))
            else:
                print(
                    f"""Error: Unsupported type: {type(child)}, top level only supports
                      addrmap and mem components."""
                )
                raise TypeError

        interrupts = []
        for device in obj["devices"]:
            if len(device.get("interrupts", [])) == 0:
                continue
            is_array = len(device["offsets"]) > 0
            for idx, _ in enumerate(device["offsets"]):
                suffix = f"_{idx}" if is_array else ""
                interrupts.append(device["name"] + suffix)

        if len(interrupts) > 0:
            obj["interrupts"] = interrupts
        return obj
