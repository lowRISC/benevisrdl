
from systemrdl import RDLCompiler
from systemrdl import node
from systemrdl.rdltypes import OnReadType
from jinja2 import Environment, FileSystemLoader
import json
import opentitan
import pathlib

TEMPLATES_DIR = './src/templates'

def run(rdlc: RDLCompiler, obj: node.RootNode, out_dir: str):
    factory = DictFactory()
    data = factory.convert_addrmap_or_regfile(rdlc, obj.top)
    with open("/tmp/reg.json", "w", encoding='utf-8') as f:
        json.dump(data, f, indent=4)

    file_loader = FileSystemLoader(TEMPLATES_DIR)
    env = Environment(loader = file_loader)

    reg_pkg_tpl = env.get_template("reg_pkg.sv.tpl")
    stream = reg_pkg_tpl.stream(data)
    path = out_dir + "/{}_reg_pkg.sv".format(data["ip_name"])
    stream.dump(path)
    print(f"Generated {path}.")

    reg_top_tpl = env.get_template("reg_top.sv.tpl")
    stream = reg_top_tpl.stream(data)
    path = out_dir + "/{}_reg_top.sv".format(data["ip_name"])
    stream.dump(path)
    print(f"Generated {path}.")


class DictFactory:
    offset_bits: int = 1 # How many bits are needed to present the offset
    # array_idx: int = 0
    # array_instance_name: str = ""

    def convert_field(self, rdlc: RDLCompiler, obj: node.FieldNode) -> dict:
        field_obj = dict()
        field_obj['name'] = obj.inst_name
        field_obj['parent_name'] = obj.parent.inst_name
        field_obj['lsb'] = obj.lsb
        field_obj['msb'] = obj.msb
        field_obj['width'] = obj.msb - obj.lsb + 1 
        field_obj['reset'] = obj.get_property('reset', default=0)
        field_obj['hw_readable'] = obj.is_hw_readable
        field_obj['hw_writable'] = obj.is_hw_writable
        field_obj['sw_readable'] = obj.is_sw_readable
        field_obj['sw_writable'] = obj.is_sw_writable
        field_obj['sw_write_en'] = bool(obj.get_property('swwe'))
        field_obj['write_en_signal'] = self.convert_field(rdlc, obj.get_property('swwe')) if field_obj['sw_write_en'] else None
        field_obj['hw_write_en'] = bool(obj.get_property('we')) 
        field_obj['swmod'] = obj.get_property('swmod') 
        field_obj['clear_onread'] = obj.get_property('onread') == OnReadType.rclr
        field_obj['set_onread'] = obj.get_property('onread') == OnReadType.rset
        field_obj['mubi'] = obj.get_property('mubi', default=False)
        field_obj['async'] = obj.get_property('async', default=None)
        field_obj['sync'] = obj.get_property('sync', default=None)
        # print(f"{obj.inst_name}\n\t.swwe: {obj.get_property('swwe')}")
        # print(f"\t.next: {obj.get_property('next')}")
        return field_obj

    def convert_reg(self, rdlc: RDLCompiler, obj: node.RegNode) -> dict:
        reg_obj = dict()

        reg_obj['name'] = obj.inst_name
        reg_obj['width'] = obj.get_property('regwidth')
        reg_obj['hw_readable'] = obj.has_hw_readable
        reg_obj['hw_writable'] = obj.has_hw_writable
        reg_obj['sw_readable'] = obj.has_sw_readable
        reg_obj['sw_writable'] = obj.has_sw_writable
        reg_obj['external'] = obj.external
        reg_obj['shadowed'] = obj.get_property('shadowed', default=False)
        
        reg_obj['offsets'] = []
        if obj.is_array:
            offset = obj.raw_address_offset
            for _idx in range(0, obj.array_dimensions[0]):
                reg_obj['offsets'].append(offset)
                self.offset_bits = max(self.offset_bits, int(offset).bit_length())
                offset += obj.array_stride
        else:
            reg_obj['offsets'].append(obj.address_offset)
            self.offset_bits = max(self.offset_bits, int(obj.address_offset).bit_length())

        # Iterate over all the fields in this reg and convert them
        reg_obj['fields'] = []
        permit = 0
        sw_write_en = False
        for field in obj.fields():
            field = self.convert_field(rdlc, field)
            reg_obj['fields'].append(field)
            permit |= opentitan.register_permit_mask(field['msb'], field['lsb'])
            sw_write_en |= field['sw_write_en']

        reg_obj['permit'] = permit
        reg_obj['sw_write_en'] = sw_write_en
        reg_obj['async'] = False
        reg_obj['needs_write_en'] = opentitan.needs_write_en(reg_obj) 
        reg_obj['needs_read_en'] = opentitan.needs_read_en(reg_obj) 
        reg_obj['needs_qe'] = opentitan.needs_qe(reg_obj) 
        reg_obj['needs_int_qe'] = opentitan.needs_int_qe(reg_obj) 
        
        return reg_obj

    def convert_localparams(self, rdlc: RDLCompiler, obj: node.AddrmapNode|node.RegfileNode) -> [dict]:
        local_params = list(filter(lambda x: x == "localparam", obj.list_properties()))
        if len(local_params) < 1: 
            print(f"WARNING: Localparams not found.")
        local_params = list(local_params)[0]
        local_params = obj.get_property(local_params)
        res = [{"name" : param.name,  "type" : param.type_,  "value": param.value} for param in local_params]
        return res


    def convert_addrmap_or_regfile(self, rdlc: RDLCompiler, obj: node.AddrmapNode|node.RegfileNode) -> dict:
        if obj.is_array:
            print(f"WARNING: Unsupported array type: {type(obj)}, skiping...")

        json_obj = dict()
        json_obj["localparams"] = self.convert_localparams(rdlc, obj)
        if isinstance(obj, node.AddrmapNode):
            print(obj.inst_name)
            json_obj['type'] = 'addrmap'
        elif isinstance(obj, node.RegfileNode):
            json_obj['type'] = 'regfile'
        else:
            raise RuntimeError

        json_obj['ip_name'] = obj.inst_name
        json_obj['offset'] = obj.address_offset

        json_obj['registers'] = []
        for child in obj.children():
            if isinstance(child, (node.AddrmapNode, node.RegfileNode)):
                if isinstance(child, node.RegfileNode):
                    print(f"WARNING: Unsupported regfile skiping...")
                    continue
                json_child = self.convert_addrmap_or_regfile(rdlc, child)
            elif isinstance(child, node.RegNode):
                json_child = self.convert_reg(rdlc, child)
            else:
                print(f"WARNING: Unsupported type: {type(child)}, skiping...")
                continue

            json_obj['registers'].append(json_child)

        json_obj['offset_bits'] = self.offset_bits
        return json_obj


