# 「3Dビュー」エリア → 「ポーズ」パネル
import bpy
import os
import pickle
from . import common
from . import compat
from .cm3d2_data import ArcHandler
from .common import POSE_DATA_DIR


POSE_LIST = {}


@compat.BlRegister()
class CNV_PT_control_primed_pose(bpy.types.Panel):
    bl_label = "ポーズ素体化"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Pose"

    def draw(self, context):
        row = self.layout.row(align = True)
        col = row.column()
        col.operator('pose.prime_pose')
        col.enabled = bpy.ops.pose.prime_pose.poll()
        col = row.column()
        col.operator('pose.revert_primed_pose')

        _, ob = common.get_outliner_selection(context, 'ARMATURE')
        # チェック対象がexecuteで変更される関係でpollでチェックさせるとREDOできなくなるため、ここで有効無効を切り替える
        if not ob or not ob.data.get('isPrimedPose'):
            col.enabled = False


@compat.BlRegister()
class CNV_PT_poselib_props(bpy.types.PropertyGroup):

    def on_import_type_changed(self, context):
        if self.import_type == 'STANCE':
            self.apply_type = 'POSE'
            self.play_animation = False
        else:
            self.apply_type, self.play_animation = self.prev_values[self.import_type]
        self.prev_values[self.import_type] = [self.apply_type, self.play_animation]

    def on_apply_type_changed(self, context):
        if self.apply_type == 'POSE':
            self.play_animation = False
        else:
            self.play_animation = self.prev_values[self.import_type][1]
        self.prev_values[self.import_type][0] = self.apply_type

    def on_play_animation_changed(self, context):
        if self.apply_type == 'ANIMATION':
            self.prev_values[self.import_type][1] = self.play_animation

    import_type_items = [
        ('STANCE', "スタンス", ""),
        ('CM3D2_POSE', "CM3D2ポーズ", ""),
        ('MY_POSE', "MyPose", ""),
    ]
    import_type: bpy.props.EnumProperty(name="ポーズ種別", items=import_type_items, default='STANCE', update=on_import_type_changed)
    apply_type_items = [
        ('ANIMATION', "アニメーション", "アニメーションをインポートします。オブジェクトに既存アニメーションがあれば差し替えます。"),
        ('POSE', "ポーズ", "アニメーションの初期フレームをポーズとして取り込みます。既存アニメーションがあっても影響ありませんが再生すると取り込んだポーズは失われます。"),
    ]
    apply_type: bpy.props.EnumProperty(name="適用方法", items=apply_type_items, default='POSE', update=on_apply_type_changed)
    play_animation: bpy.props.BoolProperty(name="適用と同時に再生する", default=False, update=on_play_animation_changed)

    prev_values = {'STANCE': ['POSE', False],
                   'CM3D2_POSE': ['ANIMATION', True],
                   'MY_POSE': ['POSE', False]}


@compat.BlRegister()
class CNV_OT_set_active_pose(bpy.types.Operator):
    bl_idname = 'pose.set_active_pose'
    bl_label = "Set Active Pose"
    bl_options = {'INTERNAL'}
    bl_description = "ポーズを適用します"

    index: bpy.props.IntProperty()

    def execute(self, context):
        set_pose(context.active_object, self.index)
        return {'FINISHED'}


@compat.BlRegister()
class CNV_PT_poselib(bpy.types.Panel):
    bl_label = "Pose Library"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Pose"

    def draw(self, context):
        layout = self.layout
        selected, ob = common.get_outliner_selection(context, 'ARMATURE')

        if not selected:
            layout.label(text="アーマチュアを選択してください", icon='INFO')
            return

        is_included_primed = any(x.data.get('isPrimedPose') for x in selected)
        if is_included_primed:
            layout.label(text="選択オブジェクトに素体ポーズ変更", icon='ERROR')
            layout.label(text="されているものがあります", icon='BLANK1')
            layout.label(text="元の素体ポーズでないと利用できません", icon='BLANK1')
            return

        if not ob:
            ob = selected[0]

        props = context.scene.poselib_props
        layout.prop(props, 'import_type', expand=True)
        col = layout.column()
        col.prop(props, 'apply_type')
        col.enabled = props.import_type != 'STANCE'
        col = layout.column()
        col.prop(props, 'play_animation')
        col.enabled = props.apply_type == 'ANIMATION'

        if props.import_type not in POSE_LIST:
            reload_pose_list(props.import_type)

        if props.import_type == 'STANCE':
            col.enabled = False
            row = layout.split(factor=0.4, align=True)
            row.label(text="ポーズ選択")
            row.template_icon_view(ob, f'pose_{props.import_type}', show_labels=False, scale=3.0, scale_popup=2.5)
        elif props.import_type == 'CM3D2_POSE':
            row = layout.split(factor=0.4, align=True)
            row.label(text="ポーズ選択")
            row.template_icon_view(ob, f'pose_{props.import_type}', show_labels=False, scale=3.0, scale_popup=2.5)
        elif props.import_type == 'MY_POSE':
            layout.label(text="ポーズ選択")
            grid = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=True, align=False)
            grid.operator_context = 'EXEC_DEFAULT'
            for i, (anm_path, idx, anm, *_) in enumerate(POSE_LIST.get(props.import_type, [])):
                col = grid.column()
                op = col.operator('pose.set_active_pose', text=anm)
                op.index = i


def reload_pose_list(import_type: str, force: bool = False):
    """
    COM3D2/CM3D2からのポーズ取り込みの更新
    """
    if import_type == 'MY_POSE':
        my_pose_dir = common.get_my_pose_path()
        my_pose_list = []
        for file in os.listdir(my_pose_dir):
            if file.endswith('.anm'):
                my_pose_list.append((None, None, os.path.splitext(file)[0], os.path.join(my_pose_dir, file)))
        POSE_LIST[import_type] = build_enum_pose_list(my_pose_list)

    elif import_type == 'STANCE':
        stance_dir = os.path.join(str(os.path.dirname(__file__)), 'poses')
        stance_list = [
            ('pose_d', os.path.join(stance_dir, 'pose_d.png'), "D-Stance", os.path.join(stance_dir, 'pose_d.anm')),
            ('pose_t', os.path.join(stance_dir, 'pose_t.png'), "T-Stance", os.path.join(stance_dir, 'pose_t.anm')),
            ('pose_a', os.path.join(stance_dir, 'pose_a.png'), "A-Stance", os.path.join(stance_dir, 'pose_a.anm')),
        ]
        POSE_LIST[import_type] = build_enum_pose_list(stance_list)

    elif import_type == 'CM3D2_POSE':
        cache_file = os.path.join(POSE_DATA_DIR, '__pose_list.pkl')
        if not force and os.path.exists(cache_file):
            POSE_LIST[import_type] = build_enum_pose_list(pickle.load(open(cache_file, 'rb')))
            return

        if not os.path.exists(POSE_DATA_DIR):
            os.makedirs(POSE_DATA_DIR)

        wm = bpy.context.window_manager
        wm.progress_begin(0, 5)

        # CM3D2/COM3D2 フォルダ内arcより、エディット用標準ポーズリストを抽出
        ah = ArcHandler
        ah.extract('csv.arc', output_dir=POSE_DATA_DIR, target_files=['edit_pose.nei'], force=force)

        # 標準ポーズリストを解析して、ksファイル・ポーズ名のリストを取得
        ks_poses = {}
        with open(os.path.join(POSE_DATA_DIR, 'edit_pose.nei.pkl'), mode='rb') as f:
            edit_poses = pickle.load(f)[1:]
        is_com3d2 = len(edit_poses[0]) == 6
        for item in edit_poses:
            if is_com3d2:
                _, icon, _, ks, pose, _ = item
            else:
                icon, _, ks, pose = item
            if ks not in ks_poses:
                ks_poses[ks] = []
            ks_poses[ks].append((pose, icon))
        wm.progress_update(1)

        # arcより指定ksファイルを抽出、解析してポーズ名よりanmファイル名を取得
        pose_list = []
        ah.extract('script.*.arc', output_dir=POSE_DATA_DIR, target_files=list(ks_poses.keys()), force=force)
        for ks, poses in ks_poses.items():
            ks_path = os.path.join(POSE_DATA_DIR, ks + '.pkl')
            if not os.path.exists(ks_path):
                continue
            with open(ks_path, mode='rb') as f:
                ks_data = pickle.load(f)
            for (pose, icon) in poses:
                if pose in ks_data:
                    if '@Motion' not in ks_data[pose]:
                        pose += 'x'
                    if '@Motion' in ks_data[pose]:
                        anm = ks_data[pose]['@Motion'][0]['mot']
                        pose_list.append((icon, anm.lower()))
        wm.progress_update(2)

        # arcよりポーズアイコンtexを抽出
        icon_arc = 'system.*.arc' if is_com3d2 else 'texture.*.arc'
        ah.extract(icon_arc, output_dir=POSE_DATA_DIR, target_files=[x[0] for x in pose_list])
        wm.progress_update(3)

        # arcよりポーズanmを抽出
        ah.extract('motion*.arc', output_dir=POSE_DATA_DIR, target_files=[f'{x[1]}.anm' for x in pose_list])
        wm.progress_update(4)

        # 所持していると確認できるものをリスト化、アイコンはpreview collectionに登録
        owned_list = []
        for icon, anm in pose_list:
            png_path = os.path.join(POSE_DATA_DIR, os.path.splitext(icon)[0] + '.png')
            anm_file = f'{anm}.anm'
            anm_path = os.path.join(POSE_DATA_DIR, anm_file)
            if os.path.exists(png_path) and os.path.exists(anm_path):
                owned_list.append((icon, png_path, anm, anm_path))  # anm_file))
        pickle.dump(owned_list, open(cache_file, 'wb'))

        POSE_LIST[import_type] = build_enum_pose_list(owned_list)
        wm.progress_end()


def build_enum_pose_list(pose_list: list) -> list:
    """
    ポーズリスト用アイコンのpreview_collection構成とEnumPropertyリストの構築
    """
    pcoll = common.preview_collections.get('pose')
    if pcoll is None:
        pcoll = bpy.utils.previews.new()
        common.preview_collections['pose'] = pcoll

    enum_list = []
    for idx, (icon, png_path, anm, anm_file) in enumerate(pose_list):
        if icon and png_path:
            try:
                pcoll.load(icon, png_path, 'IMAGE', force_reload=True)
            except KeyError:
                pass
            enum_list.append((anm_file, str(idx+1), anm, pcoll[icon].icon_id, idx))
        else:
            enum_list.append((anm_file, str(idx+1), anm))
    return enum_list


_monitored_objects = set()
_is_processing = False


def enum_poses(ob, context) -> list:
    """
    template_icon_viewでのアイコンメニューリスト返却用コールバック
    """
    props = bpy.context.scene.poselib_props
    enum_list = POSE_LIST.get(props.import_type, [])
    return enum_list


def get_pose(ob) -> int:
    """
    template_icon_viewでのアイコンメニュー表示用コールバック
    """
    props = bpy.context.scene.poselib_props
    enum_list = POSE_LIST.get(props.import_type)
    if props.apply_type == 'POSE':
        anm_path = ob.data.get('_LastPose')
        enum_ids = [i for i, (key, *_) in enumerate(enum_list) if key == anm_path]
        if enum_ids:
            return enum_ids[0]
    if ob.animation_data and ob.animation_data.action:
        enum_ids = [i for i, (key, *_) in enumerate(enum_list) if
                    os.path.basename(key) == ob.animation_data.action.name]
        if enum_ids:
            return enum_ids[0]
    return -1


def set_pose(ob, value: int):
    """
    template_icon_viewでのアイコンメニュー表示から選択したときのコールバック
    """
    props = bpy.context.scene.poselib_props
    enum_list = POSE_LIST.get(props.import_type)
    keys = [key for i, (key, *_) in enumerate(enum_list) if i == value]
    if not keys:
        return
    anm_path = keys[0]

    # 再生中なら止める
    if bpy.context.screen.is_animation_playing:
        bpy.ops.screen.animation_cancel(restore_frame=False)
        # NOTE: 3.3, 3.4 だとアニメーション停止からのポーズ適用は1発で反映されない(Blender側のバグ)

    selected, _ = common.get_outliner_selection(bpy.context, 'ARMATURE')

    if props.apply_type == 'POSE':
        _is_processing = True
        # ポーズとして適用の場合
        bpy.ops.import_anim.import_cm3d2_anm(filepath=anm_path, apply_as_pose=True)
        # 選択ポーズのカスタムプロパティ記録と今後のポーズ変更検知でクリアする仕込み
        for ob in selected:
            ob.data['_LastPose'] = anm_path
            _monitored_objects.add(ob.name)
        _is_processing = False
        common.handler_append(bpy.app.handlers.frame_change_post, frame_change_handler)
        common.handler_append(bpy.app.handlers.depsgraph_update_post, pose_change_handler)

    else:
        for ob in selected:
            if '_LastPose' in ob.data:
                del ob.data['_LastPose']
            if ob.name in _monitored_objects:
                _monitored_objects.remove(ob.name)
        # アニメーションとして適用の場合
        bpy.ops.import_anim.import_cm3d2_anm(filepath=anm_path)
        if props.play_animation:
            # 再生する場合はフレーム0に戻して再生
            bpy.context.scene.frame_set(0)
            bpy.ops.screen.animation_play()


def pose_change_handler(scene, depsgraph):
    """
    ポーズ反映からのポーズ変更により一時ポーズ消失の監視。ポーズアイコンを表示しなくするためのもの。
    """
    if not depsgraph.id_type_updated('OBJECT'):
        return
    if _is_processing:
        return
    for update in depsgraph.updates:
        if update.id.name in _monitored_objects:
            if update.is_updated_transform:
                try:
                    _monitored_objects.remove(update.id.name)
                except ValueError:
                    continue
    if not _monitored_objects:
        common.handler_remove(bpy.app.handlers.depsgraph_update_post, pose_change_handler)


def frame_change_handler(scene):
    """
    ポーズ反映からのフレーム変更により一時ポーズ消失の監視。ポーズアイコンを表示しなくするためのもの。
    """
    if _is_processing:
        return
    for ob_name in _monitored_objects:
        ob = bpy.data.objects.get(ob_name)
        if '_LastPose' in ob.data:
            del ob.data['_LastPose']
    _monitored_objects.clear()
    if not _monitored_objects:
        common.handler_remove(bpy.app.handlers.frame_change_post, frame_change_handler)


def register():
    bpy.types.Object.pose_STANCE = bpy.props.EnumProperty(items=enum_poses, get=get_pose, set=set_pose)
    bpy.types.Object.pose_CM3D2_POSE = bpy.props.EnumProperty(items=enum_poses, get=get_pose, set=set_pose)
    bpy.types.Scene.poselib_props = bpy.props.PointerProperty(type=CNV_PT_poselib_props)


def unregister():
    del bpy.types.Object.pose_STANCE
    del bpy.types.Object.pose_CM3D2_POSE
    del bpy.types.Scene.poselib_props
    common.handler_remove(bpy.app.handlers.frame_change_post, frame_change_handler)
    common.handler_remove(bpy.app.handlers.depsgraph_update_post, pose_change_handler)
