# 「プロパティ」エリア → 「アーマチュアデータ」タブ
import os
import bpy
import mathutils
from . import common, compat
from .bone_data import (calc_bone_data_diff, calc_local_bone_data_diff,
                        merge_bone_data_with_parent_names, merge_local_bone_data, parent_name_map, DEFAULT_THRESHOLD)
from .translations import *


# メニュー等に項目追加
def menu_func(self, context):
    import re
    ob = context.active_object
    if not ob or ob.type != 'ARMATURE':
        return

    arm = ob.data

    bone_data_count = 0
    if 'BoneData:0' in arm and 'LocalBoneData:0' in arm:
        for key in arm.keys():
            if re.search(r'^(Local)?BoneData:\d+$', key):
                bone_data_count += 1
    enabled_clipboard = False
    clipboard = context.window_manager.clipboard
    if 'BoneData:' in clipboard and 'LocalBoneData:' in clipboard:
        enabled_clipboard = True
    box = self.layout.box()
    box.label(text="CM3D2用", icon_value=common.kiss_icon())
    if bone_data_count or enabled_clipboard:
        col = box.column(align=True)
        row = col.row(align=True)
        row.label(text="ボーン情報", icon='CONSTRAINT_BONE')
        sub_row = row.row()
        sub_row.alignment = 'RIGHT'
        if bone_data_count:
            sub_row.label(text=str(bone_data_count), icon='CHECKBOX_HLT')
        else:
            sub_row.label(text="0", icon='CHECKBOX_DEHLT')
        row = col.row(align=True)
        row.operator('object.copy_armature_bone_data_property', icon='COPYDOWN', text="Copy")
        row.operator('object.paste_armature_bone_data_property', icon='PASTEDOWN', text="Paste")
        row.operator('object.remove_armature_bone_data_property', icon='X', text="")

    flag = False
    for bone in arm.bones:
        if not flag and re.search(r'[_ ]([rRlL])[_ ]', bone.name):
            flag = True
        if not flag and bone.name.count('*') == 1:
            if re.search(r'\.([rRlL])$', bone.name):
                flag = True
        if flag:
            col = box.column(align=True)
            col.label(text="ボーン名変換", icon='SORTALPHA')
            row = col.row(align=True)
            row.operator('armature.decode_cm3d2_bone_names', text="CM3D2 → Blender", icon='BLENDER')
            row.operator('armature.encode_cm3d2_bone_names', text="Blender → CM3D2", icon_value=common.kiss_icon())
            break
        
    col = box.column(align=True)
    col.label(text="ボーン情報更新", icon='FILE_REFRESH')
    row = col.row(align=True)
    row.operator('armature.update_bone_data', icon='ARMATURE_DATA')
    row.operator('armature.rename_base_bone', icon='BONE_DATA')

    if bone_data_count:
        col = box.column(align=True)
        col.label(text="Armature Operators", icon='OUTLINER_OB_ARMATURE')
        col.operator('object.add_cm3d2_twist_bones', text="Connect Twist Bones", icon='CONSTRAINT_BONE')
        col.operator('object.cleanup_scale_bones', text="Cleanup Scale Bones", icon='X')
        
    if 'isPrimedPose' in arm:
        col = box.column(align=True)
        if arm['isPrimedPose']:
            pose_text = "Armature State: Primed"
        else:
            pose_text = "Armature State: Normal"
        col.label(text=pose_text, icon='POSE_HLT')
        col.enabled = arm['isPrimedPose']

        row = col.row(align=True)
        
        sub_row = row.row(align=True)
        sub_row.operator('pose.set_current_rest_frame', icon='ARMATURE_DATA')

        sub_row = row.row(align=True)
        sub_row.operator('pose.set_original_rest_frame', icon='OUTLINER_DATA_ARMATURE')

        row = col.row(align=True)
        
        sub_row = row.row(align=True)
        sub_row.operator('pose.revert_primed_pose', icon='LOOP_BACK')


@compat.BlRegister()
class CNV_OT_decode_cm3d2_bone_names(bpy.types.Operator):
    bl_idname = 'armature.decode_cm3d2_bone_names'
    bl_label = "ボーン名をCM3D2用→Blender用に変換"
    bl_description = "CM3D2で使われてるボーン名をBlenderで左右対称編集できるように変換します"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        import re
        ob = context.active_object
        if ob:
            if ob.type == 'ARMATURE':
                arm = ob.data
                for bone in arm.bones:
                    if re.search(r'[_ ]([rRlL])[_ ]', bone.name):
                        return True
        return False

    def execute(self, context):
        ob = context.active_object
        arm = ob.data
        convert_count = 0
        for bone in arm.bones:
            bone_name = common.decode_bone_name(bone.name)
            if bone_name != bone.name:
                bone.name = bone_name
                convert_count += 1
        if convert_count == 0:
            self.report(type={'WARNING'}, message="変換できる名前が見つかりませんでした")
        else:
            self.report(type={'INFO'}, message="ボーン名をBlender用に変換しました")
        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_encode_cm3d2_bone_names(bpy.types.Operator):
    bl_idname = 'armature.encode_cm3d2_bone_names'
    bl_label = "ボーン名をBlender用→CM3D2用に変換"
    bl_description = "CM3D2で使われてるボーン名に元に戻します"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        import re
        ob = context.active_object
        if ob:
            if ob.type == 'ARMATURE':
                arm = ob.data
                for bone in arm.bones:
                    if bone.name.count('*') == 1 and re.search(r'\.([rRlL])$', bone.name):
                        return True
        return False

    def execute(self, context):
        ob = context.active_object
        arm = ob.data
        convert_count = 0
        for bone in arm.bones:
            bone_name = common.encode_bone_name(bone.name)
            if bone_name != bone.name:
                bone.name = bone_name
                convert_count += 1
        if convert_count == 0:
            self.report(type={'WARNING'}, message="変換できる名前が見つかりませんでした")
        else:
            self.report(type={'INFO'}, message="ボーン名をCM3D2用に戻しました")
        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_copy_armature_bone_data_property(bpy.types.Operator):
    bl_idname = 'object.copy_armature_bone_data_property'
    bl_label = "ボーン情報をコピー"
    bl_description = "カスタムプロパティのボーン情報をクリップボードにコピーします"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob:
            if ob.type == 'ARMATURE':
                arm = ob.data
                if 'BoneData:0' in arm and 'LocalBoneData:0' in arm:
                    return True
        return False

    def execute(self, context):
        output_text = ""
        ob = context.active_object.data
        pass_count = 0
        if 'BaseBone' in ob:
            output_text += 'BaseBone:' + ob['BaseBone'] + '\n'
        for i in range(99999):
            name = 'BoneData:' + str(i)
            if name in ob:
                output_text += 'BoneData:' + ob[name] + '\n'
            else:
                pass_count += 1
            if 10 < pass_count:
                break
        pass_count = 0
        for i in range(99999):
            name = 'LocalBoneData:' + str(i)
            if name in ob:
                output_text += 'LocalBoneData:' + ob[name] + '\n'
            else:
                pass_count += 1
            if 10 < pass_count:
                break
        context.window_manager.clipboard = output_text
        self.report(type={'INFO'}, message="ボーン情報をクリップボードにコピーしました")
        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_paste_armature_bone_data_property(bpy.types.Operator):
    bl_idname = 'object.paste_armature_bone_data_property'
    bl_label = "ボーン情報を貼付け"
    bl_description = "カスタムプロパティのボーン情報をクリップボードから貼付けます"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob:
            if ob.type == 'ARMATURE':
                clipboard = context.window_manager.clipboard
                if 'BoneData:' in clipboard and 'LocalBoneData:' in clipboard:
                    return True
        return False

    def execute(self, context):
        ob = context.active_object.data
        pass_count = 0
        for i in range(99999):
            name = 'BoneData:' + str(i)
            if name in ob:
                del ob[name]
            else:
                pass_count += 1
            if 10 < pass_count:
                break
        pass_count = 0
        for i in range(99999):
            name = 'LocalBoneData:' + str(i)
            if name in ob:
                del ob[name]
            else:
                pass_count += 1
            if 10 < pass_count:
                break
        bone_data_count = 0
        local_bone_data_count = 0
        for line in context.window_manager.clipboard.split('\n'):
            if line.startswith('BaseBone:'):
                ob['BaseBone'] = line[9:]  # len('BaseData:') == 9
                continue

            if line.startswith('BoneData:'):
                if line.count(',') >= 4:
                    name = 'BoneData:' + str(bone_data_count)
                    ob[name] = line[9:]  # len('BoneData:') == 9
                    bone_data_count += 1
                continue

            if line.startswith('LocalBoneData:'):
                if line.count(',') == 1:
                    name = 'LocalBoneData:' + str(local_bone_data_count)
                    ob[name] = line[14:]  # len('LocalBoneData:') == 14
                    local_bone_data_count += 1

        self.report(type={'INFO'}, message="ボーン情報をクリップボードから貼付けました")
        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_remove_armature_bone_data_property(bpy.types.Operator):
    bl_idname = 'object.remove_armature_bone_data_property'
    bl_label = "ボーン情報を削除"
    bl_description = "カスタムプロパティのボーン情報を全て削除します"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob:
            if ob.type == 'ARMATURE':
                arm = ob.data
                if 'BoneData:0' in arm and 'LocalBoneData:0' in arm:
                    return True
        return False

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.label(text="カスタムプロパティのボーン情報を全て削除します", icon='CANCEL')

    def execute(self, context):
        ob = context.active_object.data
        pass_count = 0
        if 'BaseBone' in ob:
            del ob['BaseBone']
        for i in range(99999):
            name = 'BoneData:' + str(i)
            if name in ob:
                del ob[name]
            else:
                pass_count += 1
            if 10 < pass_count:
                break
        pass_count = 0
        for i in range(99999):
            name = 'LocalBoneData:' + str(i)
            if name in ob:
                del ob[name]
            else:
                pass_count += 1
            if 10 < pass_count:
                break
        self.report(type={'INFO'}, message="ボーン情報を削除しました")
        return {'FINISHED'}

@compat.BlRegister()
class CNV_PG_bone_data_diff_item(bpy.types.PropertyGroup):
    bl_idname = 'CNV_PG_bone_data_diff_item'

    bone_name: bpy.props.StringProperty()
    parent_name: bpy.props.StringProperty(options={'HIDDEN'})
    upd_parent: bpy.props.BoolProperty(default=False)
    diff_parent: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    # BoneData 用
    upd_loc: bpy.props.BoolProperty(default=False)
    diff_loc: bpy.props.FloatProperty(precision=5, options={'HIDDEN'})

    upd_rot: bpy.props.BoolProperty(default=False)
    diff_rot: bpy.props.FloatProperty(precision=5, options={'HIDDEN'})

    upd_scl: bpy.props.BoolProperty(default=False)
    diff_scl: bpy.props.FloatProperty(precision=5, options={'HIDDEN'})

    # LocalBoneData 用
    upd_local: bpy.props.BoolProperty(default=False)
    diff_local: bpy.props.FloatProperty(precision=5, options={'HIDDEN'})

    mode: bpy.props.EnumProperty(items=[('INSERT', '', ''), ('UPDATE', '', ''), ('DELETE', '', '')], default='UPDATE')
    approved: bpy.props.BoolProperty(default=True)


@compat.BlRegister()
class CNV_UL_bone_data_diff_list(bpy.types.UIList):
    bl_idname = 'CNV_UL_bone_data_diff_list'

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0):

        split = layout.split(factor=0.48, align=True)
        col1 = split.column()
        row = col1.row(align=True)

        # ボーン名
        row.label(text=item.bone_name)

        if item.diff_parent:
            row.prop(item, 'upd_parent', text=item.parent_name)
        elif item.mode != 'UPDATE':
            row.label(text=item.parent_name)
        else:
            row.label(text=item.parent_name)

        col2 = split.column()
        row = col2.row(align=True)
        if item.mode != 'UPDATE':
            if item.mode == 'INSERT':
                row.prop(item, 'approved', text='➕ ' + _("New"))
            else:
                row.prop(item, 'approved', text='🗑 ' + _("Delete"))
            for i in range(3):
                row.label(text='')
            return

        row.prop(item, 'upd_loc', text=f'{item.diff_loc:.6f}')
        row.prop(item, 'upd_rot', text=f'{item.diff_rot:.6f}')
        row.prop(item, 'upd_scl', text=f'{item.diff_scl:.6f}')
        row.prop(item, 'upd_local', text=f'{item.diff_local:.6f}')


@compat.BlRegister()
class CNV_OT_armature_update_bone_data(bpy.types.Operator):
    bl_idname = 'armature.update_bone_data'
    bl_label = "ボーン情報取り込み"
    bl_description = "アーマチュアを解析してBoneData/LocalBoneDataを更新します"
    bl_options = {'REGISTER', 'UNDO'}

    base_bone: bpy.props.StringProperty(name="ベースボーン")
    scale: bpy.props.FloatProperty(name="倍率", default=5.0, min=0.1, max=100.0, soft_min=0.1, soft_max=100.0, precision=1, step=10)
    items1 = [('1000', '1000', ''),
              ('2000', '2000', ''),
              ('2001', '2001', '')]
    model_version: bpy.props.EnumProperty(name="ファイルバージョン", items=items1, default='1000')
    show_diff: bpy.props.BoolProperty(name="差分のみ表示", default=True, description="差分のあるボーンのみ表示します")
    threshold: bpy.props.FloatProperty(name="差分しきい値", default=DEFAULT_THRESHOLD, min=0.0, max=1.0, soft_max=1.0, precision=6, description="この値を超える要素を自動でチェックします")
    show_threshold_details: bpy.props.BoolProperty(name="差分しきい値の詳細", default=False, options={'HIDDEN'})
    items2 = [('0.001', '0.001', ''),
              ('0.0001', '0.0001', ''),
              ('0.00001', '0.00001', ''),
              ('0.000001', '0.000001', ''),
              ('0.0', '0.0', '')]
    threshold_preset: bpy.props.EnumProperty(items=items2, description="差分しきい値のプリセット値を選択します", default=str(DEFAULT_THRESHOLD))
    diff_items: bpy.props.CollectionProperty(type=CNV_PG_bone_data_diff_item)
    diff_items_all: bpy.props.CollectionProperty(type=CNV_PG_bone_data_diff_item, options={'HIDDEN'})
    active_diff_index: bpy.props.IntProperty(name="", default=-1, options={'HIDDEN'})
    single_bones: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup, options={'HIDDEN'})

    # 一時保持用データ
    _prev_show_diff = None
    _prev_scale = None
    _prev_threshold = None
    _prev_threshold_preset = None
    _new_bone_data_list = []
    _new_local_bone_data_list = []
    MAX_ROW = 10

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.type == 'ARMATURE'

    def invoke(self, context, event):
        arm_ob = context.active_object
        self.base_bone = arm_ob.data.get('BaseBone', '')
        self.model_version = str(arm_ob.data.get('ModelVersion', '1000'))
        self.scale = 1.0 / arm_ob.data.get('ImportScale', common.preferences().scale)
        self.single_bones.clear()
        for bone in arm_ob.data.bones:
            if bone.parent is None and len(bone.children) == 0:
                item = self.single_bones.add()
                item.name = bone.name
        # 初回差分計算を実行
        self._prev_scale = self.scale
        self._prev_threshold = self.threshold
        self._prev_threshold_preset = self.threshold_preset
        pre_mode = arm_ob.mode
        if pre_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
            self.recalculate_diff(context)
            bpy.ops.object.mode_set(mode=pre_mode)
        else:
            self.recalculate_diff(context)
        self.filter_diff()
        return context.window_manager.invoke_props_dialog(self, width=650)

    def draw(self, context):
        # UI 上で scale や threshold を変更したら再計算
        if self._prev_threshold_preset != self.threshold_preset:
            self._prev_threshold_preset = self.threshold_preset
            self.threshold = float(self.threshold_preset)
        if self._prev_scale != self.scale:
            self._prev_scale = self.scale
            self.recalculate_diff(context)
            self.filter_diff()
        if  (self._prev_threshold != self.threshold) or (self._prev_show_diff != self.show_diff):
            self._prev_threshold = self.threshold
            self._prev_show_diff = self.show_diff
            self.filter_diff()

        layout = self.layout

        # 設定エリア
        layout.prop_search(self, 'base_bone', self, 'single_bones', icon='BONE_DATA')
        layout.prop(self, 'model_version')
        layout.prop(self, 'scale')
        row = layout.row(align=True)
        row.prop(self, 'show_diff', icon='FILTER', toggle=True)
        row.prop(self, 'threshold')

        icon = 'TRIA_DOWN' if self.show_threshold_details else 'TRIA_LEFT'
        row.prop(self, 'show_threshold_details', text="", icon=icon, emboss=False)
        if self.show_threshold_details:
            box = layout.box()
            row = box.row(align=True)
            split = row.split(factor=0.25, align=True)
            col = split.column(align=True)
            col.label(text="差分しきい値プリセット")
            col = split.column(align=True)
            row = col.row(align=True)
            row.prop(self, 'threshold_preset', text="プリセット値", expand=True)
            col = box.column(align=True)
            desc = _("ボーン再計算では浮動小数ドリフトによる誤差が生じ、回転などは経路が多いほど末端ボーンに誤差が蓄積します。"
                     "これは誤差と見做す範囲を調整して更新不要なものを見定めるしきい値です。\n"
                     "0.0 にすると全て更新しますが実用上はそれでも問題ありません。この取り込み操作を何度も行う想定なら、"
                     "誤差が拡大しないよう最小限の更新にしておくとよいです。おすすめは 0.0001 です。")
            common.wrap_label(col, icon='LIGHT_DATA', width=640, text=desc)

        layout.separator()
        layout.label(text="更新差分確認テーブル (チェックを入れた要素のみ更新)")

        if len(self.diff_items) > self.MAX_ROW:
            split_factor1 = 0.465
            split_factor2 = 0.93
        else:
            split_factor1 = 0.48
            split_factor2 = 0.98
        # テーブルヘッダー
        box = layout.box()
        split = box.split(factor=split_factor1, align=True)
        col1 = split.column()
        row = col1.row(align=True)
        row.label(text="Bone")
        row.label(text="Parent Bone")
        col2 = split.column()
        split = col2.split(factor=split_factor2, align=True)
        col3 = split.column()
        row = col3.row(align=True)
        row.label(text=_("Location") + ' (BD)')
        row.label(text=_("Rotation") + ' (BD)')
        row.label(text=_("Scale") + ' (BD)')
        row.label(text=_("Matrix") + ' (LBD)')

        if len(self.diff_items) == 0:
            box.label(text="差分はありません", icon='INFO')
        else:
            layout.template_list('CNV_UL_bone_data_diff_list', '', self, 'diff_items', self, 'active_diff_index', rows=self.MAX_ROW)

    def execute(self, context):
        if len(self.diff_items) == 0:
            self.report({'INFO'}, "差分がないので更新しませんでした")
            return {'FINISHED'}
        is_update = False
        for item in self.diff_items:
            if item.mode == 'UPDATE' and (item.upd_loc or item.upd_rot or item.upd_scl or item.upd_parent or item.upd_local):
                is_update = True
            elif item.mode in ['INSERT', 'DELETE'] and item.approved:
                is_update = True
        if not is_update:
            self.report({'INFO'}, "更新対象がないので更新しませんでした")
            return {'FINISHED'}

        arm_ob = context.active_object

        # 既存プロパティデータを取得
        from .model_export import CNV_OT_export_cm3d2_model as export_model
        old_bone_data = export_model.bone_data_parser(export_model.indexed_data_generator(arm_ob.data, prefix='BoneData:'))
        old_local_bone_data = export_model.local_bone_data_parser(export_model.indexed_data_generator(arm_ob.data, prefix='LocalBoneData:'))

        # チェック状態のマップを作成
        diff_map = {item.bone_name: item for item in self.diff_items}

        update_map = {}
        for name, item in diff_map.items():
            if item.mode != 'UPDATE':
                continue
            fields = set()
            if item.upd_loc:
                fields.add('co')
            if item.upd_rot:
                fields.add('rot')
            if item.upd_scl:
                fields.add('scl')
            if item.upd_parent:
                fields.add('parent_name')
            update_map[name] = fields
        deleted_names = {name for name, item in diff_map.items() if item.mode == 'DELETE' and item.approved}
        inserted_names = {name for name, item in diff_map.items() if item.mode == 'INSERT' and item.approved}

        final_bone_data = merge_bone_data_with_parent_names(
            old_bone_data, self._new_bone_data_list,
            update_map=update_map, deleted_names=deleted_names,
            inserted_names=inserted_names)
        final_local_bone_data = merge_local_bone_data(
            old_local_bone_data, self._new_local_bone_data_list, self.threshold,
            update_names={name for name, item in diff_map.items() if item.mode == 'UPDATE' and item.upd_local},
            deleted_names=deleted_names, inserted_names=inserted_names)

        # 最終データをカスタムプロパティに書き戻し
        self.update_armature_bone_data_properties(arm_ob.data, final_bone_data, final_local_bone_data)

        self.report({'INFO'}, "BoneDataを更新しました")
        return {'FINISHED'}

    def recalculate_diff(self, context):
        """既存データと新解析データの差分を計算"""
        from .model_export import CNV_OT_export_cm3d2_model as export_model

        arm_ob = context.active_object
        if not arm_ob:
            return

        old_bd = export_model.bone_data_parser(export_model.indexed_data_generator(arm_ob.data, prefix='BoneData:'))
        old_lbd = export_model.local_bone_data_parser(export_model.indexed_data_generator(arm_ob.data, prefix='LocalBoneData:'))

        old_bd_by_name = {d['name']: d for d in old_bd}
        old_lbd_by_name = {d['name']: d for d in old_lbd}
        old_parents = parent_name_map(old_bd)

        self._new_bone_data_list = export_model.armature_bone_data_parser(context, arm_ob, self.scale, True)
        self._new_local_bone_data_list = export_model.armature_local_bone_data_parser(arm_ob, self.scale, True)

        new_bd_by_name = {d['name']: d for d in self._new_bone_data_list}
        new_lbd_by_name = {d['name']: d for d in self._new_local_bone_data_list}
        new_parents = parent_name_map(self._new_bone_data_list)

        all_bone_names = list(dict.fromkeys(
            list(old_bd_by_name.keys()) +
            list(old_lbd_by_name.keys()) +
            [d['name'] for d in self._new_bone_data_list] +
            [d['name'] for d in self._new_local_bone_data_list]
        ))

        # しきい値関係なく全差分アイテムを記録
        self.diff_items_all.clear()
        for name in all_bone_names:
            item = self.diff_items_all.add()
            item.bone_name = name

            # BoneData 差分
            if name in new_bd_by_name:
                item.parent_name = new_parents.get(name, '')
                if name in old_bd_by_name:
                    item.diff_loc, item.diff_rot, item.diff_scl = calc_bone_data_diff(old_bd_by_name[name], new_bd_by_name[name])
                    item.diff_parent = item.parent_name != old_parents.get(name, '')
                else:
                    item.mode = 'INSERT'
            else:
                item.parent_name = old_parents.get(name, '')
                item.mode = 'DELETE'

            # LocalBoneData 差分
            if name in new_lbd_by_name:
                if name in old_lbd_by_name:
                    item.diff_local = calc_local_bone_data_diff(old_lbd_by_name[name], new_lbd_by_name[name])

    def filter_diff(self):
        """しきい値判定した結果アイテムリストを作る"""
        self.diff_items.clear()
        for item in self.diff_items_all[:]:
            item.upd_loc = item.diff_loc >= self.threshold
            item.upd_rot = item.diff_rot >= self.threshold
            item.upd_scl = item.diff_scl >= self.threshold
            item.upd_local = item.diff_local >= self.threshold
            item.upd_parent = item.diff_parent
            has_update = any((item.upd_loc, item.upd_rot, item.upd_scl, item.upd_local, item.upd_parent))
            if not self.show_diff or item.mode != 'UPDATE' or has_update:
                add_item = self.diff_items.add()
                for k, v in item.items():
                    add_item[k] = v

    def update_armature_bone_data_properties(self, arm_data, bone_data, local_bone_data) -> None:
        """アーマチュアプロパティに反映"""
        for key in list(arm_data.keys()):
            if key.startswith('BoneData:') or key.startswith('LocalBoneData:'):
                del arm_data[key]

        for i, data in enumerate(bone_data):
            row = ','.join([data['name'], str(data['scl']), data['parent_name']])
            row += ',' + ' '.join(map(str, data['co']))
            row += ',' + ' '.join(map(str, data['rot']))
            if int(self.model_version) >= 2001:
                if 'scale' in data:
                    row += ',1,' + ' '.join(map(str, data['scale']))
                else:
                    row += ',0'
            arm_data['BoneData:' + str(i)] = row

        for i, data in enumerate(local_bone_data):
            arm_data['LocalBoneData:' + str(i)] = data['name'] + ',' + ' '.join(map(str, data['matrix']))

        arm_data['BaseBone'] = self.base_bone
        arm_data['ModelVersion'] = self.model_version
        arm_data['ImportScale'] = 1.0 / self.scale


@compat.BlRegister()
class CNV_OT_armature_rename_base_bone(bpy.types.Operator):
    bl_idname = 'armature.rename_base_bone'
    bl_label = "ベースボーン名変更"
    bl_description = "BoneDataとアーマチュアのベースボーン名を変更します"
    bl_options = {'REGISTER', 'UNDO'}

    base_bone: bpy.props.StringProperty(name="ベースボーン名", default="")

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.type == 'ARMATURE'

    def invoke(self, context, event):
        arm_ob = context.active_object
        self.base_bone = arm_ob.data.get('BaseBone', '')
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        self.layout.prop(self, 'base_bone')

    def execute(self, context):
        arm_ob = context.active_object
        old_base_bone = arm_ob.data.get('BaseBone')
        arm_bone = arm_ob.data.bones.get(old_base_bone)
        arm_bone.name = self.base_bone
        arm_ob.data['BaseBone'] = self.base_bone
        for prop, value in arm_ob.data.items():
            if prop.startswith('BoneData:'):
                bone_data = value.split(',')
                is_dirty = False
                if len(bone_data) > 0 and bone_data[0] == old_base_bone:
                    bone_data[0] = self.base_bone
                    is_dirty = True
                elif len(bone_data) > 2 and bone_data[2] == old_base_bone:
                    bone_data[2] = self.base_bone
                    is_dirty = True
                if is_dirty:
                    arm_ob.data[prop] = ','.join(bone_data)
            elif prop.startswith('LocalBoneData:'):
                local_bone_data = value.split(',')
                if len(local_bone_data) > 0 and local_bone_data[0] == old_base_bone:
                    local_bone_data[0] = self.base_bone
                    arm_ob.data[prop] = ','.join(local_bone_data)
        self.report({'INFO'}, "ベースボーン名を変更しました")
        return {'FINISHED'}


"""
- - - - - - For Twist Bones - - - - - - 
"""
@compat.BlRegister()
class CNV_OT_add_cm3d2_twist_bones(bpy.types.Operator):
    bl_idname      = 'object.add_cm3d2_twist_bones'
    bl_label       = "Add CM3D2 Twist Bones"
    bl_description = "Adds drivers to armature to automatically set twist-bone positions."
    bl_options     = {'REGISTER', 'UNDO'}

    scale: bpy.props.FloatProperty(name="Scale", default=5, min=0.1, max=100, soft_min=0.1, soft_max=100, step=100, precision=1, description="The amount by which the mesh is scaled when imported. Recommended that you use the same when at the time of export.")

    #is_fix_thigh: bpy.props.BoolProperty(name="Fix Thigh", default=False, description="Fix twist bone values for the thighs in motor-cycle pose")
    #is_drive_shape_keys: bpy.props.BoolProperty(name="Drive Shape Keys", default=True, description="Connect sliders to mesh children's shape keys")
    
    fDegPer  = 1.1
    fDegPer1 = 0.2 
    fRota    = 0.5 
                                            
    @classmethod
    def poll(cls, context):
        ob = context.object
        if ob:
            arm = ob.data
        else:
            arm = None
        has_arm  = arm and isinstance(arm, bpy.types.Armature) and ('Bip01' in arm.bones)
        can_edit = (ob and ob.data == arm) or (arm and arm.is_editmode)
        return has_arm and can_edit

    def invoke(self, context, event):
        self.scale = common.preferences().scale
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'scale'              )
        #self.layout.prop(self, 'is_fix_thigh'       )
        #self.layout.prop(self, 'is_drive_shape_keys')

    def getPoseBone(self, ob, boneName, flip=False):
        side = 'R' if flip else 'L'
        
        poseBoneList = ob.pose.bones
        poseBone = poseBoneList.get(boneName.replace('?',side)) or poseBoneList.get(boneName.replace('?','*')+'.'+side)
        
        if not poseBone:
            print("WARNING: Could not find bone \""+boneName+"\"")
            return

        return poseBone

    def driveShapeKey(self, shapekey, data, prop, expression, set_min=None, set_max=None):
        if not shapekey:
            return
        driver = shapekey.driver_add('value').driver
        driver.type = 'SCRIPTED'

        driver_var = driver.variables.new() if len(driver.variables) < 1 else driver.variables[0]
        driver_var.type = 'SINGLE_PROP'
        driver_var.name = prop

        driver_target = driver_var.targets[0]
        driver_target.id_type = 'OBJECT'
        driver_target.id = data.id_data
        driver_target.data_path = data.path_from_id(prop)

        driver.expression = expression

        if set_min:
            shapekey.slider_min = set_min
        if set_max:
            shapekey.slider_max = set_max

    def driveTwistBone(self, ob, boneName, flip=False, prop='rotation_euler', axes=(1,2,0), expression=("", "", ""), infulencers=()):
        bone = self.getPoseBone(ob, boneName, flip=flip)
        if not bone:
            return
        if 'euler' in prop:
            bone.rotation_mode = 'XYZ'

        args = []
        for name in infulencers:
            if type(infulencers) == str:
                name = infulencers
            arg_bone = self.getPoseBone(ob, name, flip=flip)
            if arg_bone:
                args.append(arg_bone.name)
            else:
                args.append(name)
            if type(infulencers) == str:
                break

        for i, index in enumerate(axes):
            driver = bone.driver_add(prop, index).driver
            driver.type = 'SCRIPTED'
            driver.use_self = True
            if type(expression) == str:
                expr = expression
            else:
                expr = expression[i]
            driver.expression = expr.format(*args, axis=['x','y','z'][index], index=index, i=i)

    def constrainTwistBone(self, ob, boneName, targetName="", flip='BOTH', type='COPY_ROTATION', space=None, map=None, **kwargs):
        if flip == 'BOTH':
            const_l = self.constrainTwistBone(ob, boneName, targetName, flip=False, type=type, space=space, map=map, **kwargs)
            const_r = self.constrainTwistBone(ob, boneName, targetName, flip=True , type=type, space=space, map=map, **kwargs)
            return const_l, const_r

        bone   = self.getPoseBone(ob, boneName  , flip=flip)
        target = self.getPoseBone(ob, targetName, flip=flip)
        if not bone or (not target and targetName):
            return None

        const = bone.constraints.new(type)
        if target:
            const.target = ob
            const.subtarget = target.name
        if space:
            const.target_space = space
            const.owner_space  = space
        if map:
            const.map_from = map
            const.map_to   = map
        for key, val in kwargs.items():
            try:
                setattr(const, key, val)
            except Exception as e:
                # TODO : Properly handle drivers in legacy version
                self.report(type={'ERROR'}, message=e.args[0])

        return const

    def execute(self, context):
        ob = context.object
        arm = ob.data
        pre_mode = ob.mode
        if pre_mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')

        # TODO : Fix shoulder constraints
        # AutoTwist() ... Shoulder : 'TBody.cs' line 2775
        self.constrainTwistBone(ob, 'Uppertwist_?', 'Bip01 ? UpperArm',
            type  = 'TRANSFORM'                 ,
            space = 'LOCAL'                     ,
            map   = 'ROTATION'                  ,
            use_motion_extrapolate = True       ,
            from_rotation_mode = 'SWING_TWIST_Y',
            mix_mode_rot       = 'REPLACE'      ,
            from_max_y_rot =  1                 ,
            to_max_y_rot   = -self.fDegPer
        )
        self.constrainTwistBone(ob, 'Uppertwist1_?', 'Bip01 ? UpperArm', 
            type  = 'TRANSFORM'                 ,
            space = 'LOCAL'                     ,
            map   = 'ROTATION'                  ,
            use_motion_extrapolate = True       ,
            from_rotation_mode = 'SWING_TWIST_Y',
            mix_mode_rot       = 'REPLACE'      ,
            from_max_y_rot = 1                  ,
            to_max_y_rot   = 1                  ,
            influence      = self.fDegPer1
        )
        self.constrainTwistBone(ob, 'Kata_?', 'Bip01 ? UpperArm', 
            space = 'WORLD',
            influence = self.fRota
        )

        # AutoTwist() ... Wrist : 'TBody.cs' line 2793
        self.constrainTwistBone(ob, 'Foretwist_?', 'Bip01 ? Hand',
            type  = 'TRANSFORM'                 ,
            space = 'LOCAL'                     ,
            map   = 'ROTATION'                  ,
            use_motion_extrapolate = True       ,
            from_rotation_mode = 'SWING_TWIST_Y',
            mix_mode_rot       = 'REPLACE'      ,
            from_max_y_rot = 1                  ,
            to_max_y_rot   = 1
        )
        self.constrainTwistBone(ob, 'Foretwist1_?',
            type  = 'LIMIT_ROTATION',
            space = 'LOCAL'         ,
            use_limit_x = True      ,
            use_limit_y = True      ,
            use_limit_z = True      ,
        )
        self.constrainTwistBone(ob, 'Foretwist1_?', 'Bip01 ? Hand', 
            type  = 'TRANSFORM'                 ,
            space = 'LOCAL'                     ,
            map   = 'ROTATION'                  ,
            use_motion_extrapolate = True       ,
            from_rotation_mode = 'SWING_TWIST_Y',
            mix_mode_rot       = 'REPLACE'      ,
            from_max_y_rot = 1                  ,
            to_max_y_rot   = 1                  ,
            influence      = 0.5
        )

        # TODO : Fix thigh constraints
        # AutoTwist() ... Thigh : 'TBody.cs' line 2813
        self.constrainTwistBone(ob, 'momotwist_?', 'Bip01 ? Thigh',
            type  = 'TRANSFORM'                 ,
            space = 'LOCAL'                     ,
            map   = 'ROTATION'                  ,
            use_motion_extrapolate = True       ,
            from_rotation_mode = 'SWING_TWIST_Y',
            mix_mode_rot       = 'REPLACE'      ,
            from_max_y_rot =  1                 ,
            to_max_y_rot   = -self.fDegPer
        )
        self.constrainTwistBone(ob, 'momotwist2_?', 'Bip01 ? Thigh',
            type  = 'TRANSFORM'                 ,
            space = 'LOCAL'                     ,
            map   = 'ROTATION'                  ,
            use_motion_extrapolate = True       ,
            from_rotation_mode = 'SWING_TWIST_Y',
            mix_mode_rot       = 'REPLACE'      ,
            from_max_y_rot = 1                  ,
            to_max_y_rot   = 1                  ,
            influence      = 0.7
        )


        # MoveMomoniku() : 'TBody.cs' line 2841
        self.driveTwistBone(ob, 'momoniku_?', flip=False, expression=("", "", 'min(0,max(-8, self.id_data.pose.bones["{0}"].matrix.col[2].xyz.dot( (0,0,-1) ) *  10 * (pi/180) ))'), infulencers=('Bip01 ? Thigh'))
        self.driveTwistBone(ob, 'momoniku_?', flip=True , expression=("", "", 'min(8,max( 0, self.id_data.pose.bones["{0}"].matrix.col[2].xyz.dot( (0,0,-1) ) * -10 * (pi/180) ))'), infulencers=('Bip01 ? Thigh'))
        self.constrainTwistBone(ob, 'Hip_?',
            type  = 'LIMIT_ROTATION',
            space = 'LOCAL'         ,
            use_limit_x = True      ,
            use_limit_y = True      ,
            use_limit_z = True      ,
        )
        self.constrainTwistBone(ob, 'Hip_?', 'Bip01 ? Thigh', 
            space = 'LOCAL_WITH_PARENT', 
            influence = 0.67
        )
        
        

        bpy.ops.object.mode_set(mode=pre_mode)
        
        return {'FINISHED'}

'''
    public void AutoTwist()
	{
		if (this.boAutoTwistShoulderL && this.Uppertwist_L != null)
		{
			Quaternion localRotation = this.UpperArmL.localRotation;
			float x = (Quaternion.Inverse(this.quaUpperArmL) * localRotation).eulerAngles.x;
			this.Uppertwist_L.localRotation = Quaternion.Euler(-0.0174532924f * this.DegPer(x, this.fDegPer), 0f, 0f);
			this.Uppertwist1_L.localRotation = Quaternion.Euler(-0.0174532924f * this.DegPer(x, this.fDegPer1), 0f, 0f);
			this.Kata_L.localRotation = this.quaKata_L;
			this.Kata_L.rotation = Quaternion.Slerp(this.Kata_L.rotation, this.UpperArmL.rotation, this.fRota);
		}
		if (this.boAutoTwistShoulderR && this.Uppertwist_R != null)
		{
			Quaternion localRotation2 = this.UpperArmR.localRotation;
			float x2 = (Quaternion.Inverse(this.quaUpperArmR) * localRotation2).eulerAngles.x;
			this.Uppertwist_R.localRotation = Quaternion.Euler(-0.0174532924f * this.DegPer(x2, this.fDegPer), 0f, 0f);
			this.Uppertwist1_R.localRotation = Quaternion.Euler(-0.0174532924f * this.DegPer(x2, 0.2f), 0f, 0f);
			this.Kata_R.localRotation = this.quaKata_R;
			this.Kata_R.rotation = Quaternion.Slerp(this.Kata_R.rotation, this.Uppertwist_R.rotation, 0.5f);
		}
		if (this.boAutoTwistWristL && this.Foretwist_L != null)
		{
			Vector3 fromDirection = this.HandL_MR.localRotation * Vector3.up;
			fromDirection.Normalize();
			Vector3 toDirection = this.HandL.localRotation * Vector3.up;
			toDirection.Normalize();
			this.m_fAngleHandL = this.AxisAngleOnAxisPlane(fromDirection, toDirection, new Vector3(1f, 0f, 0f)) * -1f;
			this.Foretwist_L.localRotation = Quaternion.AngleAxis(this.m_fAngleHandL, this.Foretwist_L_MR.localRotation * Vector3.left) * this.Foretwist_L_MR.localRotation;
			this.Foretwist1_L.localRotation = Quaternion.AngleAxis(this.m_fAngleHandL * 0.5f, this.Foretwist1_L_MR.localRotation * Vector3.left) * this.Foretwist1_L_MR.localRotation;
		}
		if (this.boAutoTwistWristR && this.Foretwist_R != null)
		{
			Vector3 fromDirection2 = this.HandR_MR.localRotation * Vector3.up;
			fromDirection2.Normalize();
			Vector3 toDirection2 = this.HandR.localRotation * Vector3.up;
			toDirection2.Normalize();
			float num = this.AxisAngleOnAxisPlane(fromDirection2, toDirection2, new Vector3(1f, 0f, 0f)) * -1f;
			this.Foretwist_R.localRotation = Quaternion.AngleAxis(num, this.Foretwist_R_MR.localRotation * Vector3.left) * this.Foretwist_R_MR.localRotation;
			this.Foretwist1_R.localRotation = Quaternion.AngleAxis(num * 0.5f, this.Foretwist1_R_MR.localRotation * Vector3.left) * this.Foretwist1_R_MR.localRotation;
		}
		if (this.boAutoTwistThighL && this.momotwist_L != null)
		{
			Quaternion quaternion = this.Thigh_L.localRotation;
			quaternion = Quaternion.Inverse(this.quaThigh_L) * quaternion;
			Vector3 vector = quaternion * Vector3.forward;
			float num2 = quaternion.eulerAngles.x;
			if (vector.z < 0f)
			{
				num2 = 180f - num2;
			}
			this.momotwist_L.localRotation = Quaternion.Euler(-0.0174532924f * this.DegPer(num2, this.fDegPer), 0f, 0f) * this.q_momotwist_L;
			this.momotwist2_L.localRotation = Quaternion.Euler(0.0174532924f * this.DegPer(num2, 0.7f), 0f, 0f) * this.q_momotwist2_L;
		}
		if (this.boAutoTwistThighR & this.momotwist_R != null)
		{
			Quaternion quaternion2 = this.Thigh_R.localRotation;
			quaternion2 = Quaternion.Inverse(this.quaThigh_R) * quaternion2;
			Vector3 vector2 = quaternion2 * Vector3.forward;
			float num3 = quaternion2.eulerAngles.x;
			if (vector2.z < 0f)
			{
				num3 = 180f - num3;
			}
			this.momotwist_R.localRotation = Quaternion.Euler(-0.0174532924f * this.DegPer(num3, this.fDegPer), 0f, 0f) * this.q_momotwist_R;
			this.momotwist2_R.localRotation = Quaternion.Euler(0.0174532924f * this.DegPer(num3, 0.7f), 0f, 0f) * this.q_momotwist2_R;
		}
	}

	public void MoveMomoniku()
	{
		if (!TBody.boMoveMomoniku || this.momoniku_L == null || this.momoniku_R == null)
		{
			return;
		}
		float num = Mathf.Clamp(Vector3.Dot(Vector3.up, this.Thigh_L.up), 0f, 0.8f);
		float num2 = Mathf.Clamp(Vector3.Dot(Vector3.up, this.Thigh_R.up), 0f, 0.8f);
		this.momoniku_L.localRotation = this.momoniku_L_MR.localRotation;
		this.momoniku_R.localRotation = this.momoniku_R_MR.localRotation;
		this.momoniku_L.Rotate(0f, 0f, num * 10f);
		this.momoniku_R.Rotate(0f, 0f, -num2 * 10f);
		this.Hip_L.localRotation = Quaternion.Slerp(this.Hip_L_MR.localRotation, this.Thigh_L.localRotation, 0.67f);
		this.Hip_R.localRotation = Quaternion.Slerp(this.Hip_R_MR.localRotation, this.Thigh_R.localRotation, 0.67f);
	}
'''



"""
- - - - - - For Bone Sliders - - - - - - 
"""
def get_axis_index_vector(axis_index, size=3):
    vec = mathutils.Vector.Fill(size)
    vec[axis_index] = 1
    return vec

def get_axis_order_matrix(axis_order):
    size = len(axis_order)
    mat = mathutils.Matrix.Diagonal( [0] * size )
    for index, axis_index in enumerate(axis_order):
        mat[index][axis_index] = 1
    return mathutils.Matrix(mat)

def get_vector_axis_index(vec):
    length = len(vec)
    for axis_index, axis_value in enumerate(vec):
        if axis_index == length-1:
            return axis_index
        else:
            axis_value = abs(axis_value)
            largest = True
            for i in range(axis_index+1, length):
                if axis_value < abs(vec[i]):
                    largest = False
                    break
            if largest:
                return axis_index

def get_matrix_axis_order(mat):
    return [ get_vector_axis_index(row) for row in mat ]



@compat.BlRegister()
class CNV_PG_cm3d2_bone_morph(bpy.types.PropertyGroup):
    bl_idname = 'CNV_PG_cm3d2_bone_morph'

    scale: bpy.props.FloatProperty(name="Scale", default=5, min=0.1, max=100, soft_min=0.1, soft_max=100, step=100, precision=1, description="The amount by which the mesh is scaled when imported. Recommended that you use the same when at the time of export.")

    def __calcMeasurements(self, context):                                               
        num    =  1340                         +                   self.sintyou * 4    +      self.DouPer * (1 + self.sintyou * 0.005) + self.KubiScl * 0.5 + self.HeadY * 0.5
        num2   =    55 * self.RegFat           + 50              * self.sintyou * 0.5  + 50 * self.DouPer * 0.4
        num3   =    55 * self.RegMeet          + 50              * self.sintyou * 0.5  + 50 * self.DouPer * 0.4
        num4   =    10 * self.UdeScl   * 0.1                                                             
        num5   =     5 * self.ArmL             +  5              * self.sintyou * 1    +  5 * self.UdeScl * 0.5
        num6   =    70 * self.Hara             + 50              * self.sintyou * 0.7  + 50 * self.Hara   * self.west * 0.005
        num7   =    10 * self.MuneL    * 2                                                                           
        num8   =  num7 * self.MuneTare * 0.005                                                                       
        num9   =    20 * self.west     * 0.5   + 15 * self.west  * self.sintyou * 0.02 + 15 * self.DouPer * self.west * 0.01
        num10  =    10 * self.koshi            +  7 * self.koshi * self.sintyou * 0.04
        num11  =     4 * self.kata                        
        num13  =    70                         +      self.MuneL                * 0.31 +                    self.west * 0.02      
        
        num13 -=     5 * (self.MuneS / 100)                
        num12  = 38000 + num2 + num3 + num4 + num5 + num6 + num7 + num8 + num9 + num10 + num11
        
        self.private_height = num   /   10
        self.private_weight = num12 / 1000
        self.private_bust   = num13
        self.private_waist  = 40 + self.west  * 0.25 + self.Hara   * 0.35
        self.private_hip    = 65 + self.koshi * 0.3  + self.RegFat * 0.025 + self.RegMeet * 0.025
             
        if   num13 <   80:
            self.private_cup = 'A'
        elif num13 >= 110:
            self.private_cup = 'N'
        else:
            cup_sizes = ['B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M']
            self.private_cup = cup_sizes[int((num13 - 80) / 2.5)]

        self.private_height = int(self.private_height) * 0.01 / context.scene.unit_settings.scale_length
        self.private_weight = int(self.private_weight)        / context.scene.unit_settings.scale_length ** 3
        self.private_bust   = int(self.private_bust  ) * 0.01 / context.scene.unit_settings.scale_length
        self.private_waist  = int(self.private_waist ) * 0.01 / context.scene.unit_settings.scale_length
        self.private_hip    = int(self.private_hip   ) * 0.01 / context.scene.unit_settings.scale_length
        self.private_cup = "'" + self.private_cup + "'"

        return None

    def __calcMune(self, context):
        if self.BreastSize >= 0:
            self.MuneL = self.BreastSize
            self.MuneS = 0
        else:
            self.MuneL = 0
            self.MuneS = (self.BreastSize / -30) * 100
        self.__calcMuneTare(context)
        return None

    def __calcMuneTare(self, context):
        if self.MuneTare > self.MuneL:
            self.MuneTare = self.MuneL
        else:
            self.__calcMeasurements(context)

    HeadX:      bpy.props.FloatProperty(name='HeadX'     , description="Size of face (left to right)", default=  50, min=   0, max= 100, step=100, precision=0)
    HeadY:      bpy.props.FloatProperty(name='HeadY'     , description="Size of face (up and down)"  , default=  50, min=   0, max= 100, step=100, precision=0, update=__calcMeasurements)
    DouPer:     bpy.props.FloatProperty(name='DouPer'    , description="Leg length"                  , default=  50, min=-100, max= 500, step=100, precision=0, update=__calcMeasurements)
    sintyou:    bpy.props.FloatProperty(name='sintyou'   , description="Height"                      , default=  50, min=-300, max= 100, step=100, precision=0, update=__calcMeasurements)
    BreastSize: bpy.props.FloatProperty(name='BreastSize', description="Breast size"                 , default=  50, min= -30, max= 195, step=100, precision=0, update=__calcMune        )
    MuneTare:   bpy.props.FloatProperty(name='MuneTare'  , description="Breast sagging level"        , default=  50, min=   0, max= 195, step=100, precision=0, update=__calcMuneTare    )
    MuneUpDown: bpy.props.FloatProperty(name='MuneUpDown', description="Position of the nipple"      , default=  10, min= -50, max= 300, step=100, precision=0)
    MuneYori:   bpy.props.FloatProperty(name='MuneYori'  , description="Direction of breast"         , default=  40, min= -50, max= 200, step=100, precision=0)
    west:       bpy.props.FloatProperty(name='west'      , description="Waist"                       , default=  50, min= -30, max= 100, step=100, precision=0, update=__calcMeasurements)
    Hara:       bpy.props.FloatProperty(name='Hara'      , description="Belly"                       , default=  20, min=   0, max= 200, step=100, precision=0, update=__calcMeasurements)
    kata:       bpy.props.FloatProperty(name='kata'      , description="Shoulder width"              , default=  50, min=-400, max= 100, step=100, precision=0, update=__calcMeasurements)
    ArmL:       bpy.props.FloatProperty(name='ArmL'      , description="Size of arms"                , default=  20, min=   0, max= 100, step=100, precision=0, update=__calcMeasurements)
    UdeScl:     bpy.props.FloatProperty(name='UdeScl'    , description="Length of arms"              , default=  50, min=   0, max= 100, step=100, precision=0, update=__calcMeasurements)
    KubiScl:    bpy.props.FloatProperty(name='KubiScl'   , description="Length of neck"              , default=  50, min=   0, max= 200, step=100, precision=0, update=__calcMeasurements)
    koshi:      bpy.props.FloatProperty(name='koshi'     , description="Hip"                         , default=  50, min=-160, max= 200, step=100, precision=0, update=__calcMeasurements)
    RegFat:     bpy.props.FloatProperty(name='RegFat'    , description="Leg thickness"               , default=  40, min=   0, max= 100, step=100, precision=0, update=__calcMeasurements)
    RegMeet:    bpy.props.FloatProperty(name='RegMeet'   , description="Leg definition"              , default=  40, min=   0, max= 100, step=100, precision=0, update=__calcMeasurements)
    MuneL:      bpy.props.FloatProperty(name='MuneL'     , description="munel shapekey value"        , default=  50, min=   0)
    MuneS:      bpy.props.FloatProperty(name='MuneS'     , description="munes shapekey value"        , default=   0, min=   0)

    # 初回計算用フラグ
    is_initialized: bpy.props.BoolProperty(name='is_initialized', options={'HIDDEN'}, default=False)

    def initialize(self):
        self.is_initialized = True
        self.__calcMeasurements(bpy.context)

    def __measurementSetter(self, value):
        self.__calcMeasurements(bpy.context)
        return None
    
    def __newGetter(attr):
        def __getter(self):
            return getattr(self, attr)
        return __getter

    private_height: bpy.props.FloatProperty (name='private_height', options={'HIDDEN'})
    private_weight: bpy.props.FloatProperty (name='private_weight', options={'HIDDEN'})
    private_bust:   bpy.props.FloatProperty (name='private_bust'  , options={'HIDDEN'})
    private_waist:  bpy.props.FloatProperty (name='private_waist' , options={'HIDDEN'})
    private_hip:    bpy.props.FloatProperty (name='private_hip'   , options={'HIDDEN'})
    private_cup:    bpy.props.StringProperty(name='private_cup'   , options={'HIDDEN'})

    height: bpy.props.FloatProperty (name="Height", precision=3, unit='LENGTH', set=__measurementSetter, get=__newGetter('private_height'))
    weight: bpy.props.FloatProperty (name="Weight", precision=3, unit='MASS'  , set=__measurementSetter, get=__newGetter('private_weight'))
    bust:   bpy.props.FloatProperty (name="Bust"  , precision=3, unit='LENGTH', set=__measurementSetter, get=__newGetter('private_bust'  ))
    waist:  bpy.props.FloatProperty (name="Waist" , precision=3, unit='LENGTH', set=__measurementSetter, get=__newGetter('private_waist' ))
    hip:    bpy.props.FloatProperty (name="Hip"   , precision=3, unit='LENGTH', set=__measurementSetter, get=__newGetter('private_hip'   ))
    cup:    bpy.props.StringProperty(name="Cup"   ,                             set=__measurementSetter, get=__newGetter('private_cup'   ))
                                                     
    def GetArmature(self, override=None):
        override = override or bpy.context.copy()
        ob = self.id_data
        override.update({
            'selected_objects'         : {ob},
            'selected_editable_objects': {ob},
            'editable_bones'           : {}  ,
            'selected_bones'           : {}  ,
            'selected_editable_bones'  : {}  ,
            'active_object'            : ob  ,
            'edit_object'              : ob  ,
        })
        return self.id_data, override

        #armature = override['object']
        #if not armature or armature.type != 'ARMATURE':
        #    print("ERROR: Active object is not an armature")
        #    return None, None
        #
        #for area in bpy.context.screen.areas:
        #    #print(area,area.type)
        #    if area.type == 'OUTLINER':
        #        override.update({
        #            'blend_data': None,
        #            'area': area,
        #            'scene': bpy.context.scene,
        #            'screen': None,
        #            'space_data': area.spaces[0],
        #            'window': None,
        #            'window_manager': None,
        #            'object': armature,
        #            'active_object': armature,
        #            'edit_object': armature,
        #        })
        #        break
        #
        #if override['area'].type != 'OUTLINER':
        #    print("ERROR: There is no 3D View Present in the current workspace")
        #    return None, None
        #
        #if False:
        #    print('\n')
        #    for k,v in override.items():
        #        print(k)
        #    print('\n')
        #return armature, override

    def GetPoseBone(self, boneName, flip=False, override=None):
        context = bpy.context
        
        side = 'L' if flip else 'R'
        armature, override = self.GetArmature()
        if not armature:
            return
        
        poseBoneList = armature.pose.bones
        poseBone = poseBoneList.get(boneName.replace('?',side)) or poseBoneList.get(boneName.replace('?','*')+'.'+side)

        # check if _SCL_ bone needs to be created
        if not poseBone and '_SCL_' in boneName:
            boneList = armature.data.edit_bones
            bpy.ops.object.mode_set(mode='EDIT')
            print("Make Scale Bone: "+boneName)
            copyBone = boneList.get(boneName.replace('_SCL_','').replace('?',side)) or boneList.get(boneName.replace('_SCL_','').replace('?','*')+'.'+side)
            if copyBone:
                #bpy.ops.armature.select_all(override, action='DESELECT')
                #for v in context.selected_bones:
                #    v.select = False
                #    v.select_head = False
                #    v.select_tail = False
                #copyBone.select = True
                #copyBone.select_head = True
                #copyBone.select_tail = True
                #boneList.active = copyBone
                #bpy.ops.armature.duplicate(override)
                new_name = copyBone.basename+'_SCL_' + ('.'+side if ('.'+side) in copyBone.name else '')
                bone = armature.data.edit_bones.new(new_name)
                bone.parent = copyBone
                bone.head = copyBone.head
                bone.tail = copyBone.tail
                bone.roll = copyBone.roll
                bone.show_wire = True
                bone.use_deform = True
                copyBone['cm3d2_scl_bone'] = False
                bone['cm3d2_scl_bone'] = False
                
                # rename vertex groups
                for child in armature.children:
                    if child.type == 'MESH':
                        vertexGroup = child.vertex_groups.get(copyBone.name)
                        if vertexGroup:
                            vertexGroup.name = bone.name
        
        bpy.ops.object.mode_set(mode='POSE')
        poseBone = poseBone or poseBoneList.get(boneName.replace('?', side)) or poseBoneList.get(boneName.replace('?','*')+'.'+side)
        
        if not poseBone:
            print("WARNING: Could not find bone \""+boneName+'\"')
            return

        return poseBone

    def GetDrivers(self, data_path, prop):
        id_data = self.id_data
        drivers = [None, None, None]
        if id_data and id_data.animation_data:
            for f in id_data.animation_data.drivers:
                fName = f.data_path
                #print("check",fName, "for", '["%s"].%s' % (data_path, prop))
                if '["{path}"].{attr}'.format(path=data_path, attr=prop) in fName:
                    #print("VALID!")
                    drivers[f.array_index] = f.driver
        return drivers


    def AddPositionDriver(self, prop, bone, drivers, axis, value, default=50):
        value = value-1
        if value == 0:
            return
        
        driver = drivers[axis]
        prefix = ' + '
        
        if not driver:
            driver = bone.driver_add('location', axis).driver
            driver.type = 'SCRIPTED'
            
            parent_length_var = driver.variables.new()
            parent_length_var.type = 'SINGLE_PROP'
            parent_length_var.name = 'parent_length'
            
            driver_target = parent_length_var.targets[0]
            driver_target.id_type = 'ARMATURE'
            driver_target.id = bone.parent.bone.id_data
            driver_target.data_path = bone.parent.bone.path_from_id('length')

            head_var = driver.variables.new()
            head_var.type = 'SINGLE_PROP'
            head_var.name = 'head'

            driver_target = head_var.targets[0]
            driver_target.id_type = 'OBJECT'
            driver_target.id = bone.id_data
            driver_target.data_path = bone.path_from_id('head') + f'[{axis}]'
            
            if axis == 1: # if y axis, include parent bone's length, because head coords are based on parent's tail
                driver.expression = '(parent_length+head)_'
            else:
                driver.expression = 'head_'
            prefix = ' * ('
            
            #driver.expression = '-{direction} + {direction}', direction=rest_value

        driver_var = driver.variables.get(prop)
        if not driver_var:
            driver_var = driver.variables.new()
            driver_var.type = 'SINGLE_PROP'
            driver_var.name = prop

            driver_target = driver_var.targets[0]
            driver_target.id_type = 'OBJECT'
            driver_target.id = bone.id_data
            driver_target.data_path = bone.id_data.cm3d2_bone_morph.path_from_id(prop)
        
        # if prop isn't already a factor
        if not prop in driver.expression:
            driver.expression = driver.expression[:-1] + prefix + f'({prop}-{default})*{value/(100-default)})'
            
        return

    def AddScaleDriver(self, prop, bone, drivers, axis, value, default=50):
        value = value-1
        if value == 0:
            return
        
        driver = drivers[axis]
        
        # if just created
        if not driver:
            driver = bone.driver_add('scale', axis).driver
            driver.type = 'SCRIPTED'
            driver.expression = '(1)'

        driver_var = driver.variables.get(prop) 
        if not driver_var:
            driver_var = driver.variables.new()
            driver_var.type = 'SINGLE_PROP'
            driver_var.name = prop

            driver_target = driver_var.targets[0]
            driver_target.id_type = 'OBJECT'
            driver_target.id = bone.id_data
            driver_target.data_path = bone.id_data.cm3d2_bone_morph.path_from_id(prop)
        
        # if prop isn't already a factor
        if not prop in driver.expression:
            driver.expression = driver.expression[:-1] + f' + ({prop}-{default})*{value/(100-default)})'
 
        return

    def SetPosition(self, prop, boneName, x, y, z, default=50):
        # Check if object has this property
        #if not bpy.context.object.get(prop) or ONLY_FIX_SETTINGS:
        #    if ONLY_FIX_SETTINGS:
        #        return
        #x = (1-x)+1
        #y = (1-y)+1
        #z = (1-z)+1

        #loc.x, loc.y, loc.z = loc.z, -loc.x, loc.y
        #x, y, z = z, x, y

        vec = mathutils.Vector((x, y, z))
        vec = compat.convert_cm_to_bl_slider_space(vec)

        pose_bone = self.GetPoseBone(boneName)
        if pose_bone:                                                       
            #rest_pos = pose_bone.bone.head_local + (pose_bone.bone.head_local - pose_bone.bone.parent.head_local) 
            #rest_pos = compat.mul(pose_bone.bone.matrix_local.inverted(), rest_pos)
            #vec = mathutils.Vector((x, y, z))# * self.scale
            #if pose_bone.parent:
            #    vec = compat.convert_cm_to_bl_bone_space(vec)
            #    vec = compat.mul(pose_bone.parent.bone.matrix_local, vec)
            #else:
            #    vec = compat.convert_cm_to_bl_space(vec)
            #vec = compat.mul(pose_bone.bone.matrix_local.inverted(), vec)

            pose_bone.bone.use_local_location = False
            drivers = self.GetDrivers(pose_bone.name,'location')
                                                        
            self.AddPositionDriver(prop, pose_bone, drivers, 0, vec[0], default=default)
            self.AddPositionDriver(prop, pose_bone, drivers, 1, vec[1], default=default)
            self.AddPositionDriver(prop, pose_bone, drivers, 2, vec[2], default=default)
                                                                   
        # repeat for left side
        if '?' in boneName:
            pose_bone = self.GetPoseBone(boneName, flip=True)
            if pose_bone:
                #rest_pos = pose_bone.bone.head_local + pose_bone.bone.head
                #rest_pos = compat.mul(pose_bone.bone.matrix_local.inverted(), rest_pos)
                #vec = mathutils.Vector((x, y, z))# * self.scale
                #if pose_bone.parent:
                #    vec = compat.convert_cm_to_bl_bone_space(vec)
                #    vec = compat.mul(pose_bone.parent.bone.matrix_local, vec)
                #else:
                #    vec = compat.convert_cm_to_bl_space(vec)
                #vec = compat.mul(pose_bone.bone.matrix_local.inverted(), vec)
                
                pose_bone.bone.use_local_location = False
                drivers = self.GetDrivers(pose_bone.name,'location')

                vec[2] = (1-vec[2])+1 # mirror z axis
                
                self.AddPositionDriver(prop, pose_bone, drivers, 0, vec[0], default=default)
                self.AddPositionDriver(prop, pose_bone, drivers, 1, vec[1], default=default)
                self.AddPositionDriver(prop, pose_bone, drivers, 2, vec[2], default=default)
                                                                            
        return

    def SetScale(self, prop, boneName, x, y, z, default=50):
        # Check if object has this property
        #if not bpy.context.object.get(prop) or ONLY_FIX_SETTINGS:
        #    if ONLY_FIX_SETTINGS:
        #        return

        #x, y, z = z, abs(-x), y

        mat = mathutils.Matrix.Diagonal((x, y, z)).to_4x4()
        mat = compat.convert_cm_to_bl_bone_rotation(mat)
        x, y, z = -mat.to_scale()

        bone = self.GetPoseBone(boneName)
        if bone:
            drivers = self.GetDrivers(bone.name,'scale')
            
            self.AddScaleDriver(prop, bone, drivers, 0, x, default=default)
            self.AddScaleDriver(prop, bone, drivers, 1, y, default=default)
            self.AddScaleDriver(prop, bone, drivers, 2, z, default=default)
        
        # repeat for left side
        if '?' in boneName:
            bone = self.GetPoseBone(boneName, flip=True)
            if bone:
                drivers = self.GetDrivers(bone.name,'scale')
                
                self.AddScaleDriver(prop, bone, drivers, 0, x, default=default)
                self.AddScaleDriver(prop, bone, drivers, 1, y, default=default)
                self.AddScaleDriver(prop, bone, drivers, 2, z, default=default)
        
        return


@compat.BlRegister()
class CNV_PG_cm3d2_wide_slider(bpy.types.PropertyGroup):
    bl_idname = 'CNV_PG_cm3d2_wide_slider'

    scale: bpy.props.FloatProperty(name="Scale", default=5, min=0.1, max=100, soft_min=0.1, soft_max=100, step=100, precision=1, description="The amount by which the mesh is scaled when imported. Recommended that you use the same when at the time of export.")

    empty: bpy.props.EnumProperty(items=[('EMPTY','-',"This property never has a value")], name="Empty", description="This property never has a value")
    
    enable_all: bpy.props.BoolProperty(name="Enable All", description="Enable all sliders, even ones without a GUI in-game", default=False)

    HIPPOS:     bpy.props.FloatVectorProperty(name='HIPPOS'    , description="Hips Position"         , default=(0,0,0), min=-100, max= 200, precision=2, subtype='XYZ'        , unit='NONE')
    THIPOS:     bpy.props.FloatVectorProperty(name='THIPOS'    , description="Legs Position"         , default=(0,0,0), min=-100, max= 200, precision=2, subtype='XYZ'        , unit='NONE')
    MTWPOS:     bpy.props.FloatVectorProperty(name='MTWPOS'    , description="Thigh Position"        , default=(0,0,0), min=-1.0, max= 1.0, precision=2, subtype='XYZ'        , unit='NONE')
    MMNPOS:     bpy.props.FloatVectorProperty(name='MMNPOS'    , description="Rear Thigh Position"   , default=(0,0,0), min=-1.0, max= 1.0, precision=2, subtype='XYZ'        , unit='NONE')
    THI2POS:    bpy.props.FloatVectorProperty(name='THI2POS'   , description="Knee Position"         , default=(0,0,0), min=-100, max= 200, precision=2, subtype='XYZ'        , unit='NONE')
    SKTPOS:     bpy.props.FloatVectorProperty(name='SKTPOS'    , description="Skirt Position"        , default=(0,0,0), min=-1.0, max= 1.0, precision=2, subtype='XYZ'        , unit='NONE')
    SPIPOS:     bpy.props.FloatVectorProperty(name='SPIPOS'    , description="Lower Abdomen Position", default=(0,0,0), min=-1.0, max= 1.0, precision=2, subtype='XYZ'        , unit='NONE')
    S0APOS:     bpy.props.FloatVectorProperty(name='S0APOS'    , description="Upper Abdomen Position", default=(0,0,0), min=-1.0, max= 1.0, precision=2, subtype='XYZ'        , unit='NONE')
    S1POS:      bpy.props.FloatVectorProperty(name='S1POS'     , description="Lower Chest Position"  , default=(0,0,0), min=-1.0, max= 1.0, precision=2, subtype='XYZ'        , unit='NONE')
    S1APOS:     bpy.props.FloatVectorProperty(name='S1APOS'    , description="Upper Chest Position"  , default=(0,0,0), min=-1.0, max= 1.0, precision=2, subtype='XYZ'        , unit='NONE')
    MUNEPOS:    bpy.props.FloatVectorProperty(name='MUNEPOS'   , description="Breasts Position"      , default=(0,0,0), min=-1.0, max= 1.0, precision=2, subtype='XYZ'        , unit='NONE')
    MUNESUBPOS: bpy.props.FloatVectorProperty(name='MUNESUBPOS', description="Breasts Sub-Position"  , default=(0,0,0), min=-1.0, max= 1.0, precision=2, subtype='XYZ'        , unit='NONE')
    NECKPOS:    bpy.props.FloatVectorProperty(name='NECKPOS'   , description="Neck Position"         , default=(0,0,0), min=-1.0, max= 1.0, precision=2, subtype='XYZ'        , unit='NONE')
    CLVPOS:     bpy.props.FloatVectorProperty(name='CLVPOS'    , description="Clavicle Position"     , default=(0,0,0), min=-1.0, max= 1.0, precision=2, subtype='XYZ'        , unit='NONE')

    PELSCL:     bpy.props.FloatVectorProperty(name='PELSCL'    , description="Pelvis Scale"          , default=(1,1,1), min= 0.1, max= 2.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    HIPSCL:     bpy.props.FloatVectorProperty(name='HIPSCL'    , description="Hips Scale"            , default=(1,1,1), min= 0.1, max= 2.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    THISCL:     bpy.props.FloatVectorProperty(name='THISCL'    , description="Legs Scale"            , default=(1,1,1), min= 0.1, max= 2.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    MTWSCL:     bpy.props.FloatVectorProperty(name='MTWSCL'    , description="Thigh Scale"           , default=(1,1,1), min= 0.1, max= 2.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    MMNSCL:     bpy.props.FloatVectorProperty(name='MMNSCL'    , description="Rear Thigh Scale"      , default=(1,1,1), min= 0.1, max= 2.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    THISCL2:    bpy.props.FloatVectorProperty(name='THISCL2'   , description="Knee Scale"            , default=(1,1,1), min= 0.1, max= 2.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    CALFSCL:    bpy.props.FloatVectorProperty(name='CALFSCL'   , description="Calf Scale"            , default=(1,1,1), min= 0.1, max= 2.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    FOOTSCL:    bpy.props.FloatVectorProperty(name='FOOTSCL'   , description="Foot Scale"            , default=(1,1,1), min= 0.1, max= 2.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    SKTSCL:     bpy.props.FloatVectorProperty(name='SKTSCL'    , description="Skirt Scale"           , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    SPISCL:     bpy.props.FloatVectorProperty(name='SPISCL'    , description="Lower Abdomen Scale"   , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    S0ASCL:     bpy.props.FloatVectorProperty(name='S0ASCL'    , description="Upper Abdomen Scale"   , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    S1_SCL:     bpy.props.FloatVectorProperty(name='S1_SCL'    , description="Lower Chest Scale"     , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    S1ASCL:     bpy.props.FloatVectorProperty(name='S1ASCL'    , description="Upper Chest Scale"     , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    S1ABASESCL: bpy.props.FloatVectorProperty(name='S1ABASESCL', description="Upper Torso Scale"     , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    MUNESCL:    bpy.props.FloatVectorProperty(name='MUNESCL'   , description="Breasts Scale"         , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    MUNESUBSCL: bpy.props.FloatVectorProperty(name='MUNESUBSCL', description="Breasts Sub-Scale"     , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    NECKSCL:    bpy.props.FloatVectorProperty(name='NECKSCL'   , description="Neck Scale"            , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    CLVSCL:     bpy.props.FloatVectorProperty(name='CLVSCL'    , description="Clavicle Scale"        , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    KATASCL:    bpy.props.FloatVectorProperty(name='KATASCL'   , description="Shoulders Scale"       , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    UPARMSCL:   bpy.props.FloatVectorProperty(name='UPARMSCL'  , description="Upper Arm Scale"       , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    FARMSCL:    bpy.props.FloatVectorProperty(name='FARMSCL'   , description="Forearm Scale"         , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')
    HANDSCL:    bpy.props.FloatVectorProperty(name='HANDSCL'   , description="Hand Scale"            , default=(1,1,1), min= 0.1, max= 3.0, precision=2, subtype='XYZ_LENGTH' , unit='NONE')

    def GetArmature(self, override=None):
        return CNV_PG_cm3d2_bone_morph.GetArmature(self, override=override)
    
    def GetPoseBone(self, boneName, flip=False, override=None):
        return CNV_PG_cm3d2_bone_morph.GetPoseBone(self, boneName, flip=flip, override=override)

    def GetDrivers(self, data_path, prop):
        return CNV_PG_cm3d2_bone_morph.GetDrivers(self, data_path, prop)


    def AddPositionDriver(self, prop, index, bone, drivers, axis, value):
        if value == 0:
            return
              
        driver = drivers[axis]

        if not driver:
            driver = bone.driver_add('location',axis).driver
            driver.type = 'SCRIPTED'
            driver.expression = '0'

        prop_var = prop + f'_{index}_'
        driver_var = driver.variables.get(prop_var) 
        if not driver_var:
            driver_var = driver.variables.new()
            driver_var.type = 'SINGLE_PROP'
            driver_var.name = prop_var

            driver_target = driver_var.targets[0]
            driver_target.id_type = 'OBJECT'
            driver_target.id = bone.id_data
            driver_target.data_path = bone.id_data.cm3d2_wide_slider.path_from_id(prop) + f'[{index}]'

              
        # if prop isn't already a factor
        if not prop_var in driver.expression:
            driver.expression = driver.expression + f' + {prop_var}*{value}'
                
        return
              
              
    def AddScaleDriver(self, prop, index, bone, drivers, axis):
        if index < 0:
            return
              
        driver = drivers[axis]
        if not driver:
            driver = bone.driver_add('scale', axis).driver
            driver.type = 'SCRIPTED'
            driver.expression = '1'
        
        prop_var = f'{prop}_{index}_'
        driver_var = driver.variables.get(prop_var) 
        if not driver_var:
            driver_var = driver.variables.new()
            driver_var.type = 'SINGLE_PROP'
            driver_var.name = prop_var

            driver_target = driver_var.targets[0]
            driver_target.id_type = 'OBJECT'
            driver_target.id = bone.id_data
            driver_target.data_path = bone.id_data.cm3d2_wide_slider.path_from_id(prop) + f'[{index}]'

              
        # if prop isn't already a factor
        if not prop_var in driver.expression:
            driver.expression = driver.expression + f' * {prop_var}'
                
        return
              
                      
    def AddVectorProperty(self, object, prop, value=None, default=0.0, min=-100, max=200):
        #value = value or [default, default, default]
        #object[prop] = not RESET_SETTINGS and object.get(prop) or value
        #object['_RNA_UI'][prop] = {
        #    'description': "",
        #    'default': default,
        #    'min': min,
        #    'max': max,
        #    'soft_min': min,
        #    'soft_max': max,
        #}     
        return
    
              
    def SetPosition(self, prop, boneName, ux, uy, uz, axisOrder=[0,1,2], axisFlip=None):
        # Check if object has this property
        #if not bpy.context.object.get(prop) or ONLY_FIX_SETTINGS:
        #    self.AddVectorProperty(bpy.context.object, prop)
        #    if ONLY_FIX_SETTINGS:
        #        return

        mat = get_axis_order_matrix(axisOrder).to_4x4()
        mat.translation = mathutils.Vector((ux, uy, uz)) * self.scale
        mat = compat.convert_cm_to_bl_bone_space(mat)
        uVec = mat.to_translation()
        axisOrder = get_matrix_axis_order(mat.to_3x3())

        if axisFlip != None:
            flipVec = get_axis_index_vector(axisFlip)
            flipVec = compat.convert_cm_to_bl_bone_space(flipVec)
            axisFlip = get_vector_axis_index(flipVec)
        
        ##ux, uy, uz = uz*5, ux*5, -uy*5
        ##axisFlip = axisOrder[axisFlip] if axisFlip else None
        #axisFlip = 1 if axisFlip == 0 else ( 2 if axisFlip == 1 else (0 if axisFlip == 2 else None) )
        ##axisFlip = axisOrder[axisFlip] if axisFlip else None
        #axisOrder[0], axisOrder[1], axisOrder[2] = axisOrder[2], axisOrder[0], axisOrder[1]
        ##axisFlip = axisOrder[axisFlip] if axisFlip != None else None
        
        bone = self.GetPoseBone(boneName)
        if bone:
            bone.bone.use_local_location = False
            drivers = self.GetDrivers(bone.name,'location')
        
            self.AddPositionDriver(prop, axisOrder[0], bone, drivers, 0, uVec[0])
            self.AddPositionDriver(prop, axisOrder[1], bone, drivers, 1, uVec[1])
            self.AddPositionDriver(prop, axisOrder[2], bone, drivers, 2, uVec[2])
        
        # repeat for left side
        if '?' in boneName:
            bone = self.GetPoseBone(boneName, flip=True)
            if bone:
                bone.bone.use_local_location = False
                drivers = self.GetDrivers(bone.name,'location')

                if axisFlip != None:
                    print(axisFlip)
                    uVec[axisFlip] *= -1
                
                #if   axisFlip == 0:
                #    ux = -ux
                #elif axisFlip == 1:
                #    uy = -uy
                #elif axisFlip == 2:
                #    uz = -uz
                
                self.AddPositionDriver(prop, axisOrder[0], bone, drivers, 0, uVec[0])
                self.AddPositionDriver(prop, axisOrder[1], bone, drivers, 1, uVec[1])
                self.AddPositionDriver(prop, axisOrder[2], bone, drivers, 2, uVec[2])
                                                                             
        return


    def SetScale(self, prop, boneName, axisOrder=[0,1,2]):
        # Check if object has this property
        #if not bpy.context.object.get(prop) or ONLY_FIX_SETTINGS:
        #    self.AddVectorProperty(bpy.context.object, prop, default=1.0, min=0.1, max=3.0)
        #    if ONLY_FIX_SETTINGS:
        #        return

        # x, y, z = x, z, y
        #axisOrder[0], axisOrder[1], axisOrder[2] = axisOrder[0], axisOrder[2], axisOrder[1]
        
        axisMat = get_axis_order_matrix(axisOrder).to_4x4()
        axisMat = compat.convert_cm_to_bl_bone_rotation(axisMat)
        #axisMat = compat.convert_cm_to_bl_bone_space(axisMat)
        axisOrder = get_matrix_axis_order(axisMat)
        
        bone = self.GetPoseBone(boneName)
        if bone:
            drivers = self.GetDrivers(bone.name,'scale')
            
            self.AddScaleDriver(prop, axisOrder[0], bone, drivers, 2)
            self.AddScaleDriver(prop, axisOrder[1], bone, drivers, 1)
            self.AddScaleDriver(prop, axisOrder[2], bone, drivers, 0)
        
        # repeat for left side
        if '?' in boneName:
            bone = self.GetPoseBone(boneName, True)
            if bone:
                drivers = self.GetDrivers(bone.name,'scale')

                self.AddScaleDriver(prop, axisOrder[0], bone, drivers, 2)
                self.AddScaleDriver(prop, axisOrder[1], bone, drivers, 1)
                self.AddScaleDriver(prop, axisOrder[2], bone, drivers, 0)
        
        return


@compat.BlRegister()
class CNV_OT_add_cm3d2_body_sliders(bpy.types.Operator):
    bl_idname      = 'object.add_cm3d2_body_sliders'
    bl_label       = "Add CM3D2 Body Sliders"
    bl_description = "Adds drivers to armature to enable body sliders."
    bl_options     = {'REGISTER', 'UNDO'}

    scale: bpy.props.FloatProperty(name="Scale", default=5, min=0.1, max=100, soft_min=0.1, soft_max=100, step=100, precision=1, description="The amount by which the mesh is scaled when imported. Recommended that you use the same when at the time of export.")

    is_fix_thigh: bpy.props.BoolProperty(name="Fix Thigh", default=False, description="Fix twist bone values for the thighs in motor-cycle pose")
    is_drive_shape_keys: bpy.props.BoolProperty(name="Drive Shape Keys", default=True, description="Connect sliders to mesh children's shape keys")
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if ob:
            arm = ob.data
        else:
            arm = None
        has_arm  = arm and isinstance(arm, bpy.types.Armature) and ('Bip01' in arm.bones)
        can_edit = (ob and ob.data == arm) or (arm and arm.is_editmode)
        return has_arm and can_edit

    def invoke(self, context, event):
        self.scale = common.preferences().scale
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'scale'              )
        #self.layout.prop(self, 'is_fix_thigh'       )
        self.layout.prop(self, 'is_drive_shape_keys')

    def driveShapeKey(self, shapekey, data, prop, expression, set_min=None, set_max=None):
        if not shapekey:
            return
        driver = shapekey.driver_add('value').driver
        driver.type = 'SCRIPTED'

        driver_var = driver.variables.new() if len(driver.variables) < 1 else driver.variables[0]
        driver_var.type = 'SINGLE_PROP'
        driver_var.name = prop

        driver_target = driver_var.targets[0]
        driver_target.id_type = 'OBJECT'
        driver_target.id = data.id_data
        driver_target.data_path = data.path_from_id(prop)

        driver.expression = expression

        if set_min:
            shapekey.slider_min = set_min
        if set_max:
            shapekey.slider_max = set_max

    def driveTwistBone(self, bone, prop='rotation_euler', axis=0, expression=''):
        if not bone:
            return
        driver = bone.driver_add(prop, axis).driver
        driver.type = 'SCRIPTED'
        driver.use_self = True

        driver.expression = expression

    def execute(self, context):
        ob = context.object
        arm = ob.data
        pre_mode = ob.mode
        #if pre_mode != 'EDIT':
        #    override = context.copy()
        #    override['active_object'] = ob
        #    bpy.ops.object.mode_set(override, mode='EDIT')

        morph   = ob.cm3d2_bone_morph
        sliders = ob.cm3d2_wide_slider

        morph.scale   = self.scale
        sliders.scale = self.scale



        #BoneMorph.SetPosition('KubiScl', 'Bip01 Neck'        , 0.95, 1   , 1   , 1.05, 1   , 1   )
        #BoneMorph.SetPosition('KubiScl', 'Bip01 Head'        , 0.8 , 1   , 1   , 1.2 , 1   , 1   )
        #BoneMorph.SetScale   ('UdeScl' , 'Bip01 ? UpperArm'  , 0.85, 1   , 1   , 1.15, 1   , 1   )
        #BoneMorph.SetScale   ('EyeSclX', 'Eyepos_L'          , 1   , 1   , 0.92, 1   , 1   , 1.08)
        #BoneMorph.SetScale   ('EyeSclX', 'Eyepos_R'          , 1   , 1   , 0.92, 1   , 1   , 1.08)
        #BoneMorph.SetScale   ('EyeSclY', 'Eyepos_L'          , 1   , 0.92, 1   , 1   , 1.08, 1   )
        #BoneMorph.SetScale   ('EyeSclY', 'Eyepos_R'          , 1   , 0.92, 1   , 1   , 1.08, 1   )
        #BoneMorph.SetPosition('EyePosX', 'Eyepos_R'          , 1   , 1   , 0.9 , 1   , 1   , 1.1 )
        #BoneMorph.SetPosition('EyePosX', 'Eyepos_L'          , 1   , 1   , 0.9 , 1   , 1   , 1.1 )
        #BoneMorph.SetPosition('EyePosY', 'Eyepos_R'          , 1   , 0.93, 1   , 1   , 1.07, 1   )
        #BoneMorph.SetPosition('EyePosY', 'Eyepos_L'          , 1   , 0.93, 1   , 1   , 1.07, 1   )
        #BoneMorph.SetScale   ('HeadX'  , 'Bip01 Head'        , 1   , 0.9 , 0.8 , 1   , 1.1 , 1.2 )
        #BoneMorph.SetScale   ('HeadY'  , 'Bip01 Head'        , 0.8 , 0.9 , 1   , 1.2 , 1.1 , 1   )
        #BoneMorph.SetPosition('DouPer' , 'Bip01 Spine'       , 1   , 1   , 0.94, 1   , 1   , 1.06)
        #BoneMorph.SetPosition('DouPer' , 'Bip01 Spine0a'     , 0.88, 1   , 1   , 1.12, 1   , 1   )
        #BoneMorph.SetPosition('DouPer' , 'Bip01 Spine1'      , 0.88, 1   , 1   , 1.12, 1   , 1   )
        #BoneMorph.SetPosition('DouPer' , 'Bip01 Spine1a'     , 0.88, 1   , 1   , 1.12, 1   , 1   )
        #BoneMorph.SetPosition('DouPer' , 'Bip01 Neck'        , 1.03, 1   , 1   , 0.97, 1   , 1   )
        #BoneMorph.SetPosition('DouPer' , 'Bip01 ? Calf'      , 0.87, 1   , 1   , 1.13, 1   , 1   )
        #BoneMorph.SetPosition('DouPer' , 'Bip01 ? Foot'      , 0.87, 1   , 1   , 1.13, 1   , 1   )
        #BoneMorph.SetScale   ('DouPer' , 'Bip01 ? Thigh_SCL_', 0.87, 1   , 1   , 1.13, 1   , 1   )
        #BoneMorph.SetScale   ('DouPer' , 'momotwist_?'       , 0.87, 1   , 1   , 1.13, 1   , 1   )
        #BoneMorph.SetScale   ('DouPer' , 'Bip01 ? Calf_SCL_' , 0.87, 1   , 1   , 1.13, 1   , 1   )
        #BoneMorph.SetScale   ('DouPer' , 'Bip01 ? UpperArm'  , 0.98, 1   , 1   , 1.02, 1   , 1   )
        #BoneMorph.SetPosition('sintyou', 'Bip01 Spine'       , 1   , 1   , 0.85, 1   , 1   , 1.15)
        #BoneMorph.SetPosition('sintyou', 'Bip01 Spine0a'     , 0.88, 1   , 1   , 1.12, 1   , 1   )
        #BoneMorph.SetPosition('sintyou', 'Bip01 Spine1'      , 0.88, 1   , 1   , 1.12, 1   , 1   )
        #BoneMorph.SetPosition('sintyou', 'Bip01 Spine1a'     , 0.88, 1   , 1   , 1.12, 1   , 1   )
        #BoneMorph.SetPosition('sintyou', 'Bip01 Neck'        , 0.97, 1   , 1   , 1.03, 1   , 1   )
        #BoneMorph.SetPosition('sintyou', 'Bip01 Head'        , 0.9 , 1   , 1   , 1.1 , 1   , 1   )
        #BoneMorph.SetPosition('sintyou', 'Bip01 ? Calf'      , 0.87, 1   , 1   , 1.13, 1   , 1   )
        #BoneMorph.SetPosition('sintyou', 'Bip01 ? Foot'      , 0.87, 1   , 1   , 1.13, 1   , 1   )
        #BoneMorph.SetScale   ('sintyou', 'Bip01 ? UpperArm'  , 0.9 , 1   , 1   , 1.1 , 1   , 1   )
        #BoneMorph.SetScale   ('sintyou', 'Bip01 ? Thigh_SCL_', 0.87, 1   , 1   , 1.13, 1   , 1   )
        #BoneMorph.SetScale   ('sintyou', 'momotwist_?'       , 0.87, 1   , 1   , 1.13, 1   , 1   )
        #BoneMorph.SetScale   ('sintyou', 'Bip01 ? Calf_SCL_' , 0.87, 1   , 1   , 1.13, 1   , 1   )
        #BoneMorph.SetScale   ('koshi'  , 'Bip01 Pelvis_SCL_' , 1   , 0.8 , 0.92, 1   , 1.2 , 1.08)
        #BoneMorph.SetScale   ('koshi'  , 'Bip01 Spine_SCL_'  , 1   , 1   , 1   , 1   , 1   , 1   )
        #BoneMorph.SetScale   ('koshi'  , 'Hip_?'             , 1   , 0.96, 0.9 , 1   , 1.04, 1.1 )
        #BoneMorph.SetScale   ('koshi'  , 'Skirt'             , 1   , 0.85, 0.88, 1   , 1.2 , 1.12)
        #BoneMorph.SetPosition('kata'   , 'Bip01 ? Clavicle'  , 0.98, 1   , 0.5 , 1.02, 1   , 1.5 )
        #BoneMorph.SetScale   ('kata'   , 'Bip01 Spine1a_SCL_', 1   , 1   , 0.95, 1   , 1   , 1.05)
        #BoneMorph.SetScale   ('west'   , 'Bip01 Spine_SCL_'  , 1   , 0.95, 0.9 , 1   , 1.05, 1.1 )
        #BoneMorph.SetScale   ('west'   , 'Bip01 Spine0a_SCL_', 1   , 0.85, 0.7 , 1   , 1.15, 1.3 )
        #BoneMorph.SetScale   ('west'   , 'Bip01 Spine1_SCL_' , 1   , 0.9 , 0.85, 1   , 1.1 , 1.15)
        #BoneMorph.SetScale   ('west'   , 'Bip01 Spine1a_SCL_', 1   , 0.95, 0.95, 1   , 1.05, 1.05)
        #BoneMorph.SetScale   ('west'   , 'Skirt'             , 1   , 0.92, 0.88, 1   , 1.08, 1.12)



        morph.SetPosition('KubiScl', 'Bip01 Neck'         , 1.05, 1   , 1   )
        morph.SetPosition('KubiScl', 'Bip01 Head'         , 1.2 , 1   , 1   )
                                                                      
        morph.SetScale   ('UdeScl' , 'Bip01 ? UpperArm'   , 1.15, 1   , 1   )
                                                                      
        morph.SetScale   ('HeadX'  , 'Bip01 Head'         , 1   , 1.1 , 1.2 )
        morph.SetScale   ('HeadY'  , 'Bip01 Head'         , 1.2 , 1.1 , 1   )
        
        morph.SetPosition('sintyou', 'Bip01 Spine'        , 1   , 1   , 1.15)
        morph.SetPosition('sintyou', 'Bip01 Spine0a'      , 1.12, 1   , 1   )
        morph.SetPosition('sintyou', 'Bip01 Spine1'       , 1.12, 1   , 1   )
        morph.SetPosition('sintyou', 'Bip01 Spine1a'      , 1.12, 1   , 1   )
        morph.SetPosition('sintyou', 'Bip01 Neck'         , 1.03, 1   , 1   )
        morph.SetPosition('sintyou', 'Bip01 Head'         , 1.1 , 1   , 1   )
        morph.SetPosition('sintyou', 'Bip01 ? Calf'       , 1.13, 1   , 1   )
        morph.SetPosition('sintyou', 'Bip01 ? Foot'       , 1.13, 1   , 1   )
        morph.SetScale   ('sintyou', 'Bip01 ? UpperArm'   , 1.1 , 1   , 1   )
        morph.SetScale   ('sintyou', 'Bip01 ? Thigh_SCL_' , 1.13, 1   , 1   )
        morph.SetScale   ('sintyou', 'momotwist_?'        , 1.13, 1   , 1   )
        morph.SetScale   ('sintyou', 'Bip01 ? Calf_SCL_'  , 1.13, 1   , 1   )
                                                                            
        # for DouPer, any bone not a thigh or a decendant of one, it's values are inverted
        morph.SetPosition('DouPer' , 'Bip01 Spine'        , 1, 1, (1-1.06)+1)
        morph.SetPosition('DouPer' , 'Bip01 Spine0a'      , (1-1.12)+1, 1, 1)
        morph.SetPosition('DouPer' , 'Bip01 Spine1'       , (1-1.12)+1, 1, 1)
        morph.SetPosition('DouPer' , 'Bip01 Spine1a'      , (1-1.12)+1, 1, 1)
        morph.SetPosition('DouPer' , 'Bip01 Neck'         , (1-0.97)+1, 1, 1)
        morph.SetScale   ('DouPer' , 'Bip01 ? UpperArm'   , (1-1.02)+1, 1, 1)
        morph.SetPosition('DouPer' , 'Bip01 ? Calf'       ,       1.13, 1, 1)
        morph.SetPosition('DouPer' , 'Bip01 ? Foot'       ,       1.13, 1, 1)
        morph.SetScale   ('DouPer' , 'Bip01 ? Thigh_SCL_' ,       1.13, 1, 1)
        morph.SetScale   ('DouPer' , 'momotwist_?'        ,       1.13, 1, 1)
        morph.SetScale   ('DouPer' , 'Bip01 ? Calf_SCL_'  ,       1.13, 1, 1)

        # This has some issues            
        morph.SetScale   ('koshi'  , 'Bip01 Pelvis_SCL_'  , 1   , 1.2 , 1.08)
        morph.SetScale   ('koshi'  , 'Bip01 Spine_SCL_'   , 1   , 1   , 1   )
        morph.SetScale   ('koshi'  , 'Hip_?'              , 1   , 1.04, 1.1 )
        morph.SetScale   ('koshi'  , 'Skirt'              , 1   , 1.2 , 1.12)
                                     
        #morph.SetPosition('kata'   , 'Bip01 ? Clavicle'   , 1.02, 1   , 1.5, default=0)
        morph.SetPosition('kata'   , 'Bip01 ? Clavicle'   , 1.02, 1   , 1.5 , default=50)
        morph.SetScale   ('kata'   , 'Bip01 Spine1a_SCL_' , 1   , 1   , 1.05, default=50)
                                        
        morph.SetScale   ('west'   , 'Bip01 Spine_SCL_'   , 1   , 1.05, 1.1 )
        morph.SetScale   ('west'   , 'Bip01 Spine0a_SCL_' , 1   , 1.15, 1.3 )
        morph.SetScale   ('west'   , 'Bip01 Spine1_SCL_'  , 1   , 1.1 , 1.15)
        morph.SetScale   ('west'   , 'Bip01 Spine1a_SCL_' , 1   , 1.05, 1.05)
        morph.SetScale   ('west'   , 'Skirt'              , 1   , 1.08, 1.12)
        
        # WideSlider functions MUST be called AFTER all BoneMorph calls
        sliders.SetPosition('THIPOS'    , 'Bip01 ? Thigh'     ,  0    ,  0.001,  0.001, axisFlip=2, axisOrder=[1, 2, 0]) #axisFlip=2 #axisFlip=0
        sliders.SetPosition('THI2POS'   , 'Bip01 ? Thigh_SCL_',  0.001,  0.001,  0.001, axisFlip=2, axisOrder=[1, 2, 0]) #axisFlip=2 #axisFlip=0
        sliders.SetPosition('HIPPOS'    , 'Hip_?'             ,  0.001,  0.001,  0.001, axisFlip=2, axisOrder=[1, 2, 0]) #axisFlip=2 #axisFlip=0
        sliders.SetPosition('MTWPOS'    , 'momotwist_?'       ,  0.1  ,  0.1  , -0.1  , axisFlip=2                     ) #axisFlip=2 #axisFlip=2
        sliders.SetPosition('MMNPOS'    , 'momoniku_?'        ,  0.1  ,  0.1  , -0.1  , axisFlip=1                     ) #axisFlip=1 #axisFlip=1
        sliders.SetPosition('SKTPOS'    , 'Skirt'             , -0.1  , -0.1  ,  0.1  ,             axisOrder=[2, 1, 0]) #           #
        sliders.SetPosition('SPIPOS'    , 'Bip01 Spine'       , -0.1  ,  0.1  ,  0.1                                   ) #           #
        sliders.SetPosition('S0APOS'    , 'Bip01 Spine0a'     , -0.1  ,  0.1  ,  0.1                                   ) #           #
        sliders.SetPosition('S1POS'     , 'Bip01 Spine1'      , -0.1  ,  0.1  ,  0.1                                   ) #           #
        sliders.SetPosition('S1APOS'    , 'Bip01 Spine1a'     , -0.1  ,  0.1  ,  0.1                                   ) #           #
        sliders.SetPosition('NECKPOS'   , 'Bip01 Neck'        , -0.1  ,  0.1  ,  0.1                                   ) #           #
        sliders.SetPosition('CLVPOS'    , 'Bip01 ? Clavicle'  , -0.1  ,  0.1  , -0.1  , axisFlip=2                     ) #axisFlip=2 #axisFlip=2
        sliders.SetPosition('MUNESUBPOS', 'Mune_?_sub'        , -0.1  ,  0.1  ,  0.1  , axisFlip=1, axisOrder=[2, 1, 0]) #axisFlip=1 #axisFlip=2
        sliders.SetPosition('MUNEPOS'   , 'Mune_?'            ,  0.1  , -0.1  , -0.1  , axisFlip=2, axisOrder=[1, 2, 0]) #axisFlip=2 #axisFlip=0
                                                                                                                                     
        sliders.SetScale   ('THISCL'    , 'Bip01 ? Thigh'     , axisOrder=[0, 1, -1])
        sliders.SetScale   ('MTWSCL'    , 'momotwist_?'       )
        sliders.SetScale   ('MMNSCL'    , 'momoniku_?'        )
        sliders.SetScale   ('PELSCL'    , 'Bip01 Pelvis_SCL_' )
        sliders.SetScale   ('THISCL2'   , 'Bip01 ? Thigh_SCL_')#, axisOrder=[0, 1, -1])
        sliders.SetScale   ('CALFSCL'   , 'Bip01 ? Calf'      )#, axisOrder=[0, 1, -1])
        sliders.SetScale   ('FOOTSCL'   , 'Bip01 ? Foot'      )
        sliders.SetScale   ('SKTSCL'    , 'Skirt'             )
        sliders.SetScale   ('SPISCL'    , 'Bip01 Spine_SCL_'  )
        sliders.SetScale   ('S0ASCL'    , 'Bip01 Spine0a_SCL_')
        sliders.SetScale   ('S1_SCL'    , 'Bip01 Spine1_SCL_' )
        sliders.SetScale   ('S1ASCL'    , 'Bip01 Spine1a_SCL_')
        sliders.SetScale   ('S1ABASESCL', 'Bip01 Spine1a'     )#, axisOrder=[0, 1, -1]))
        sliders.SetScale   ('KATASCL'   , 'Kata_?'            )
        sliders.SetScale   ('UPARMSCL'  , 'Bip01 ? UpperArm'  )
        sliders.SetScale   ('FARMSCL'   , 'Bip01 ? Forearm'   )
        sliders.SetScale   ('HANDSCL'   , 'Bip01 ? Hand'      )
        sliders.SetScale   ('CLVSCL'    , 'Bip01 ? Clavicle'  )
        sliders.SetScale   ('MUNESCL'   , 'Mune_?'            )
        sliders.SetScale   ('MUNESUBSCL', 'Mune_?_sub'        )
        sliders.SetScale   ('NECKSCL'   , 'Bip01 Neck_SCL_'   )
        sliders.SetScale   ('HIPSCL'    , 'Hip_?'             )
        sliders.SetScale   ('PELSCL'    , 'Hip_?'             ) # hips are also scaled with pelvis
        
        if self.is_fix_thigh:
            bone = morph.GetPoseBone('momoniku_?')
            bone.rotation_quaternion[0] = 0.997714
            bone.rotation_quaternion[3] = -0.06758
            bone = morph.GetPoseBone('momoniku_?', flip=True)
            bone.rotation_quaternion[0] = 0.997714
            bone.rotation_quaternion[3] = 0.06758
            
        if self.is_drive_shape_keys:
            for child in ob.children:
                if child.type == 'MESH':
                    sks = child.data.shape_keys.key_blocks
                    self.driveShapeKey(sks.get('arml'    ), morph, 'ArmL'    , 'ArmL     * 0.01')
                    self.driveShapeKey(sks.get('hara'    ), morph, 'Hara'    , 'Hara     * 0.01')
                    self.driveShapeKey(sks.get('munel'   ), morph, 'MuneL'   , 'MuneL    * 0.01', set_max=2)
                    self.driveShapeKey(sks.get('munes'   ), morph, 'MuneS'   , 'MuneS    * 0.01')
                    self.driveShapeKey(sks.get('munetare'), morph, 'MuneTare', 'MuneTare * 0.01', set_max=2)
                    self.driveShapeKey(sks.get('regfat'  ), morph, 'RegFat'  , 'RegFat   * 0.01')
                    self.driveShapeKey(sks.get('regmeet' ), morph, 'RegMeet' , 'RegMeet  * 0.01')

        if True:
            bones = ob.pose.bones
            Mune_L = bones.get('Mune_L') or bones.get('Mune_*.L')
            Mune_R = bones.get('Mune_R') or bones.get('Mune_*.R')
            if Mune_L:
                Mune_L.rotation_mode = 'XYZ'
            if Mune_R:                  
                Mune_R.rotation_mode = 'XYZ'
            
            self.driveTwistBone(Mune_R, axis=0, expression='-(self.id_data.cm3d2_bone_morph.MuneUpDown-50) * self.id_data.cm3d2_bone_morph.MuneL * (pi/180) * 0.00060')
            self.driveTwistBone(Mune_L, axis=0, expression='+(self.id_data.cm3d2_bone_morph.MuneUpDown-50) * self.id_data.cm3d2_bone_morph.MuneL * (pi/180) * 0.00060')
            self.driveTwistBone(Mune_R, axis=2, expression='-(self.id_data.cm3d2_bone_morph.MuneYori  -50) * self.id_data.cm3d2_bone_morph.MuneL * (pi/180) * 0.00025')
            self.driveTwistBone(Mune_L, axis=2, expression='-(self.id_data.cm3d2_bone_morph.MuneYori  -50) * self.id_data.cm3d2_bone_morph.MuneL * (pi/180) * 0.00025')



        

        bpy.ops.object.mode_set(mode=pre_mode)
        
        return {'FINISHED'}



@compat.BlRegister()
class DATA_PT_cm3d2_sliders(bpy.types.Panel):
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = 'data'
    bl_label       = "CM3D2 Sliders"
    bl_idname      = 'DATA_PT_cm3d2_sliders'

    @classmethod
    def poll(cls, context):
        ob = context.object
        if ob:
            arm = ob.data
        else:
            arm = None
        return arm and isinstance(arm, bpy.types.Armature) and ('Bip01' in arm.bones)

    def draw(self, context):
        ob = context.object
        if ob:
            arm = ob.data
        else:
            arm = None

        morph = ob.cm3d2_bone_morph

        # 初回の数値計算、自プロパティ書き換えがあるためdraw外で行う必要がありタイマー実行する
        if not morph.is_initialized:
            bpy.app.timers.register(morph.initialize, first_interval=0)
            return

        self.layout.alignment = 'RIGHT'
        flow = self.layout.grid_flow(row_major=True, columns=2, align=True)
        flow.use_property_split    = True
        flow.use_property_decorate = False
        flow.prop(morph, 'height', text="Height", emboss=False)
        flow.prop(morph, 'weight', text="Weight", emboss=False)
        flow.prop(morph, 'bust'  , text="Bust"  , emboss=False)
        flow.prop(morph, 'cup'   , text="Cup"   , emboss=False)
        flow.prop(morph, 'waist' , text="Waist" , emboss=False)
        flow.prop(morph, 'hip'   , text="Hip"   , emboss=False)
                                
        row = self.layout.row()
        #row.enabled = bpy.ops.object.add_cm3d2_body_sliders.poll(context.copy())
        op = row.operator('object.add_cm3d2_body_sliders', text="Connect Sliders", icon='CONSTRAINT_BONE')
        
        row = self.layout.row()
        #row.enabled = bpy.ops.object.cleanup_scale_bones.poll(context.copy())
        op = row.operator('object.cleanup_scale_bones', text="Cleanup Scale Bones", icon='X')




@compat.BlRegister()
class DATA_PT_cm3d2_body_sliders(bpy.types.Panel):
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = 'data'
    bl_label       = "Body Sliders"
    bl_idname      = 'DATA_PT_cm3d2_body_sliders'
    bl_parent_id   = 'DATA_PT_cm3d2_sliders'
    bl_options     = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.object and True

    def draw(self, context):
        morph = context.object.cm3d2_bone_morph
        self.layout.operator('object.save_cm3d2_body_sliders_to_menu', icon='COPYDOWN')

        self.layout.use_property_split = True
        flow = self.layout.column_flow()
        flow.scale_x = 0.5
        col = flow.column(align=True); col.prop(morph, 'HeadX'     , text="Face Width"  , slider=True)
        pass;                          col.prop(morph, 'HeadY'     , text="Face Height" , slider=True)
        col = flow.column(align=True); col.prop(morph, 'DouPer'    , text="Leg Length"  , slider=True)
        pass;                          col.prop(morph, 'sintyou'   , text="Height"      , slider=True)
        col = flow.column(align=True); col.prop(morph, 'BreastSize', text="Breast Size" , slider=True)
        pass;                          col.prop(morph, 'MuneTare'  , text="Breast Sag"  , slider=True)
        pass;                          col.prop(morph, 'MuneUpDown', text="Breast Pitch", slider=True)
        pass;                          col.prop(morph, 'MuneYori'  , text="Breast Yaw"  , slider=True)
        col = flow.column(align=True); col.prop(morph, 'west'      , text="Waist"       , slider=True)
        pass;                          col.prop(morph, 'Hara'      , text="Belly"       , slider=True)
        pass;                          col.prop(morph, 'kata'      , text="Shoulders"   , slider=True)
        pass;                          col.prop(morph, 'ArmL'      , text="Arm Size"    , slider=True)
        pass;                          col.prop(morph, 'UdeScl'    , text="Arm Length"  , slider=True)
        pass;                          col.prop(morph, 'KubiScl'   , text="Neck Length" , slider=True)
        col = flow.column(align=True); col.prop(morph, 'koshi'     , text="Hip"         , slider=True)
        pass;                          col.prop(morph, 'RegFat'    , text="Leg Fat"     , slider=True)
        pass;                          col.prop(morph, 'RegMeet'   , text="Leg Meat"    , slider=True)
                                       

@compat.BlRegister()
class DATA_PT_cm3d2_wide_sliders(bpy.types.Panel):
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = 'data'
    bl_label       = "Wide Sliders"
    bl_idname      = 'DATA_PT_cm3d2_wide_sliders'
    bl_parent_id   = 'DATA_PT_cm3d2_sliders'
    bl_options     = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.object and True

    def draw(self, context):
        sliders = context.object.cm3d2_wide_slider
        
        self.layout.use_property_split = True

        row = self.layout.row()
        row.use_property_decorate = False
        row.prop(sliders, 'enable_all', text="Enable All Sliders")

        flow = self.layout.grid_flow(row_major=True)
        flow.scale_x = 0.5

        def _transform_prop(name, pos_prop=None, scl_prop=None, pos_enabled=(True, True, True), scl_enabled=(True, True, True)):
            #lab = flow.row(align=True)
            #lab.alignment = 'RIGHT'
            #lab.label(text=name)
            #sub = lab.column()
            #sub.label(text=name)
            #sub.alignment = 'RIGHT'
            
            tab = flow.column()#align=True)
            #tab.alignment = 'LEFT'
            #tab.label(text=name)

            col = tab.column(align=True)
            
            global used_name
            used_name = False
            def _vec_prop(type_name, prop_id, enabled_axes, axis_names):
                global used_name
                #vec = tab.row(align=True)
                #vec.label(text=type_name)
                #col = vec.column(align=True)
                for i in range(0, 3):
                    is_enabled  = enabled_axes[i] or sliders.enable_all
                    is_disabled = enabled_axes[i] == None

                    row = col.row(align=True)
                    row.enabled = not is_disabled and is_enabled
                    
                    axis_name = axis_names[i]
                    if i == 0:
                        axis_name = type_name + ' ' + axis_name
                        if not used_name:
                            axis_name = name + ' ' + axis_name
                            used_name = True

                    row.prop(
                        sliders                                , 
                        prop_id if not is_disabled else 'empty',
                        text   = axis_name                     , 
                        slider = not is_disabled               ,
                        emboss = not is_disabled               ,
                        index  = -1 if is_disabled else i      ,
                    )

            if pos_prop:
                _vec_prop(iface_("Position"), pos_prop, pos_enabled, ('X', 'Y', 'Z'))
            if scl_prop:
                _vec_prop(iface_("Scale"   ), scl_prop, scl_enabled, ('X', 'Y', 'Z'))


        _transform_prop("Pelvis"       , None        , 'PELSCL'                                                                           )
        _transform_prop("Hips"         , 'HIPPOS'    , 'HIPSCL'                                                                           )
        _transform_prop("Legs"         , 'THIPOS'    , 'THISCL'    , pos_enabled=(True , None , True ), scl_enabled=(True , True , None ) )
        _transform_prop("Thigh"        , 'MTWPOS'    , 'MTWSCL'                                                                           )
        _transform_prop("Rear Thigh"   , 'MMNPOS'    , 'MMNSCL'                                                                           )
        _transform_prop("Knee"         , 'THI2POS'   , 'THISCL2'                                      , scl_enabled=(True , True , False) )
        _transform_prop("Calf"         , None        , 'CALFSCL'                                      , scl_enabled=(True , True , False) )
        _transform_prop("Foot"         , None        , 'FOOTSCL'                                                                          )
        _transform_prop("Skirt"        , 'SKTPOS'    , 'SKTSCL'    , pos_enabled=(False, False, True )                                    )
        _transform_prop("Lower Abdomen", 'SPIPOS'    , 'SPISCL'    , pos_enabled=(True , False, True )                                    )
        _transform_prop("Upper Abdomen", 'S0APOS'    , 'S0ASCL'    , pos_enabled=(True , True , False)                                    )
        _transform_prop("Lower Chest"  , 'S1POS'     , 'S1_SCL'    , pos_enabled=(True , True , False)                                    )
        _transform_prop("Upper Chest"  , 'S1APOS'    , 'S1ASCL'    , pos_enabled=(True , True , False)                                    )
        _transform_prop("Upper Torso"  , None        , 'S1ABASESCL'                                   , scl_enabled=(True , True , False) )
        _transform_prop("Breasts"      , 'MUNEPOS'   , 'MUNESCL'                                                                          )
        _transform_prop("Breasts Sub"  , 'MUNESUBPOS', 'MUNESUBSCL'                                                                       )
        _transform_prop("Neck"         , 'NECKPOS'   , 'NECKSCL'                                                                          )
        _transform_prop("Clavicle"     , 'CLVPOS'    , 'CLVSCL'                                                                           )
        _transform_prop("Shoulders"    , None        , 'KATASCL'                                                                          )
        _transform_prop("Upper Arm"    , None        , 'UPARMSCL'                                                                         )
        _transform_prop("Forearm"      , None        , 'FARMSCL'                                                                          )
        _transform_prop("Hand"         , None        , 'HANDSCL'                                                                          )

                                                           


@compat.BlRegister()
class CNV_OT_cleanup_scale_bones(bpy.types.Operator):
    bl_idname      = 'object.cleanup_scale_bones'
    bl_label       = "Cleanup Scale Bones"
    bl_description = "Remove scale bones from the active armature object"
    bl_options     = {'REGISTER', 'UNDO'}

    scale: bpy.props.FloatProperty(name="Scale", default=5, min=0.1, max=100, soft_min=0.1, soft_max=100, step=100, precision=1, description="The amount by which the mesh is scaled when imported. Recommended that you use the same when at the time of export.")

    is_keep_bones_with_children: bpy.props.BoolProperty(name="Keep bones with children", default=True, description="Will not remove scale bones that have children (for custom scale bones)")
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if ob:
            arm = ob.data
        else:
            arm = None
        has_arm  = arm and isinstance(arm, bpy.types.Armature)
        has_scl = False
        if has_arm:
            for bone in arm.edit_bones:
                if '_SCL_' in bone.name:
                    has_scl = True
                    break
        return has_arm and has_scl

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'is_keep_bones_with_children')

    def execute(self, context):
        ob = context.object
        arm = ob.data

        edit_bones = arm.edit_bones
        deleted_bones = {}
        for bone in edit_bones:
            if not '_SCL_' in bone.name:
                continue
            if self.is_keep_bones_with_children and len(bone.children) > 0:
                continue
            parent = edit_bones.get(bone.name.replace('_SCL_','')) or bone.parent
            if parent:
                parent['cm3d2_scl_bone'] = True
                deleted_bones[bone.name] = parent.name
                edit_bones.remove(bone)

        for child in ob.children:
            vgroups = child.vertex_groups
            if vgroups and len(vgroups) > 0:
                for old_name, new_name in deleted_bones.items():
                    old_vgroup = vgroups.get(old_name)
                    if old_vgroup:
                        old_vgroup.name = new_name

        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_save_cm3d2_body_sliders_to_menu(bpy.types.Operator):
    bl_idname      = 'object.save_cm3d2_body_sliders_to_menu'
    bl_label       = "Save CM3D2 Body Sliders to Menu"
    bl_description = "Remove scale bones from the active armature object"
    bl_options     = {'REGISTER', 'UNDO'}

    is_overwrite: bpy.props.BoolProperty(name="Overwrite Existing", default=True)

    @classmethod
    def poll(cls, context):
        ob = context.object
        if ob:
            arm = ob.data
        else:
            arm = None
        has_arm  = arm and isinstance(arm, bpy.types.Armature)
        return has_arm

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'is_overwrite')
        if self.is_overwrite:
            self.layout.label(text="Any existing data will be overwritten", icon='ERROR')

    def execute(self, context):
        ob = context.object
        menu_file_data = ob.cm3d2_menu
        morph = ob.cm3d2_bone_morph

        def add_menu_prop_command(prop_name):
            menu_file_data.parse_list(
                ['prop',
                    prop_name,
                    str(int( getattr(morph, prop_name) ))
                ]
            )

        if self.is_overwrite:
            menu_file_data.clear()

            menu_file_data.version     = 1000
            menu_file_data.path        = os.path.relpath(bpy.data.filepath, start=bpy.path.abspath('//..'))
            menu_file_data.name        = f'{ob.name} {data_("Body")}'
            menu_file_data.category    = 'set_body'
            menu_file_data.description = data_("Generated in blender using body sliders")
                                                                                            
            menu_file_data.parse_list(['メニューフォルダ', 'system'                                 ])
            menu_file_data.parse_list(['category', 'set_body'                               ])
            menu_file_data.parse_list(['priority', '100'                                    ])
            menu_file_data.parse_list(['icons'   , '_i_set_body_1_.tex'                     ])
            menu_file_data.parse_list(['属性追加' , 'クリックしても選択状態にしない'               ])
            menu_file_data.parse_list(['name'    , menu_file_data.name                      ])
            menu_file_data.parse_list(['setumei' , data_("Generated in blender using body sliders")])

        add_menu_prop_command('HeadX'     )
        add_menu_prop_command('HeadY'     )
        add_menu_prop_command('DouPer'    )
        add_menu_prop_command('sintyou'   )
        add_menu_prop_command('BreastSize')
        add_menu_prop_command('MuneTare'  )
        add_menu_prop_command('MuneUpDown')
        add_menu_prop_command('MuneYori'  )
        add_menu_prop_command('west'      )
        add_menu_prop_command('Hara'      )
        add_menu_prop_command('kata'      )
        add_menu_prop_command('ArmL'      )
        add_menu_prop_command('UdeScl'    )
        add_menu_prop_command('KubiScl'   )
        add_menu_prop_command('koshi'     )
        add_menu_prop_command('RegFat'    )
        add_menu_prop_command('RegMeet'   )

        self.report(type={'INFO'}, message="Successfully saved properties to menu file data in Properties > Object Tab > CM3D2 Menu File")

        return {'FINISHED'}
