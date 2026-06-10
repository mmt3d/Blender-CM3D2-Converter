# 「プロパティ」エリア → 「テクスチャ」タブ
import os
import bpy
import bmesh
import mathutils
from . import common
from . import compat
from . import cm3d2_data
from .translations.pgettext_functions import *

LAYOUT_FACTOR = 0.3


# 0.0～1.0までの値設定メニュー
@compat.BlRegister()
class TEXTURE_MT_context_texture_values_normal(bpy.types.Menu):
    bl_idname = 'TEXTURE_MT_context_texture_values_normal'
    bl_label = "値リスト"

    def draw(self, context):
        tex_slot = context.texture_slot
        for i in range(11):
            value = round(i * 0.1, 1)
            icon = 'LAYER_USED' if i % 2 else 'LAYER_ACTIVE'
            self.layout.operator('texture.set_color_value_old', text=str(value), icon=icon).color = list(tex_slot.color) + [value]


# _OutlineWidth用の値設定メニュー
@compat.BlRegister()
class TEXTURE_MT_context_texture_values_OutlineWidth(bpy.types.Menu):
    bl_idname = 'TEXTURE_MT_context_texture_values_OutlineWidth'
    bl_label = "値リスト"

    def draw(self, context):
        tex_slot = context.texture_slot
        for i in range(16):
            value = round(i * 0.0002, 4)
            icon = 'LAYER_USED' if i % 2 else 'LAYER_ACTIVE'
            self.layout.operator('texture.set_color_value_old', text=str(value), icon=icon).color = list(tex_slot.color) + [value]


# _RimPower用の値設定メニュー
@compat.BlRegister()
class TEXTURE_MT_context_texture_values_RimPower(bpy.types.Menu):
    bl_idname = 'TEXTURE_MT_context_texture_values_RimPower'
    bl_label = "値リスト"

    def draw(self, context):
        tex_slot = context.texture_slot
        for i in range(16):
            value = round(i * 2, 0)
            icon = 'LAYER_USED' if i % 2 else 'LAYER_ACTIVE'
            if value == 0:
                icon = 'ERROR'
            self.layout.operator('texture.set_color_value_old', text=str(value), icon=icon).color = list(tex_slot.color) + [value]


# _ZTest用の値設定メニュー
@compat.BlRegister()
class TEXTURE_MT_context_texture_values_ZTest(bpy.types.Menu):
    bl_idname = 'TEXTURE_MT_context_texture_values_ZTest'
    bl_label = "値リスト"

    node_name: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob:
            mate = ob.active_material
            if mate:
                return mate.use_nodes
        return False

    def draw(self, context):
        ob = context.active_object
        mate = ob.active_material
        if mate.use_nodes:
            mate.node_tree.nodes.get()
        tex_slot = context.texture_slot
        for i in range(9):
            value = round(i, 0)
            opr = self.layout.operator('texture.set_value', text=str(value))
            opr.node_name, opr.color = self.node_name, list(tex_slot.color) + [value]


@compat.BlRegister()
class CNV_OT_show_image(bpy.types.Operator):
    bl_idname = 'image.show_image'
    bl_label = "画像を表示"
    bl_description = "指定の画像をUV/画像エディターに表示します"
    bl_options = {'REGISTER', 'UNDO'}

    image_name: bpy.props.StringProperty(name="画像名")

    def execute(self, context):
        if self.image_name in context.blend_data.images:
            img = context.blend_data.images[self.image_name]
        else:
            self.report(type={'ERROR'}, message="指定された画像が見つかりません")
            return {'CANCELLED'}

        area = common.get_request_area(context, 'IMAGE_EDITOR')
        if area:
            common.set_area_space_attr(area, 'image', img)
        else:
            self.report(type={'ERROR'}, message="画像を表示できるエリアが見つかりませんでした")
            return {'CANCELLED'}
        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_replace_cm3d2_tex(bpy.types.Operator, common.NodeHandler):
    bl_idname = 'image.replace_cm3d2_tex'
    bl_label = "テクスチャを探す"
    bl_description = "CM3D2本体のインストールフォルダからtexファイルを探して開きます"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        mate = context.material
        return mate and mate.use_nodes
        # ob = bpy.context.active_object
        # if ob:
        # 	mate = ob.active_material
        # 	if mate:
        # 		return mate.use_nodes
        # return False

    def execute(self, context):
        node = self.get_node(context)
        if node and node.type == 'TEX_IMAGE':
            img = node.image
            if img and common.replace_cm3d2_tex(img, reload_path=True):
                self.report(type={'INFO'}, message=f_tip_("テクスチャファイルを読み込みました。file={}", img.filepath))
                node.image_user.use_auto_refresh = True
                return {'FINISHED'}
            else:
                msg = f_tip_("テクスチャファイルが見つかりませんでした。file={}", img.filepath) if img else f_tip_("イメージが設定されていません。")
                self.report(type={'ERROR'}, message=msg)
        else:
            self.report(type={'ERROR'}, message="テクスチャノードが見つからないため、スキップしました。")
        return {'CANCELLED'}


@compat.BlRegister()
class CNV_OT_sync_tex_color_ramps(bpy.types.Operator):
    bl_idname = 'texture.sync_tex_color_ramps'
    bl_label = "設定をプレビューに同期"
    bl_description = "設定値をテクスチャのプレビューに適用してわかりやすくします"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if getattr(context, 'material'):
            return True

        return getattr(context, 'texture_slot') and getattr(context, 'texture')

    def execute(self, context):
        for mate in context.blend_data.materials:
            if 'shader1' in mate and 'shader2' in mate:
                for slot in mate.texture_slots:
                    if slot:
                        common.set_texture_color(slot)
        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_set_default_toon_textures(bpy.types.Operator, common.NodeHandler):
    bl_idname = 'texture.set_default_toon_textures'
    bl_label = "トゥーンを選択"
    bl_description = "CM3D2にデフォルトで入っているトゥーンテクスチャを選択できます"
    bl_options = {'REGISTER', 'UNDO'}

    tex_name: bpy.props.StringProperty(name="テクスチャ名")

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob:
            mate = ob.active_material
            if mate and mate.use_nodes:
                return True

        return False

    def execute(self, context):
        node = self.get_node(context)
        if node is None:
            self.report(type={'ERROR'}, message=f_tip_("対象のノードが見つかりません={}", self.node_name))
            return {'CANCELLED'}

        texpathes = common.get_texpath_dict()
        texpath = texpathes.get(self.tex_name.lower())
        if texpath is None:
            if node.image is None:
                node.image = context.blend_data.images.new(self.tex_name, 128, 128)
                node.image.source = 'FILE'
            # 見つからない場合でも、テクスチャ名、ファイルパスに変更を反映
            node.image.name = self.tex_name
            node.image.filepath = self.tex_name + '.png'
        else:

            if node.image is None:
                node.image = bpy.data.images.load(texpath)
                node.image.source = 'FILE'
            else:
                node.image.filepath = texpath
                node.image.reload()

        node.image['cm3d2_path'] = common.get_tex_cm3d2path(node.image.filepath)
        self.report(type={'INFO'}, message=f_tip_("ノード({})のテクスチャを再設定しました。filepath={}", self.node_name, node.image.filepath))
        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_reload_textures(bpy.types.Operator):
    bl_idname = 'texture.reload_textures'
    bl_label = "イメージの再読込み"
    bl_description = "実ファイルパスの設定から、再読込み"
    bl_options = {'REGISTER', 'UNDO'}

    tex_name: bpy.props.StringProperty(name="テクスチャ名")

    @classmethod
    def poll(cls, context):
        return len(context.blend_data.images) > 0

    def execute(self, context):
        image = context.blend_data.images.get(self.tex_name)
        if image:
            image.reload()
            return {'FINISHED'}

        self.report(type={'ERROR'}, message=f_tip_("対象のイメージが見つかりません={}", self.tex_name))
        return {'CANCELLED'}


@compat.BlRegister()
class CNV_OT_auto_set_color_value(bpy.types.Operator):
    bl_idname = 'texture.auto_set_color_value'
    bl_label = "色設定値を自動設定"
    bl_description = "色関係の設定値をテクスチャの色情報から自動で設定します"
    bl_options = {'REGISTER', 'UNDO'}

    is_all: bpy.props.BoolProperty(name="全てが対象", default=True)
    saturation_multi: bpy.props.FloatProperty(name="彩度の乗算値", default=2.2, min=0, max=5, soft_min=0, soft_max=5, step=10, precision=2)
    value_multi: bpy.props.FloatProperty(name="明度の乗算値", default=0.3, min=0, max=5, soft_min=0, soft_max=5, step=10, precision=2)
    node_name: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if not ob or ob.type != 'MESH':
            return False

        mate = ob.active_material
        if not mate or mate.use_nodes is False:
            return False

        tex_node = mate.node_tree.nodes.get('_MainTex')
        # if tex_node is None:  # serial_numberが入っているケースを考慮する場合
        # 	for node in mate.node_tree.nodes:
        # 		if node.name.startswith('_MainTex.'):
        # 			name = common.remove_serial_number(node.name)
        # 			if name == '_MainTex':
        # 				tex_node = node
        # 				break
        if tex_node is None:
            return False

        img = tex_node.image
        return img and len(img.pixels)

        # found = False
        # if img and len(img.pixels):
        # 	found = True
        # else:
        # 	layer = me.uv_layers.active
        # 	if layer and len(layer.data):
        # 		# TODO imageはアクセスできないため、代替がないか確認
        # 		if layer.data[0].image:
        # 			if len(layer.data[0].image.pixels):
        # 				found = True
        # return found

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'is_all', icon='ACTION')
        row = self.layout.row()
        row.label(text="", icon='SHADING_RENDERED')
        row.prop(self, 'saturation_multi')
        row = self.layout.row()
        row.label(text="", icon='SHADING_SOLID')
        row.prop(self, 'value_multi')

    def execute(self, context):
        ob = context.active_object
        me = ob.data
        mate = ob.active_material
        # active_slot = context.texture_slot
        # active_tex = context.texture
        # tex_name = common.remove_serial_number(active_tex.name)

        target_slots = []
        if self.is_all:
            for node in mate.node_tree.nodes:
                node_name = common.remove_serial_number(node.name)
                if node_name in ['_ShadowColor', '_RimColor', '_OutlineColor']:
                    target_slots.append(node)
        else:
            target_slots.append(mate.node_tree.nodes)

        main_node = mate.node_tree.nodes.get('_MainTex')
        if main_node is None:
            for node in mate.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    name = common.remove_serial_number(node.name)
                    if name == '_MainTex':
                        main_node = node
                        break
        img = None
        if main_node:
            img = main_node.image

        if img is None or len(img.pixels) == 0:
            layer = me.uv_layers.active
            if len(layer.data) > 0:
                img = layer.data[0].image

        if img is None or len(img.pixels) == 0:
            return {'CANCELLED'}

        sample_count = 10
        img_width, img_height, img_channel = img.size[0], img.size[1], img.channels

        bm = bmesh.new()
        try:
            bm.from_mesh(me)
            uv_lay = bm.loops.layers.uv.active
            uvs = [l[uv_lay].uv[:] for f in bm.faces if f.material_index == ob.active_material_index for l in f.loops]
        finally:
            bm.free()

        avg_color = mathutils.Color([0, 0, 0])
        seek_interval = len(uvs) / sample_count
        for sample_index in range(sample_count):
            uv_index = int(seek_interval * sample_index)
            x, y = uvs[uv_index]
            x, y = int(x * img_width), int(y * img_height)

            pixel_index = ((y * img_width) + x) * img_channel
            color = mathutils.Color(img.pixels[pixel_index:pixel_index + 3])

            avg_color += color
        avg_color /= sample_count
        avg_color.s *= self.saturation_multi
        avg_color.v *= self.value_multi

        for slot in target_slots:
            slot.outputs[0].default_value = (avg_color[0], avg_color[1], avg_color[2], 1.0)

        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_quick_export_cm3d2_tex(bpy.types.Operator):
    bl_idname = 'image.quick_export_cm3d2_tex'
    bl_label = "texで保存"
    bl_description = "テクスチャの画像を同フォルダにtexとして保存します"
    bl_options = {'REGISTER'}

    node_name: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def execute(self, context):
        img = compat.get_tex_image(context, self.node_name)
        if img is None or len(img.pixels) == 0:
            self.report(type={'ERROR'}, message=f_tip_("イメージの取得に失敗しました。{}", self.node_name))
            return {'CANCELLED'}

        filepath = os.path.splitext(bpy.path.abspath(img.filepath))[0] + '.tex'
        if 'cm3d2_path' in img:
            path = img['cm3d2_path']
        else:
            path = common.get_tex_cm3d2path(img.filepath)
            img['cm3d2_path'] = path

        # 既存のファイルがあればそこから、バージョンとサイズを取得
        version = '1000'
        uv_rects = None
        if os.path.exists(filepath):
            tex_data = common.load_cm3d2tex(filepath, skip_data=True)
            if tex_data:
                version = str(tex_data[0])
                uv_rects = tex_data[2]
        bpy.types.Scene.MyUVRects = uv_rects
        with context.temp_override(edit_image=img):
            bpy.ops.image.export_cm3d2_tex(filepath=filepath, path=path, version=version)

        self.report(type={'INFO'}, message="同フォルダにtexとして保存しました。" + filepath)
        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_set_color_value(bpy.types.Operator, common.NodeHandler):
    bl_idname = 'texture.set_color_value'
    bl_label = "色設定値を設定"
    bl_description = "色タイプの設定値を設定します"
    bl_options = {'REGISTER', 'UNDO'}

    color: bpy.props.FloatVectorProperty(name="色", default=(0, 0, 0, 0), subtype='COLOR', size=4)

    @classmethod
    def poll(cls, context):
        mate = context.material
        return mate and mate.use_nodes

    def execute(self, context):
        node = self.get_node(context)
        if node is None:
            return {'CANCELLED'}

        node.outputs[0].default_value = self.color
        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_set_value(bpy.types.Operator, common.NodeHandler):
    bl_idname = 'texture.set_value'
    bl_label = "設定値を設定"
    bl_description = "floatタイプの設定値を設定します"
    bl_options = {'REGISTER', 'UNDO'}

    value: bpy.props.FloatProperty(name="value")

    @classmethod
    def poll(cls, context):
        mate = context.material
        return mate and mate.use_nodes

    def execute(self, context):
        node = self.get_node(context)
        if node is None:  # or node.type != 'VALUE':
            return {'CANCELLED'}
        node.outputs[0].default_value = self.value

        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_texture_reset_offset(bpy.types.Operator, common.NodeHandler):
    bl_idname = 'texture.reset_offset'
    bl_label = "テクスチャのオフセットをリセット"
    bl_description = "テクスチャのオフセットに初期値(0, 0)を設定します"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        node = self.get_node(context)
        if node and node.type == 'TEX_IMAGE':
            node.texture_mapping.translation[0] = 0
            node.texture_mapping.translation[1] = 0
            return {'FINISHED'}

        return {'CANCELLED'}


@compat.BlRegister()
class CNV_OT_texture_reset_scale(bpy.types.Operator, common.NodeHandler):
    bl_idname = 'texture.reset_scale'
    bl_label = "テクスチャのスケールをリセット"
    bl_description = "テクスチャのスケールに初期値(1, 1)を設定します"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        node = self.get_node(context)
        if node and node.type == 'TEX_IMAGE':
            node.texture_mapping.scale[0] = 1
            node.texture_mapping.scale[1] = 1
            return {'FINISHED'}

        return {'CANCELLED'}


@compat.BlRegister()
class CNV_OT_set_cm3d2path(bpy.types.Operator, common.NodeHandler):
    bl_idname = 'texture.set_cm3d2path'
    bl_label = "CM3D2パスを設定"
    bl_description = "texタイプのCM3D2パスを自動設定します"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        node = self.get_node(context)
        if node and node.type == 'TEX_IMAGE':
            img = node.image
            img['cm3d2_path'] = common.get_tex_cm3d2path(img.filepath)
            return {'FINISHED'}
        return {'CANCELLED'}


@compat.BlRegister()
class CNV_OT_setup_image_name(bpy.types.Operator, common.NodeHandler):
    bl_idname = 'texture.setup_image_name'
    bl_label = "イメージ名から拡張子を除外"
    bl_description = "texタイプのイメージ名から拡張子を除外します"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        node = self.get_node(context)
        if node and node.type == 'TEX_IMAGE':
            img = node.image
            common.setup_image_name(img)
            return {'FINISHED'}
        return {'CANCELLED'}


# Toon設定メニュー
class ToonSelectMenuBase:
    bl_label = "toon tex 選択"

    def draw(self, context):
        layout = self.layout
        cmd = 'texture.set_default_toon_textures'
        for toon_tex in cm3d2_data.TOON_TEXES:
            icon = 'LAYER_ACTIVE' if 'Shadow' not in toon_tex else 'LAYER_USED'
            opr = layout.operator(cmd, text=toon_tex, icon=icon)
            opr.node_name, opr.tex_name = self.node_name(), toon_tex

    def node_name(self):
        pass


@compat.BlRegister()
class TEXTURE_MT_texture_ToonRamp(bpy.types.Menu, ToonSelectMenuBase):
    bl_idname = 'TEXTURE_MT_texture_ToonRamp'

    def node_name(self):
        return '_ToonRamp'


@compat.BlRegister()
class TEXTURE_MT_texture_ShadowRateToon(bpy.types.Menu, ToonSelectMenuBase):
    bl_idname = 'TEXTURE_MT_texture_ShadowRateToon'

    def node_name(self):
        return '_ShadowRateToon'


@compat.BlRegister()
class TEXTURE_MT_texture_OutlineToonRamp(bpy.types.Menu, ToonSelectMenuBase):
    bl_idname = 'TEXTURE_MT_texture_OutlineToonRamp'

    def node_name(self):
        return '_OutlineToonRamp'
