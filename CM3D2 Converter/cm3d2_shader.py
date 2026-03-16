import bpy
from .compat import new_socket, map_shader_node


def toon_vector_node_tree():
    """トゥーンランプのベクトルを生成するノードツリーを作成する"""
    if (nt := NodeTreeHelper.get_or_create(name='Toon Vector', type='ShaderNodeTree')).is_exists:
        return nt.node_tree

    # Set interfaces
    nt.socket('Light Switch', 'INPUT', 'NodeSocketFloat')
    nt.socket('Toon Vector', 'OUTPUT', 'NodeSocketVector')

    # Set nodes
    group_input = nt.node('Group Input', type='NodeGroupInput', location=(-380.0, 80.0))
    math_less_than = nt.node('Math Less Than', type='ShaderNodeMath', location=(220.0, 160.0), operation='LESS_THAN', inputs={'Value': 0.5})
    diffuse_bsdf = nt.node('Diffuse BSDF', type='ShaderNodeBsdfDiffuse', location=(-180.0, -80.0), inputs={'Color': (1.0, 1.0, 1.0, 1.0)})
    shader_to_rgb = nt.node('Shader To RGB', type='ShaderNodeShaderToRGB', location=(20.0, -80.0))
    map_range = nt.node('Map Range', type='ShaderNodeMapRange', location=(220.0, -20.0), inputs={'From Min': 0.0, 'From Max': 1.2, 'To Min': 0.0, 'To Max': 1.0})
    mix = nt.node('Mix', type='ShaderNodeMix', location=(420.0, 60.0), data_type='FLOAT', blend_type='MIX', inputs={'B': 1.0})
    combine_xyz = nt.node('Combine XYZ', type='ShaderNodeCombineXYZ', location=(620.0, 20.0), inputs={'Y': 0.5, 'Z': 0.0})
    group_output = nt.node('Group Output', type='NodeGroupOutput', location=(820.0, 20.0))

    # Set links
    nt.link(group_input.outputs('Light Switch'), math_less_than.inputs('Value'))
    nt.link(diffuse_bsdf.outputs('BSDF'), shader_to_rgb.inputs('Shader'))
    nt.link(shader_to_rgb.outputs('Color'), map_range.inputs('Value'))
    nt.link(map_range.outputs('Result'), mix.inputs('A'))
    nt.link(math_less_than.outputs('Value'), mix.inputs('Factor'))
    nt.link(mix.outputs('Result'), combine_xyz.inputs('X'))
    nt.link(combine_xyz.outputs('Vector'), group_output.inputs('Toon Vector'))

    return nt.node_tree


def com3d2_shader_node_tree():
    """COM3D2のシェーダーを再現するノードツリーを作成する"""
    if (nt := NodeTreeHelper.get_or_create(name='COM3D2 Shader', type='ShaderNodeTree')).is_exists:
        return nt.node_tree

    # Set interfaces
    nt.socket('Shader', 'OUTPUT', 'NodeSocketShader')
    nt.socket('MainTex', 'INPUT', 'NodeSocketColor')
    nt.socket('MainTexAlpha', 'INPUT', 'NodeSocketFloat')
    nt.socket('ToonRamp', 'INPUT', 'NodeSocketColor', default=(1.0, 1.0, 1.0, 1.0))
    nt.socket('ShadowTex', 'INPUT', 'NodeSocketColor')
    nt.socket('ShadowRateToon', 'INPUT', 'NodeSocketColor', default=(1.0, 1.0, 1.0, 1.0))
    nt.socket('HiTex', 'INPUT', 'NodeSocketColor')
    nt.socket('OutlineTex', 'INPUT', 'NodeSocketColor')
    nt.socket('OutlineToonRamp', 'INPUT', 'NodeSocketColor', default=(1.0, 1.0, 1.0, 1.0))
    nt.socket('Color', 'INPUT', 'NodeSocketColor', default=(1.0, 1.0, 1.0, 1.0))
    nt.socket('ShadowColor', 'INPUT', 'NodeSocketColor')
    nt.socket('RimColor', 'INPUT', 'NodeSocketColor')
    nt.socket('OutlineColor', 'INPUT', 'NodeSocketColor')
    nt.socket('Shininess', 'INPUT', 'NodeSocketFloat')
    nt.socket('RimPower', 'INPUT', 'NodeSocketFloat', default=25.0)
    nt.socket('RimShift', 'INPUT', 'NodeSocketFloat')
    nt.socket('HiRate', 'INPUT', 'NodeSocketFloat')
    nt.socket('HiPow', 'INPUT', 'NodeSocketFloat')
    nt.socket('UseTransparent', 'INPUT', 'NodeSocketFloat', default=0.0)

    # Set nodes
    group_output = nt.node('Group Output', type='NodeGroupOutput', location=(1760.0, 400.0))
    group_input = nt.node('Group Input', type='NodeGroupInput', location=(-960.0, 40.0))

    geometry = nt.node('Geometry', type='ShaderNodeNewGeometry', location=(-960.0, 400.0))
    glossy_bsdf = nt.node('Glossy BSDF', type='ShaderNodeBsdfGlossy', location=(-960.0, -500.0), distribution='MULTI_GGX')
    layer_weight = nt.node('Layer Weight', type='ShaderNodeLayerWeight', location=(-960.0, -780.0))

    mix_main = nt.node('Mix Main', type='ShaderNodeMix', location=(-400.0, 560.0), blend_type='MULTIPLY', data_type='RGBA', inputs={'Factor': 1.0})
    mix_main_toon = nt.node('Mix Main Toon', type='ShaderNodeMix', location=(-140.0, 560.0), blend_type='MULTIPLY', data_type='RGBA', inputs={'Factor': 1.0})
    mix_shadow = nt.node('Mix Shadow', type='ShaderNodeMix', location=(-400.0, 300.0), blend_type='DODGE', data_type='RGBA', inputs={'Factor': 1.0})
    mix_shadow_toon = nt.node('Mix Shadow Toon', type='ShaderNodeMix', location=(-140.0, 300.0), blend_type='MULTIPLY', data_type='RGBA', inputs={'Factor': 1.0})
    mix_main_shadow = nt.node('Mix Main/Shadow', type='ShaderNodeMix', location=(120.0, 460.0), blend_type='MIX', data_type='RGBA')
    mix_shininess = nt.node('Mix Shininess', type='ShaderNodeMix', location=(380.0, 300.0), blend_type='SCREEN', data_type='RGBA', inputs={'B': (1.0, 1.0, 1.0, 1.0)})
    mix_rim = nt.node('Mix Rim', type='ShaderNodeMix', location=(640.0, 300.0), blend_type='MULTIPLY', data_type='RGBA', inputs={'Factor': 1.0})
    mix_high = nt.node('Mix High', type='ShaderNodeMix', location=(900.0, 300.0), blend_type='ADD', data_type='RGBA')
    mix_final = nt.node('Mix Final', type='ShaderNodeMix', location=(1140.0, 300.0), blend_type='MIX', data_type='RGBA')
    toon_bsdf = nt.node('Toon BSDF', type='ShaderNodeBsdfToon', location=(1340.0, 300.0), component='DIFFUSE')
    trans_bsdf = nt.node('Transparent BSDF', type='ShaderNodeBsdfTransparent', location=(1340.0, 400.0))
    shader_mix = nt.node('Shader Mix', type='ShaderNodeMixShader', location=(1560.0, 400.0), inputs={'Factor': 1.0})

    mix_outline = nt.node('Mix Outline', type='ShaderNodeMix', location=(640.0, -20.0), blend_type='SCREEN', data_type='RGBA')
    mix_outline_toon = nt.node('Mix Outline Toon', type='ShaderNodeMix', location=(900.0, -20.0), blend_type='MULTIPLY', data_type='RGBA')

    high_map_range = nt.node('High Map Range', type='ShaderNodeMapRange', location=(-400.0, 20.0), inputs={'From Min': 0.0, 'From Max': 50.0, 'To Min': 1.0, 'To Max': -0.5})
    high_math_mul = nt.node('High Math Multiply', type='ShaderNodeMath', location=(-140.0, 20.0), operation='MULTIPLY', inputs={'Value': {1: 2.0}})
    high_contrast = nt.node('High Contrast', type='ShaderNodeBrightContrast', location=(120.0, 20.0))

    shader_to_rgb = nt.node('Shader To RGB', type='ShaderNodeShaderToRGB', location=(-400.0, -280.0))
    shine_math_mul_add = nt.node('Shininess Math Multiply Add', type='ShaderNodeMath', location=(-140.0, -280.0), operation='MULTIPLY_ADD')
    shine_math_mul = nt.node('Shininess Math Multiply', type='ShaderNodeMath', location=(120.0, -280.0), operation='MULTIPLY', inputs={'Value': {1: 0.4}})
    shine_math_inv = nt.node('Shininess Math Invert', type='ShaderNodeMath', location=(-400.0, -400.0), operation='MULTIPLY', inputs={'Value': {1: -1.0}})

    rim_shift_add = nt.node('Rim Shift Add', type='ShaderNodeMath', location=(-680.0, -660.0), operation='ADD')
    rim_math_log = nt.node('Rim Math Logarithm', type='ShaderNodeMath', location=(-480.0, -660.0), operation='LOGARITHM', inputs={'Value': {1: 2.0}})
    rim_math_mul = nt.node('Rim Math Multiply', type='ShaderNodeMath', location=(-280.0, -660.0), operation='MULTIPLY')
    rim_math_max = nt.node('Rim Math Maximum', type='ShaderNodeMath', location=(-80.0, -660.0), operation='MAXIMUM', inputs={'Value': {1: -0.3}})
    mix_rim_color = nt.node('Mix Rim Color', type='ShaderNodeMix', location=(120.0, -480.0), blend_type='MIX', data_type='RGBA', inputs={'Factor': 1.0})
    mix_rim_shift = nt.node('Mix Rim Shift', type='ShaderNodeMix', location=(380.0, -480.0), blend_type='ADD', data_type='RGBA', inputs={'Factor': 1.0, 'B': (1.0, 1.0, 1.0, 1.0)})

    # Set links
    nt.link(group_input.outputs('MainTex'), mix_main.inputs('A'))
    nt.link(group_input.outputs('Color'), mix_main.inputs('B'))
    nt.link(mix_main.outputs('Result'), mix_main_toon.inputs('A'))
    nt.link(group_input.outputs('ToonRamp'), mix_main_toon.inputs('B'))
    nt.link(group_input.outputs('ShadowTex'), mix_shadow.inputs('A'))
    nt.link(mix_shadow.outputs('Result'), mix_shadow_toon.inputs('A'))
    nt.link(group_input.outputs('ToonRamp'), mix_shadow_toon.inputs('B'))
    nt.link(group_input.outputs('ShadowColor'), mix_shadow.inputs('B'))
    nt.link(group_input.outputs('ShadowRateToon'), mix_main_shadow.inputs('Factor'))
    nt.link(mix_shadow_toon.outputs('Result'), mix_main_shadow.inputs('A'))
    nt.link(mix_main_toon.outputs('Result'), mix_main_shadow.inputs('B'))
    nt.link(group_input.outputs('OutlineTex'), mix_outline.inputs('B'))
    nt.link(group_input.outputs('OutlineColor'), mix_outline.inputs('A'))
    nt.link(mix_outline.outputs('Result'), mix_outline_toon.inputs('A'))
    nt.link(group_input.outputs('OutlineToonRamp'), mix_outline_toon.inputs('B'))
    nt.link(mix_outline_toon.outputs('Result'), mix_final.inputs('B'))
    nt.link(mix_main_shadow.outputs('Result'), mix_shininess.inputs('A'))
    nt.link(mix_shininess.outputs('Result'), mix_rim.inputs('A'))
    nt.link(group_input.outputs('RimColor'), mix_rim.inputs('B'))
    nt.link(mix_rim.outputs('Result'), mix_high.inputs('A'))
    nt.link(geometry.outputs('Backfacing'), mix_final.inputs('Factor'))
    nt.link(mix_high.outputs('Result'), mix_final.inputs('A'))
    nt.link(mix_final.outputs('Result'), toon_bsdf.inputs('Color'))
    nt.link(toon_bsdf.outputs('BSDF'), shader_mix.inputs('Shader', 1))
    nt.link(group_input.outputs('MainTexAlpha'), shader_mix.inputs('Factor'))
    nt.link(group_input.outputs('UseTransparent'), trans_bsdf.inputs('Color'))
    nt.link(trans_bsdf.outputs('BSDF'), shader_mix.inputs('Shader', 0))
    nt.link(shader_mix.outputs('Shader'), group_output.inputs('Shader'))

    nt.link(group_input.outputs('HiRate'), mix_high.inputs('Factor'))
    nt.link(group_input.outputs('HiPow'), high_map_range.inputs('Value'))
    nt.link(high_map_range.outputs('Result'), high_contrast.inputs('Brightness'))
    nt.link(group_input.outputs('HiTex'), high_contrast.inputs('Color'))
    nt.link(high_map_range.outputs('Result'), high_math_mul.inputs('Value', 0))
    nt.link(high_math_mul.outputs('Value'), high_contrast.inputs('Contrast'))
    nt.link(high_contrast.outputs('Color'), mix_high.inputs('B'))

    nt.link(glossy_bsdf.outputs('BSDF'), shader_to_rgb.inputs('Shader'))
    nt.link(shader_to_rgb.outputs('Color'), shine_math_mul_add.inputs('Value', 0))
    nt.link(group_input.outputs('Shininess'), shine_math_mul_add.inputs('Value', 1))
    nt.link(group_input.outputs('Shininess'), shine_math_inv.inputs('Value', 0))
    nt.link(shine_math_inv.outputs('Value'), shine_math_mul_add.inputs('Value', 2))
    nt.link(shine_math_mul_add.outputs('Value'), shine_math_mul.inputs('Value', 0))
    nt.link(shine_math_mul.outputs('Value'), mix_shininess.inputs('Factor'))

    nt.link(group_input.outputs('RimShift'), rim_shift_add.inputs('Value', 0))
    nt.link(layer_weight.outputs('Facing'), rim_shift_add.inputs('Value', 1))
    nt.link(rim_shift_add.outputs('Value'), rim_math_log.inputs('Value', 0))
    nt.link(rim_math_log.outputs('Value'), rim_math_mul.inputs('Value', 0))
    nt.link(group_input.outputs('RimPower'), rim_math_mul.inputs('Value', 1))
    nt.link(rim_math_mul.outputs('Value'), rim_math_max.inputs('Value', 0))
    nt.link(group_input.outputs('RimColor'), mix_rim_color.inputs('A'))
    nt.link(rim_math_max.outputs('Value'), mix_rim_color.inputs('B'))
    nt.link(mix_rim_color.outputs('Result'), mix_rim_shift.inputs('A'))
    nt.link(mix_rim_shift.outputs('Result'), mix_rim.inputs('B'))

    return nt.node_tree


def bind_light_switch(socket):
    """
    ライトのオンオフを制御するドライバをソケットに設定する
    これを使ってshadowTexの表示制御する
    """
    # Set light
    light = find_or_create_light()

    # Set driver for light switch
    driver = socket.driver_add('default_value').driver
    driver.type = 'SCRIPTED'
    driver.expression = '1 - light_switch'
    var = driver.variables.new()
    var.name = 'light_switch'
    var.type = 'SINGLE_PROP'
    target = var.targets[0]
    target.id_type = 'OBJECT'
    target.id = light
    target.data_path = 'hide_render'
    socket.id_data.update_tag()


def bind_use_transparent(socket, material):
    """透過の使用を制御するドライバをソケットに設定する"""
    driver = socket.driver_add('default_value').driver
    driver.type = 'SCRIPTED'
    driver.expression = 'use_transparent'
    var = driver.variables.new()
    var.name = 'use_transparent'
    var.type = 'SINGLE_PROP'
    target = var.targets[0]
    target.id_type = 'MATERIAL'
    target.id = material
    target.data_path = 'use_transparency_overlap'
    socket.id_data.update_tag()


def find_or_create_light():
    """既存のライトを探し、存在しない場合は新規に追加する"""
    light = None
    # 既存のライトを探す
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            light = obj
            break
    # 存在しない場合、追加する
    if light is None:
        light_data = bpy.data.lights.new(name="COM3D2 Light", type='POINT')
        light = bpy.data.objects.new(name="COM3D2 Light", object_data=light_data)
        bpy.context.collection.objects.link(light)
    return light


def invalidate_cache():
    """ノードツリーのキャッシュを無効化する"""
    for name in ['Toon Vector', 'COM3D2 Shader']:
        node_group = bpy.data.node_groups.get(name)
        if node_group:
            bpy.data.node_groups.remove(node_group)


class NodeTreeHelper:
    """シェーダーノードツリーの作成と管理を簡略化しバージョンによる違いを吸収するヘルパークラス"""
    def __init__(self, node_tree: bpy.types.NodeTree):
        self.node_tree = node_tree
        self.is_exists = False

    @classmethod
    def get_or_create(cls, name: str, type: str):
        nt = bpy.data.node_groups.get(name)
        is_exists = True
        if nt is None:
            nt = bpy.data.node_groups.new(name=name, type=type)
            is_exists = False

        helper = cls(nt)
        helper.is_exists = is_exists
        return helper

    def socket(self, name: str, in_out: str, socket_type: str, default = None):
        socket = new_socket(self.node_tree, name, in_out, socket_type)
        if default is not None:
            socket.default_value = default
        return socket

    def node(self, name: str, type: str, inputs: dict = None, **kwargs):
        type, socket_map, inputs = map_shader_node(type, inputs)
        return NodeHelper(self.node_tree.nodes.new(type), name, inputs=inputs, socket_map=socket_map, **kwargs)

    def link(self, out_socket, in_socket):
        self.node_tree.links.new(out_socket, in_socket)


class NodeHelper:
    """シェーダーノードの作成と管理を簡略化するためのヘルパークラス"""
    def __init__(self, node: bpy.types.Node, name: str, inputs: dict = None, socket_map: dict = None, **kwargs):
        self.node = node
        self.node.name = name
        self.socket_map = socket_map if socket_map is not None else {}
        inputs = inputs if inputs is not None else {}
        for key, value in kwargs.items():
            if hasattr(self.node, key):
                setattr(self.node, key, value)
        for key, value in inputs.items():
            if key in self.socket_map:
                key = self.socket_map[key]
            if isinstance(value, dict):
                for index, subvalue in value.items():
                    self.inputs(key, index).default_value = subvalue
            else:
                self.inputs(key).default_value = value

    def outputs(self, name: str, type: str|int = None):
        return self._sockets(self.node.outputs, name)

    def inputs(self, name: str, type: str|int = None):
        return self._sockets(self.node.inputs, name, type)

    def _sockets(self, sockets, name: str, type: str|int = None):
        if name in self.socket_map:
            name = self.socket_map[name]
        name_filtered = [x for x in sockets if x.name == name]
        if type is not None:
            if isinstance(type, int):
                return name_filtered[type]
            else:
                return next(filter(lambda x: x.type == type, name_filtered))
        elif len(name_filtered) == 1:
            return name_filtered[0]
        elif len(name_filtered) == 0:
            return None
        else:
            try_types = []
            if hasattr(self.node, 'data_type'):
                try_types.append(self.node.data_type)
                if self.node.data_type.startswith('FLOAT_'):
                    try_types.append(self.node.data_type[6:])
            for t in try_types:
                type_filtered = list(filter(lambda x: x.type == t, name_filtered))
                if len(type_filtered) > 0:
                    return type_filtered[0]
        return name_filtered[0]
