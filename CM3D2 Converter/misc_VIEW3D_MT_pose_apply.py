# 「3Dビュー」エリア → ポーズモード or オブジェクトモード → Ctrl+A (ポーズ → 適用)
import bpy
import mathutils
from . import common
from . import compat


# メニュー等に項目追加
def menu_func(self, context):
    self.layout.separator()
    self.layout.operator('pose.transfer_pose' , icon_value=common.kiss_icon())
    self.layout.operator('pose.prime_pose', icon_value=common.kiss_icon())
    row = self.layout.row()
    row.operator('pose.revert_primed_pose', icon_value=common.kiss_icon())
    __, ob = common.get_outliner_selection(context, 'ARMATURE')
    # チェック対象がexecuteで変更される関係でpollでチェックさせるとREDOできなくなるため、ここで有効無効を切り替える
    if not ob or not ob.data.get('isPrimedPose'):
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
        selected, ob = common.get_outliner_selection(context, 'ARMATURE')
        selected = [o for o in selected if o != ob]
        if ob and len(selected) == 1:
            return True
        return False

    def draw(self, context):
        self.layout.prop(self, 'is_only_selected')
        self.layout.prop(self, 'is_key_location' )
        self.layout.prop(self, 'is_key_rotation' )
        self.layout.prop(self, 'is_key_scale'    )

    def execute(self, context):
        selected, target_ob = common.get_outliner_selection(context, 'ARMATURE')
        selected = [o for o in selected if o != target_ob]
        source_ob = selected[0]

        pre_mode = target_ob.mode
        pre_hide = target_ob.hide_get()

        # ポーズモードで操作した場合のみ対象ボーンは選択のみとするのをデフォルトにする (REDOで変えられる)
        if not self.properties.is_property_set('is_only_selected'):
            self.is_only_selected = pre_mode == 'POSE'

        # 対象ボーンの選定・トランスフォームクリア・選択状態バックアップ
        target_ob.hide_set(False)
        with context.temp_override(object=target_ob, active_object=target_ob):
            bpy.ops.object.mode_set(mode='POSE')
            pre_selected_pose_bones = compat.get_selected_pose_bones(context)
            if self.is_only_selected:
                bones = pre_selected_pose_bones
            else:
                bpy.ops.pose.select_all(action='SELECT')
                bones = target_ob.pose.bones
            bpy.ops.pose.transforms_clear()

        # 対象ボーンにコンストレイントを一時的に追加
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
                const.name = 'TEMP_TRANSFORM'
                const.target = source_ob
                const.subtarget = bone.name
            if self.is_key_scale:
                source_bone = source_ob.pose.bones.get(bone.name)
                const = bone.constraints.new('LIMIT_SCALE')
                const.name = 'TEMP_SCALE'
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
                if source_ob.data.get('isPrimedPose'):
                    source_prime_scale = mathutils.Vector(source_bone.get('prime_scale', (1, 1, 1)))
                    const.min_x *= source_prime_scale.x
                    const.min_y *= source_prime_scale.y
                    const.min_z *= source_prime_scale.z
                if target_ob.data.get('isPrimedPose'):
                    target_prime_scale = mathutils.Vector(bone.get('prime_scale', (1, 1, 1)))
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
        target_ob.hide_set(pre_hide)
        
        return {'FINISHED'}


class CNV_OT_base_prime_pose_operator(bpy.types.Operator):

    is_apply_armature_modifier: bpy.props.BoolProperty(name="関係するメッシュのアーマチュアを適用", default=True)
    is_preserve_shape_key_values: bpy.props.BoolProperty(name="Preserve Shape Key Values", default=True , description="Ensure shape key values of child mesh objects are not changed")
    is_deform_preserve_volume: bpy.props.BoolProperty(name="アーマチュア適用は体積を維持", default=True)
    keyframe_range: bpy.props.IntProperty(name="配置するキーフレームの範囲", description="比較用に元のレストポーズと交互に配置するキーフレームの範囲", default=10, min=2)
    revert_primed_pose: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        selected, ob = common.get_outliner_selection(context, 'ARMATURE')
        selected = [o for o in selected if o != ob]
        if ob and ob.type == 'ARMATURE' and len(selected) == 0:
            return True
        return False

    def draw(self, context):
        self.layout.prop(self, 'is_apply_armature_modifier')

        col = self.layout.column()
        col.enabled = self.is_apply_armature_modifier
        col.prop(self , 'is_preserve_shape_key_values')
        col.prop(self , 'is_deform_preserve_volume'   )
        if not self.revert_primed_pose:
            col.prop(self, 'keyframe_range')

    def execute(self, context):
        __, ob = common.get_outliner_selection(context, 'ARMATURE')
        arm = ob.data
        progress = 0

        pre_mode = ob.mode
        pre_hide = ob.hide_get()
        ob.hide_set(False)
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
            backup_attrs = ['name', 'show_expanded', 'show_in_editmode', 'show_on_cage', 'show_render',
                            'show_viewport', 'use_apply_on_spline', 'invert_vertex_group', 'use_bone_envelopes',
                            'use_vertex_groups', 'vertex_group']
            context.window_manager.progress_begin(0, len(ob.children) + 1)
            for child in ob.children:
                with context.temp_override(object=child, active_object=child):
                    if child.type == 'MESH' and len(child.modifiers) and bpy.ops.object.forced_modifier_apply.poll():
                        backup = {}
                        for mod in child.modifiers:
                            if mod.type == 'ARMATURE':
                                mod.use_deform_preserve_volume = self.is_deform_preserve_volume
                                if mod.object == ob:
                                    for attr in backup_attrs:
                                        backup[attr] = getattr(mod, attr)
                        apply_results = bpy.ops.object.forced_modifier_apply(apply_viewport_visible=True,
                                                                             is_preserve_shape_key_values=self.is_preserve_shape_key_values,
                                                                             initial_progress=progress)
                        if ('FINISHED' in apply_results) and backup:
                            new_mod = child.modifiers.new(name=backup['name'], type='ARMATURE')
                            new_mod.object = ob
                            new_mod.use_deform_preserve_volume = self.is_deform_preserve_volume
                            for attr in backup_attrs:
                                setattr(new_mod, attr, backup[attr])
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
            arm['isPrimedPose'] = False
        elif 'BoneData:0' in arm and 'LocalBoneData:0' in arm:
            # レストポーズ変更フラグ
            arm['isPrimedPose'] = True

            # 元のレストポーズを現ポーズとしてコピー導入(カスタムプロパティからの再現)
            copy_pose_from_property(ob)

            # キーフレーム利用の準備
            if not ob.animation_data:
                ob.animation_data_create()
            # 専用のアクション名で用意する
            action_name = f'{ob.name}_poses'
            action, __ = compat.get_new_action_and_fcurves(action_name, ob.name)
            action.use_fake_user = True
            ob.animation_data.action = action

            def insert_pose(ob, i):
                for bone in ob.pose.bones:
                    bone.keyframe_insert(data_path='location', frame=i, group=bone.name)
                    bone.keyframe_insert(data_path='rotation_euler', frame=i, group=bone.name)
                    bone.keyframe_insert(data_path='rotation_quaternion', frame=i, group=bone.name)
                    bone.keyframe_insert(data_path='scale', frame=i, group=bone.name)

            keys = range(self.keyframe_range)
            # 偶数フレームに元のレストポーズをポーズとして配置
            for i in filter(lambda x: x % 2 == 0, keys):
                insert_pose(ob, i)
            # 奇数フレームにレストポーズを配置
            bpy.ops.pose.transforms_clear()
            for i in filter(lambda x: x % 2 != 0, keys):
                insert_pose(ob, i)
            # レストポーズフレームに移動
            bpy.context.scene.frame_set(1)

        context.window_manager.progress_end()

        # 各種選択状態を戻す
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='DESELECT')
        compat.set_select_pose_bones(pre_selected_pose_bones)
        bpy.ops.object.mode_set(mode=pre_mode)
        ob.hide_set(pre_hide)

        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_prime_pose(CNV_OT_base_prime_pose_operator):
    bl_idname = 'pose.prime_pose'
    bl_label = "現在のポーズで素体化"
    bl_description = "現在のポーズで衣装をモデリングしやすくする素体を作成します"
    bl_options = {'REGISTER', 'UNDO'}


@compat.BlRegister()
class CNV_OT_revert_primed_pose(CNV_OT_base_prime_pose_operator):
    bl_idname = 'pose.revert_primed_pose'
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
    bone_data = export_model.bone_data_parser(export_model.indexed_data_generator(arm, prefix='BoneData:'))

    import_scale = arm.get('ImportScale', common.preferences().scale)

    global_fix_mat = mathutils.Matrix.Identity(4)

    for data in bone_data:
        if data['parent_index'] == -1:
            parent = None
        else:
            parent_name = bone_data[data['parent_index']]['name']
            parent = ob.pose.bones.get(common.decode_bone_name(parent_name, is_convert_bone_weight_names))

        bone = ob.pose.bones.get(common.decode_bone_name(data['name'], is_convert_bone_weight_names))

        local_co = mathutils.Vector(data['co'].copy()) * import_scale
        local_rot = mathutils.Quaternion(data['rot'].copy())
        local_co_mat = mathutils.Matrix.Translation(local_co)
        local_rot_mat = local_rot.to_matrix().to_4x4()
        local_mat = compat.mul(local_co_mat, local_rot_mat)
        local_mat = compat.convert_cm_to_bl_bone_space(local_mat)

        parent_matrix = parent.matrix if parent else global_fix_mat
        mat = compat.mul(parent_matrix, local_mat)
        mat = compat.convert_cm_to_bl_bone_rotation(mat)
        if not parent:
            mat = compat.fix_root_bone_rotation(mat)
            mat.translation = compat.convert_cm_to_bl_local_space(local_co)

        compat.set_bone_matrix(bone, mat)

        if 'scale' in data:
            bone['cm3d2_bone_scale'] = data['scale']
            scale = mathutils.Vector(data['scale'])
            scale *= import_scale * 0.01
            bone.bbone_x = scale.x
            bone.bbone_z = scale.z


class CNV_OT_set_frame(bpy.types.Operator):

    target_frame = 1

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        arm = ob.data
        return arm.get('isPrimedPose') and context.scene.frame_current % 2 != cls.target_frame % 2

    def execute(self, context):
        context.scene.frame_set(self.target_frame)
        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_set_original_rest_frame(CNV_OT_set_frame):
    bl_idname = 'pose.set_original_rest_frame'
    bl_label = "Original Rest"
    bl_description = "Moves to original rest pose frame"
    bl_options = {'REGISTER', 'UNDO'}
    target_frame = 0


@compat.BlRegister()
class CNV_OT_set_current_rest_frame(CNV_OT_set_frame):
    bl_idname = 'pose.set_current_rest_frame'
    bl_label = "Current Rest"
    bl_description = "Moves to current rest pose frame"
    bl_options = {'REGISTER', 'UNDO'}
    target_frame = 1
