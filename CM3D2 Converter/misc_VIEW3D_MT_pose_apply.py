# 「3Dビュー」エリア → ポーズモード or オブジェクトモード → Ctrl+A (ポーズ → 適用)
import bpy
import mathutils
from . import common
from . import compat


# メニュー等に項目追加
def menu_func(self, context):
    self.layout.separator()
    self.layout.operator('pose.transfer_pose' , icon_value=common.kiss_icon())
    self.layout.operator('pose.apply_prime_field', icon_value=common.kiss_icon())
    row = self.layout.row()
    row.operator('pose.revert_primed_pose', icon_value=common.kiss_icon())
    ob = context.active_object
    # チェック対象がexecuteで変更される関係でpollでチェックさせるとREDOできなくなるため、ここで有効無効を切り替える
    if not ob or ob.type != 'ARMATURE' or not ob.data.get('is T Stance'):
        row.enabled = False

@compat.BlRegister()
class CNV_OT_transfer_pose(bpy.types.Operator):
    bl_idname = 'pose.transfer_pose'
    bl_label = "Transfer Pose"
    bl_description = "Transfers the visual pose of the selected object to the active object"
    bl_options = {'REGISTER', 'UNDO'}

    is_only_selected: bpy.props.BoolProperty(name="Only Selected", default=True)
    is_key_location: bpy.props.BoolProperty(name="Key Location", default=True)
    is_key_rotation: bpy.props.BoolProperty(name="Key Rotation", default=True)
    is_key_scale: bpy.props.BoolProperty(name="Key Scale", default=True)

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        selected = [o for o in context.selected_objects if o != ob]
        if ob and ob.type == 'ARMATURE' and len(selected) == 1 and selected[0].type == 'ARMATURE':
            return True
        return False

    def draw(self, context):
        self.layout.prop(self, 'is_only_selected')
        self.layout.prop(self, 'is_key_location' )
        self.layout.prop(self, 'is_key_rotation' )
        self.layout.prop(self, 'is_key_scale'    )

    def execute(self, context):
        target_ob = context.active_object
        selected = [o for o in context.selected_objects if o != target_ob]
        source_ob = selected[0]

        pre_mode = target_ob.mode
        
        bpy.ops.object.mode_set(mode='POSE')
        pre_selected_pose_bones = compat.get_selected_pose_bones(context)
        bpy.ops.pose.select_all(action='SELECT')

        # ポーズモードで操作した場合のみ対象ボーンは選択のみとするのをデフォルトにする (REDOで変えられる)
        if not self.properties.is_property_set('is_only_selected'):
            self.is_only_selected = pre_mode == 'POSE'
        # 対象ボーンにコンストレイントを一時的に追加
        bones = pre_selected_pose_bones if self.is_only_selected else target_ob.pose.bones
        for bone in bones:
            # ターゲット側に同名のボーンがなければスキップ
            if bone.name not in source_ob.data.bones:
                continue
            # すでに同名のコンストレイントがある場合は削除しておく
            for c in bone.constraints:
                if c.name in ['TEMP_TRANSFORM', 'TEMP_SCALE']:
                    bone.constraints.remove(c)
            if self.is_key_location or self.is_key_rotation:
                # コピー（変形）コンストレイントを追加、ターゲットのレストポーズを参照
                const = bone.constraints.new('COPY_TRANSFORMS')
                const.name = "TEMP_TRANSFORM"
                const.target = source_ob
                const.subtarget = bone.name
            if self.is_key_scale:
                source_bone = source_ob.pose.bones.get(bone.name)
                const = bone.constraints.new('LIMIT_SCALE')
                const.name = "TEMP_SCALE"
                const.owner_space = 'LOCAL'
                const.use_transform_limit = True
                const.use_min_x = True
                const.use_min_y = True
                const.use_min_z = True
                const.use_max_x = True
                const.use_max_y = True
                const.use_max_z = True
                const.min_x = source_bone.scale.x
                const.min_y = source_bone.scale.y
                const.min_z = source_bone.scale.z
                if source_ob.data.get("is T Stance"):
                    source_prime_scale = mathutils.Vector(source_bone.get('prime_scale',(1,1,1)))
                    const.min_x *= source_prime_scale.x
                    const.min_y *= source_prime_scale.y
                    const.min_z *= source_prime_scale.z
                if target_ob.data.get("is T Stance"):
                    target_prime_scale = mathutils.Vector(bone.get('prime_scale', (1,1,1)))
                    const.min_x /= target_prime_scale.x
                    const.min_y /= target_prime_scale.y
                    const.min_z /= target_prime_scale.z
                const.max_x = const.min_x
                const.max_y = const.min_y
                const.max_z = const.min_z

        # コンストレイントに沿ってポーズ適用
        bpy.ops.pose.visual_transform_apply()

        # 一時的に作ったコンストレイントを削除
        for bone in target_ob.pose.bones:
            for c in bone.constraints:
                if c.name in ['TEMP_TRANSFORM', 'TEMP_SCALE']:
                    bone.constraints.remove(c)

        # ボーン選択状態・モードを元に戻す
        bpy.ops.pose.select_all(action='DESELECT')
        compat.set_select_pose_bones(pre_selected_pose_bones)
        bpy.ops.object.mode_set(mode=pre_mode)
        
        return {'FINISHED'}


class CNV_OT_base_apply_prime_field(bpy.types.Operator):

    is_apply_armature_modifier: bpy.props.BoolProperty(name="関係するメッシュのアーマチュアを適用", default=True)
    is_preserve_shape_key_values: bpy.props.BoolProperty(name="Preserve Shape Key Values", default=True , description="Ensure shape key values of child mesh objects are not changed")
    is_deform_preserve_volume: bpy.props.BoolProperty(name="アーマチュア適用は体積を維持", default=True)
    revert_primed_pose: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        selected = [o for o in context.selected_objects if o != ob]
        if ob and ob.type == 'ARMATURE' and ob.select_get() and len(selected) == 0:
            return True
        return False

    def draw(self, context):
        self.layout.prop(self, 'is_apply_armature_modifier')

        col = self.layout.column()
        col.enabled = self.is_apply_armature_modifier
        col.prop(self , 'is_preserve_shape_key_values')
        col.prop(self , 'is_deform_preserve_volume'   )

    def execute(self, context):
        ob = context.active_object
        arm = ob.data
        progress = 0

        pre_mode = ob.mode
        bpy.ops.object.mode_set(mode='POSE')
        pre_selected_pose_bones = compat.get_selected_pose_bones(context)

        # 元のレストポーズに戻す場合
        if self.revert_primed_pose:
            # キーフレーム比較アクションは破棄する
            action_name = f'{ob.name}_poses'
            action = context.blend_data.actions.get(action_name)
            if action:
                context.blend_data.actions.remove(action)

            # 元のレストポーズを現ポーズとしてコピー導入(カスタムプロパティからの再現)
            copy_pose_from_property(ob)

        # 現ポーズでのアーマチュアモディファイアの強制適用 ＆ 適用後用の新規アーマチュアモディファイア追加
        bpy.ops.object.mode_set(mode='OBJECT')
        compat.set_select(ob, True)
        if self.is_apply_armature_modifier and ob.children:
            context.window_manager.progress_begin(0, len(ob.children)+1)
            for child in ob.children:
                with context.temp_override(object=child, active_object=child):
                    if child.type == 'MESH' and len(child.modifiers) and bpy.ops.object.forced_modifier_apply.poll():
                        for mod in child.modifiers:
                            if mod.type == 'ARMATURE':
                                mod.use_deform_preserve_volume = self.is_deform_preserve_volume
                                if not mod.object == ob:
                                    had_armature = False
                                else:
                                    had_armature = True
                                    old_name                = mod.name
                                    old_show_expanded       = mod.show_expanded
                                    old_show_in_editmode    = mod.show_in_editmode
                                    old_show_on_cage        = mod.show_on_cage
                                    old_show_render         = mod.show_render
                                    old_show_viewport       = mod.show_viewport
                                    old_use_apply_on_spline = mod.use_apply_on_spline
                                    old_invert_vertex_group = mod.invert_vertex_group
                                    old_use_bone_envelopes  = mod.use_bone_envelopes
                                    #old_use_multi_modifier  = mod.use_multi_modifier
                                    old_use_vertex_groups   = mod.use_vertex_groups
                                    old_vertex_group        = mod.vertex_group
                        apply_results = bpy.ops.object.forced_modifier_apply(apply_viewport_visible=True, is_preserve_shape_key_values=self.is_preserve_shape_key_values, initial_progress=progress)
                        if ('FINISHED' in apply_results) and had_armature:
                            new_mod = child.modifiers.new(name=old_name, type='ARMATURE')
                            new_mod.object              = ob
                            new_mod.use_deform_preserve_volume = self.is_deform_preserve_volume
                            new_mod.show_expanded       = old_show_expanded
                            new_mod.show_in_editmode    = old_show_in_editmode
                            new_mod.show_on_cage        = old_show_on_cage
                            new_mod.show_render         = old_show_render
                            new_mod.show_viewport       = old_show_viewport
                            new_mod.use_apply_on_spline = old_use_apply_on_spline
                            new_mod.invert_vertex_group = old_invert_vertex_group
                            new_mod.use_bone_envelopes  = old_use_bone_envelopes
                            #new_mod.use_multi_modifier  = old_use_multi_modifier
                            new_mod.use_vertex_groups   = old_use_vertex_groups
                            new_mod.vertex_group        = old_vertex_group
                
                progress += 1
                context.window_manager.progress_update(progress)

        else:
            context.window_manager.progress_begin(0, 1)  

        compat.set_active(context, ob)
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='SELECT')
        for bone in ob.pose.bones:
            prime_scale = mathutils.Vector(bone.get('prime_scale', (1.0,1.0,1.0)))
            bone_scale = bone.scale #bone.matrix.to_scale()
            prime_scale.x *= bone_scale.x
            prime_scale.y *= bone_scale.y
            prime_scale.z *= bone_scale.z
            bone['prime_scale'] = prime_scale
            #bone['_RNA_UI']['prime_scale']['subtype'] = 'XYZ'

        # 現ポーズをレストポーズに適用
        bpy.ops.pose.armature_apply()

        # 元のレストポーズに戻す場合
        if self.revert_primed_pose:
            # レストポーズ変更フラグを解除
            arm['is T Stance'] = False
        elif 'BoneData:0' in arm and 'LocalBoneData:0' in arm:
            # レストポーズ変更フラグ
            arm['is T Stance'] = True

            # 元のレストポーズを現ポーズとしてコピー導入(カスタムプロパティからの再現)
            copy_pose_from_property(ob)

            # キーフレーム利用の準備
            if not ob.animation_data:
                ob.animation_data_create()
            # 専用のアクション名で用意する
            action_name = f'{ob.name}_poses'
            action = context.blend_data.actions.get(action_name)
            if not action:
                action = context.blend_data.actions.new(action_name)
                action.use_fake_user = True
            else:
                # 既に存在している場合、フレーム付けなおしのため全fcurveをクリアする
                _ = compat.get_fcurves(action=action, slot_name=ob.name, clear=True)
            ob.animation_data.action = action

            def insert_pose(ob, i):
                for bone in ob.pose.bones:
                    bone.keyframe_insert(data_path="location", frame=i, group=bone.name)
                    bone.keyframe_insert(data_path="rotation_euler", frame=i, group=bone.name)
                    bone.keyframe_insert(data_path="rotation_quaternion", frame=i, group=bone.name)
                    bone.keyframe_insert(data_path='scale', frame=i, group=bone.name)

            # 0フレームに元のレストポーズをポーズとして配置
            insert_pose(ob, 0)
            # 1フレームにレストポーズを配置
            bpy.ops.pose.transforms_clear()
            insert_pose(ob, 1)
            # レストポーズフレームに移動
            bpy.context.scene.frame_set(1)

        context.window_manager.progress_end()

        # 各種選択状態を戻す
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='DESELECT')
        compat.set_select_pose_bones(pre_selected_pose_bones)
        bpy.ops.object.mode_set(mode=pre_mode)

        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_apply_prime_field(CNV_OT_base_apply_prime_field):
    bl_idname = 'pose.apply_prime_field'
    bl_label = "現在のポーズで素体化"
    bl_description = "現在のポーズで衣装をモデリングしやすくする素体を作成します"
    bl_options = {'REGISTER', 'UNDO'}


@compat.BlRegister()
class CNV_OT_revert_primed_pose(CNV_OT_base_apply_prime_field):
    bl_idname = "pose.revert_primed_pose"
    bl_label = "元の素体ポーズに戻す"
    bl_description = "カスタムプロパティのボーン情報を元に最初の素体ポーズを復元します"
    bl_options = {'REGISTER', 'UNDO'}

    revert_primed_pose: bpy.props.BoolProperty(default=True, options={'HIDDEN'})

    def invoke(self, context, event):
        # Properties パネルからの呼び出し向け (REDOパネル出せないため)
        return context.window_manager.invoke_props_dialog(self)


def copy_pose_from_property(ob: bpy.types.Object):
    """
    指定のアーマチュアオブジェクトのカスタムプロパティのボーン情報から元のレストポーズをポーズとして復元する
    """
    arm = ob.data

    import re
    is_convert_bone_weight_names = any(
        b for b in arm.bones if b.name.count('*') == 1 and re.search(r'\.([rRlL])$', b.name))

    from .model_export import CNV_OT_export_cm3d2_model as export_model
    bone_data = export_model.bone_data_parser(export_model.indexed_data_generator(arm, prefix="BoneData:"))

    import_scale = arm.get('ImportScale', common.preferences().scale)

    for data in bone_data:
        if data['parent_index'] == -1:
            continue
        parent_name = bone_data[data['parent_index']]['name']
        parent = ob.pose.bones.get(common.decode_bone_name(parent_name, is_convert_bone_weight_names))
        if not parent:
            continue

        bone = ob.pose.bones.get(common.decode_bone_name(data['name'], is_convert_bone_weight_names))

        local_co = mathutils.Vector(data['co'].copy()) * import_scale
        local_rot = mathutils.Quaternion(data['rot'].copy())
        local_co_mat = mathutils.Matrix.Translation(local_co)
        local_rot_mat = local_rot.to_matrix().to_4x4()
        local_mat = compat.mul(local_co_mat, local_rot_mat)
        local_mat = compat.convert_cm_to_bl_bone_space(local_mat)
        mat = compat.mul(parent.matrix, local_mat)
        mat = compat.convert_cm_to_bl_bone_rotation(mat)

        compat.set_bone_matrix(bone, mat)

        if 'scale' in data:
            bone['cm3d2_bone_scale'] = data['scale']
            scale = mathutils.Vector(data['scale'])
            scale *= import_scale * 0.01
            bone.bbone_x = scale.x
            bone.bbone_z = scale.z
