from __future__ import annotations
import re
import struct
import math
from typing import Literal
import bpy
import mathutils
import os
from . import common
from . import compat
from . fileutil import deserialize_from_file
from . translations.pgettext_functions import *
from . common import CM3D2ImportError

from CM3D2.Serialization.Files import Anm  # type: ignore
from System import FormatException  # type: ignore


# メインオペレーター
@compat.BlRegister()
class CNV_OT_import_cm3d2_anm(bpy.types.Operator):
    bl_idname = 'import_anim.import_cm3d2_anm'
    bl_label = "CM3D2モーション (.anm)"
    bl_description = "カスタムメイド3D2のanmファイルを読み込みます"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filename_ext = '.anm'
    filter_glob: bpy.props.StringProperty(default='*.anm', options={'HIDDEN'})

    scale: bpy.props.FloatProperty(name="倍率", default=5, min=0.1, max=100, soft_min=0.1, soft_max=100, step=100, precision=1, description="インポート時のメッシュ等の拡大率です")
    set_frame_rate: bpy.props.BoolProperty(name="Set Framerate", default=True, description="Change the scene's render settings to 60 fps")
    is_loop: bpy.props.BoolProperty(name="Loop", default=True)

    is_anm_data_text: bpy.props.BoolProperty(name="Anm Text (SLOW)", default=False, description="Output Data to a JSON file")
    
    set_frame: bpy.props.BoolProperty(name="フレーム開始・終了位置を調整", default=True)
    ignore_automatic_bone: bpy.props.BoolProperty(name="Twisterボーンを除外", default=True)

    is_location: bpy.props.BoolProperty(name="Location", default=True)
    is_rotation: bpy.props.BoolProperty(name="Rotation", default=True)
    is_scale: bpy.props.BoolProperty(name="Scale", default=True)
    is_tangents: bpy.props.BoolProperty(name="Tangents", default=False)

    apply_as_pose: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        selected, _ = common.get_outliner_selection(context, 'ARMATURE')
        return bool(selected)

    def invoke(self, context, event):
        prefs = common.preferences()
        if prefs.anm_default_path:
            self.filepath = common.default_cm3d2_dir(prefs.anm_default_path, None, 'anm')
        else:
            self.filepath = common.default_cm3d2_dir(prefs.anm_import_path, None, 'anm')
        self.scale = prefs.scale
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        self.layout.prop(self, 'scale')
        self.layout.prop(self, 'set_frame_rate'  , icon='RENDER_ANIMATION')
        self.layout.prop(self, 'is_loop'         , icon='LOOP_BACK')
        self.layout.prop(self, 'is_anm_data_text', icon='TEXT')

        box = self.layout.box()
        box.prop(self, 'set_frame', icon='NEXT_KEYFRAME')
        box.prop(self, 'ignore_automatic_bone', icon='X')

        box = self.layout.box()
        box.label(text="読み込むアニメーション情報")
        column = box.column(align=True)
        column.prop(self, 'is_location', icon='CON_LOCLIKE')
        column.prop(self, 'is_rotation', icon='CON_ROTLIKE')
        column.prop(self, 'is_scale'   , icon='CON_SIZELIKE')
        column.prop(self, 'is_tangents', icon='IPO_BEZIER')

    def execute(self, context):
        prefs = common.preferences()
        prefs.anm_import_path = self.filepath
        prefs.scale = self.scale

        try:
            anm_importer = self.get_anm_importer()
            anm_importer.import_anm(context, self.filepath)
        except IOError:
            self.report(type={'ERROR'}, message=f_tip_("ファイルを開くのに失敗しました、アクセス不可かファイルが存在しません。file={}", self.filepath))
            return {'CANCELLED'}
        except CM3D2ImportError as ex:
            self.report(type={'ERROR'}, message=ex.message)
            return {'CANCELLED'}

        return {'FINISHED'}

    def get_anm_importer(self) -> AnmImporter:
        anm_importer = AnmImporter(reporter=self)

        anm_importer.scale                   = self.scale
        anm_importer.set_frame_rate          = self.set_frame_rate
        anm_importer.is_loop                 = self.is_loop
        anm_importer.is_anm_data_text        = self.is_anm_data_text
        anm_importer.set_frame               = self.set_frame
        anm_importer.ignore_automatic_bone   = self.ignore_automatic_bone
        anm_importer.is_location             = self.is_location
        anm_importer.is_rotation             = self.is_rotation
        anm_importer.is_scale                = self.is_scale
        anm_importer.is_tangents             = self.is_tangents
        anm_importer.apply_as_pose           = self.apply_as_pose

        return anm_importer


class AnmImporter:
    def __init__(self, reporter: bpy.types.Operator):
        self.reporter = reporter

        self.scale                   = 5
        self.set_frame_rate          = True
        self.is_loop                 = True
        self.is_anm_data_text        = False
        self.set_frame               = True
        self.ignore_automatic_bone   = True
        self.is_location             = True
        self.is_rotation             = True
        self.is_scale                = False
        self.is_tangents             = False
        self.apply_as_pose           = False

        self._keyframe_queue: dict[bpy.types.FCurve, list[tuple[tuple[float, float], str]]] = {}

    def import_anm(self, context: bpy.types.Context, filepath: str):
        target_objects, _ = common.get_outliner_selection(context, 'ARMATURE')
        for i, ob in enumerate(target_objects):
            # ポーズをいじった状態からインポートするとねじれが発生しうるのでレストポーズにクリアする
            self._transforms_clear(ob)
            if self.apply_as_pose:
                # ポーズ適用の場合はanmインポート先をコピーされた一時オブジェクトにする
                temp_ob = ob.copy()
                temp_ob.hide_set(False)
                compat.link(context.scene, temp_ob)
                # フレーム増減調整をやめる
                self.set_frame = False
                anm_data = self.read_anm_data(filepath, only_first_frame=True)
                with context.temp_override(active_object=temp_ob):
                    self._import_anm(context, anm_data, '__temp_action')
                # 適用した一時オブジェクトからポーズボーン情報をコピーする
                self._transforms_copy(src=temp_ob, dst=ob)
                # 一時オブジェクトを削除する
                common.remove_data(temp_ob)
            else:
                # 通常のanmインポート
                action_name = os.path.basename(filepath)
                anm_data = self.read_anm_data(filepath)
                with context.temp_override(active_object=ob):
                    self._import_anm(context, anm_data, action_name)

    @staticmethod
    def _transforms_clear(ob: bpy.types.Object):
        # ポースモードを使わずtransforms_clear()するのと同等の処理
        for bone in ob.pose.bones:
            bone.location = (0.0, 0.0, 0.0)
            if bone.rotation_mode == 'QUATERNION':
                bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            elif bone.rotation_mode == 'AXIS_ANGLE':
                bone.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
            else:
                bone.rotation_euler = (0.0, 0.0, 0.0)
            bone.scale = (1.0, 1.0, 1.0)

        bpy.context.view_layer.update()

    @staticmethod
    def _transforms_copy(src: bpy.types.Object, dst: bpy.types.Object):
        # 現在のポーズボーン情報を丸ごとコピー
        for src_bone, dst_bone in zip(src.pose.bones, dst.pose.bones):
            dst_bone.matrix_basis = src_bone.matrix_basis.copy()

        bpy.context.view_layer.update()

    def _import_anm(self, context: bpy.types.Context, anm_data: dict, action_name: str):
        if self.is_anm_data_text:
            self.import_anm_data_to_text(context, anm_data)

        if self.set_frame_rate:
            context.scene.render.fps = 60
        fps = context.scene.render.fps

        ob = context.active_object
        arm = ob.data
        pose = ob.pose
        base_bone = arm.get('BaseBone')
        if base_bone:
            base_bone = arm.bones.get(base_bone)

        anim = ob.animation_data
        if not anim:
            anim = ob.animation_data_create()
        action, fcurves = compat.get_new_action_and_fcurves(action_name, ob.name)
        anim.action = action

        max_frame = 0
        bpy.ops.object.mode_set(mode='OBJECT')
        found_unknown = []
        found_tangents = []
        
        self._keyframe_queue = {}
        
        for bone_name, bone_data in anm_data.items():
            if self.ignore_automatic_bone:
                if re.match(r'Kata_[RL]', bone_name):
                    continue
                if re.match(r'Uppertwist1_[RL]', bone_name):
                    continue
                if re.match(r'momoniku_[RL]', bone_name):
                    continue

            if bone_name not in pose.bones:
                bone_name = common.decode_bone_name(bone_name)
                if bone_name not in pose.bones:
                    continue
            bone = arm.bones[bone_name]
            pose_bone = pose.bones[bone_name]

            loc_fcurves  = None

            locs, loc_tangents, quats, quat_tangents, scls, scl_tangents, bone_found_unknown = \
                    self.get_bone_keyframe_data(found_unknown, bone_data)
            found_unknown.extend(bone_found_unknown)

            '''
            for frame, (loc, quat) in enumerate(zip(locs.values(), quats.values())):
                loc  = mathutils.Vector(loc) * self.scale
                quat = mathutils.Quaternion(quat)
            
                loc_mat = mathutils.Matrix.Translation(loc).to_4x4()
                rot_mat = quat.to_matrix().to_4x4()
                mat     = compat.mul(loc_mat, rot_mat)
                
                bone_loc  = bone.head_local.copy()
                bone_quat = bone.matrix.to_quaternion()
            
                if bone.parent:
                    parent = bone.parent
                else:
                    parent = base_bone
                    
                if parent:
                    mat = compat.convert_cm_to_bl_bone_space(mat)
                    mat = compat.mul(parent.matrix_local, mat)
                    mat = compat.convert_cm_to_bl_bone_rotation(mat)
                    pose_mat = bone.convert_local_to_pose(
                        matrix              = mat, 
                        matrix_local        = bone.matrix_local,
                        parent_matrix       = mathutils.Matrix.Identity(4),
                        parent_matrix_local = parent.matrix_local
                    )
                else:
                    mat = compat.convert_cm_to_bl_bone_rotation(mat)
                    mat = compat.convert_cm_to_bl_space(mat)
                    pose_mat = bone.convert_local_to_pose(
                        matrix       = mat, 
                        matrix_local = bone.matrix_local
                    )
            
                if self.is_location:
                    pose_bone.location = pose_mat.to_translation()
                    pose_bone.keyframe_insert('location'           , frame=frame * fps, group=pose_bone.name)
                if self.is_rotation:
                    pose_bone.rotation_quaternion = pose_mat.to_quaternion()
                    pose_bone.keyframe_insert('rotation_quaternion', frame=frame * fps, group=pose_bone.name)
                if max_frame < frame * fps:
                    max_frame = frame * fps
            '''            
            
            def _apply_tangents(fcurves, keyframes, tangents):
                for axis_index, axis_keyframes in enumerate(keyframes):
                    fcurve = fcurves[axis_index]
                    fcurve.update() # make sure automatic handles are calculated
                    axis_keyframes.sort() # make sure list is in order
                    for keyframe_index, frame in enumerate(axis_keyframes):
                        tangent_in  = tangents[frame]['in' ][axis_index]
                        tangent_out = tangents[frame]['out'][axis_index]

                        vec_in   = mathutils.Vector((1, tangent_in  / fps))   
                        vec_out  = mathutils.Vector((1, tangent_out / fps))

                        this_keyframe = fcurve.keyframe_points[keyframe_index  ]
                        next_keyframe = fcurve.keyframe_points[keyframe_index+1] if keyframe_index+1 < len(axis_keyframes) else None
                        last_keyframe = fcurve.keyframe_points[keyframe_index-1] if keyframe_index-1 >= 0                  else None
                        
                        if vec_in.y != vec_out.y:
                            this_keyframe.handle_left_type  = 'FREE'
                            this_keyframe.handle_right_type = 'FREE'
                        else:
                            this_keyframe.handle_left_type  = 'ALIGNED'
                            this_keyframe.handle_right_type = 'ALIGNED'

                        this_co = mathutils.Vector(this_keyframe.co)
                        next_co = mathutils.Vector(next_keyframe.co) if next_keyframe else None
                        last_co = mathutils.Vector(last_keyframe.co) if last_keyframe else None
                        if not next_keyframe:
                            next_keyframe = fcurve.keyframe_points[0]
                            if next_keyframe and next_keyframe != this_keyframe:
                                next_co = mathutils.Vector(next_keyframe.co)
                                next_co.x += max_frame
                        if not last_keyframe:
                            last_keyframe = fcurve.keyframe_points[len(axis_keyframes)-1]
                            if last_keyframe and last_keyframe != this_keyframe:
                                last_co = mathutils.Vector(last_keyframe.co)
                                last_co.x -= max_frame

                        factor = 3
                        dist_in  = (last_co.x - this_co.x) / factor if factor and last_co else None
                        dist_out = (next_co.x - this_co.x) / factor if factor and next_co else None
                        if not dist_in and not dist_out:
                            dist_in  = this_keyframe.handle_left[0]  - this_co.x
                            dist_out = this_keyframe.handle_right[0] - this_co.x
                        #elif not dist_in:
                        #    dist_in  = -dist_out
                        #elif not dist_out:
                        #    dist_out = -dist_in

                        this_keyframe.handle_left  = vec_in  * dist_in  + this_co
                        this_keyframe.handle_right = vec_out * dist_out + this_co


            if self.is_location:
                loc_fcurves = [None, None, None]
                loc_keyframes = [[],[],[]]
                rna_data_path = 'pose.bones["{bone_name}"].location'.format(bone_name=bone.name)
                for axis_index in range(0, 3):
                    new_fcurve = fcurves.find(rna_data_path, index=axis_index)
                    if not new_fcurve:
                        new_fcurve = compat.fcurves_new(fcurves, rna_data_path, index=axis_index, group_name=pose_bone.name)
                    loc_fcurves[axis_index] = new_fcurve
                
                def _convert_loc(loc) -> mathutils.Vector:
                    loc = mathutils.Vector(loc) * self.scale
                    #bone_loc = bone.head_local.copy()
                    #
                    #if bone.parent:
                    #    #loc.x, loc.y, loc.z = -loc.y, -loc.x, loc.z
                    #
                    #    #co.x, co.y, co.z = -co.y, co.z, co.x
                    #    #loc.x, loc.y, loc.z = loc.z, -loc.x, loc.y
                    #    #mat = mathutils.Matrix(
                    #    #    [( 0,  0,  1,  0), 
                    #    #     (-1,  0,  0,  0), 
                    #    #     ( 0,  1,  0,  0),
                    #    #     ( 0,  0,  0,  1)]
                    #    #)
                    #    #loc = compat.mul(mat, loc)
                    #
                    #    loc = compat.convert_cm_to_bl_bone_space(loc)
                    #
                    #    bone_loc = bone_loc - bone.parent.head_local
                    #    bone_loc.rotate(bone.parent.matrix_local.to_quaternion().inverted())
                    #else:
                    #    #loc.x, loc.y, loc.z = loc.x, loc.z, loc.y
                    #    loc = compat.convert_cm_to_bl_space(loc)
                    #
                    #result_loc = loc - bone_loc
                    if bone.parent:
                        loc = compat.convert_cm_to_bl_bone_space(loc)
                        loc = compat.mul(bone.parent.matrix_local, loc)
                    else:
                        loc = compat.convert_cm_to_bl_space(loc)
                    return compat.mul(bone.matrix_local.inverted(), loc)

                for time, loc in locs.items():
                    result_loc = _convert_loc(loc)
                    #pose_bone.location = result_loc

                    #pose_bone.keyframe_insert('location', frame=frame * fps, group=pose_bone.name)
                    if max_frame < time * fps:
                        max_frame = time * fps
     
                    for fcurve in loc_fcurves:
                        fcurve: bpy.types.FCurve
                        keyframe_type = 'KEYFRAME'
                        tangents = loc_tangents[time]
                        if tangents:
                            tangents = mathutils.Vector((tangents['in'][fcurve.array_index], tangents['out'][fcurve.array_index]))
                            if tangents.magnitude < 1e-6:
                                keyframe_type = 'JITTER'
                            elif tangents.magnitude > 0.1:
                                keyframe_type = 'EXTREME'

                        self._queue_append_keyframe(fcurve, time * fps, result_loc[fcurve.array_index], keyframe_type)                        
                        loc_keyframes[fcurve.array_index].append(time)

                self._create_keyframes_in_queue()
                
                if self.is_loop:
                    for fcurve in loc_fcurves:
                        new_modifier = fcurve.modifiers.new('CYCLES')

                if self.is_tangents:
                    for time, tangents in loc_tangents.items():
                        tangent_in  = mathutils.Vector(tangents['in' ]) * self.scale
                        tangent_out = mathutils.Vector(tangents['out']) * self.scale
                        if bone.parent:
                            tangent_in  = compat.convert_cm_to_bl_bone_space(tangent_in )
                            tangent_out = compat.convert_cm_to_bl_bone_space(tangent_out)
                        else:
                            tangent_in  = compat.convert_cm_to_bl_space(tangent_in )
                            tangent_out = compat.convert_cm_to_bl_space(tangent_out)
                        tangents['in' ][:] = tangent_in [:]
                        tangents['out'][:] = tangent_out[:]

                    _apply_tangents(loc_fcurves, loc_keyframes, loc_tangents)
                
                        
            
            
            if self.is_rotation:
                quat_fcurves = [None, None, None, None]
                quat_keyframes = [[],[],[],[]]
                rna_data_path = 'pose.bones["{bone_name}"].rotation_quaternion'.format(bone_name=pose_bone.name)
                for axis_index in range(0, 4):
                    new_fcurve = fcurves.find(rna_data_path, index=axis_index)
                    if not new_fcurve:
                        new_fcurve = compat.fcurves_new(fcurves, rna_data_path, index=axis_index, group_name=pose_bone.name)
                    quat_fcurves[axis_index] = new_fcurve


                bone_quat = bone.matrix.to_quaternion()
                def _convert_quat(quat) -> mathutils.Quaternion:
                    quat = mathutils.Quaternion(quat)
                    #orig_quat = quat.copy()
                    '''Can't use matrix transforms here as they would mess up interpolation.'''
                    if bone.parent:
                        quat.w, quat.x, quat.y, quat.z = quat.w, -quat.z, quat.x, -quat.y
                        #quat_mat = compat.convert_cm_to_bl_bone_space(quat.to_matrix().to_4x4())
                        #quat_mat = compat.convert_cm_to_bl_bone_rotation(quat_mat)
                    else:
                        quat.w, quat.x, quat.y, quat.z = quat.w, -quat.z, quat.x, -quat.y
                        quat = compat.mul(mathutils.Matrix.Rotation(math.radians(-90.0), 4, 'Z').to_quaternion(), quat)
                        #quat_mat = compat.convert_cm_to_bl_space(quat.to_matrix().to_4x4())
                        #quat = compat.convert_cm_to_bl_bone_rotation(quat_mat).to_quaternion()
                    quat = compat.mul(bone_quat.inverted(), quat)
                    #quat.make_compatible(orig_quat)
                    return quat
                        
                for time, quat in quats.items():
                    result_quat = _convert_quat(quat)
                    #pose_bone.rotation_quaternion = result_quat.copy()
            
                    #pose_bone.keyframe_insert('rotation_quaternion', frame=frame * fps, group=pose_bone.name)
                    if max_frame < time * fps:
                        max_frame = time * fps
                    
                    for fcurve in quat_fcurves:
                        fcurve: bpy.types.FCurve
                        keyframe_type = 'KEYFRAME'
                        tangents = quat_tangents[time]
                        if tangents:
                            tangents = mathutils.Vector((tangents['in'][fcurve.array_index], tangents['out'][fcurve.array_index]))
                            if tangents.magnitude < 1e-6:
                                keyframe_type = 'JITTER'
                            elif tangents.magnitude > 0.1:
                                keyframe_type = 'EXTREME'

                        self._queue_append_keyframe(fcurve, time * fps, result_quat[fcurve.array_index], keyframe_type)
                        quat_keyframes[fcurve.array_index].append(time)

                self._create_keyframes_in_queue()
                
                if self.is_loop:
                    for fcurve in quat_fcurves:
                        new_modifier = fcurve.modifiers.new('CYCLES')
                
                if self.is_tangents:
                    for time, tangents in quat_tangents.items():
                        tangents['in' ][:] = _convert_quat(tangents['in' ])[:]
                        tangents['out'][:] = _convert_quat(tangents['out'])[:]

                    _apply_tangents(quat_fcurves, quat_keyframes, quat_tangents)
                            



            if self.is_scale:
                scl_fcurves = [None, None, None]
                scl_keyframes = [[],[],[]]
                rna_data_path = 'pose.bones["{bone_name}"].scale'.format(bone_name=bone.name)
                for axis_index in range(0, 3):
                    new_fcurve = fcurves.find(rna_data_path, index=axis_index)
                    if not new_fcurve:
                        new_fcurve = compat.fcurves_new(fcurves, rna_data_path, index=axis_index, group_name=pose_bone.name)
                    scl_fcurves[axis_index] = new_fcurve
                
                def _convert_scl(scl) -> mathutils.Vector:
                    scl = mathutils.Vector(scl)
                    scl_mat: mathutils.Matrix = mathutils.Matrix.LocRotScale(
                        mathutils.Vector((0,0,0)), 
                        mathutils.Quaternion((1,0,0,0)), 
                        scl
                    )
                    if bone.parent:
                        pass
                        scl_mat = compat.convert_cm_to_bl_bone_space(scl_mat)
                        scl_mat = compat.mul(bone.parent.matrix_local, scl_mat)
                        scl_mat = compat.convert_cm_to_bl_bone_rotation(scl_mat)
                    else:
                        scl_mat = compat.convert_cm_to_bl_space(scl_mat)
                        scl_mat = compat.convert_cm_to_bl_bone_rotation(scl_mat)
                    scl_mat = compat.mul(bone.matrix_local.inverted(), scl_mat)
                    return scl_mat.to_scale()

                for time, scl in scls.items():
                    result_scl = _convert_scl(scl)
                    #pose_bone.location = result_loc

                    #pose_bone.keyframe_insert('location', frame=frame * fps, group=pose_bone.name)
                    if max_frame < time * fps:
                        max_frame = time * fps
     
                    for fcurve in scl_fcurves:
                        fcurve: bpy.types.FCurve
                        keyframe_type = 'KEYFRAME'
                        tangents = scl_tangents[time]
                        if tangents:
                            tangents = mathutils.Vector((tangents['in'][fcurve.array_index], tangents['out'][fcurve.array_index]))
                            if tangents.magnitude < 1e-6:
                                keyframe_type = 'JITTER'
                            elif tangents.magnitude > 0.1:
                                keyframe_type = 'EXTREME'

                        self._queue_append_keyframe(fcurve, time * fps, result_scl[fcurve.array_index], keyframe_type)                        
                        scl_keyframes[fcurve.array_index].append(time)

                self._create_keyframes_in_queue()
                
                if self.is_loop:
                    for fcurve in scl_fcurves:
                        new_modifier = fcurve.modifiers.new('CYCLES')

                if self.is_tangents:
                    for time, tangents in scl_tangents.items():
                        tangent_in  = mathutils.Vector(tangents['in' ]) * self.scale
                        tangent_out = mathutils.Vector(tangents['out']) * self.scale
                        if bone.parent:
                            tangent_in  = compat.convert_cm_to_bl_bone_space(tangent_in )
                            tangent_out = compat.convert_cm_to_bl_bone_space(tangent_out)
                        else:
                            tangent_in  = compat.convert_cm_to_bl_space(tangent_in )
                            tangent_out = compat.convert_cm_to_bl_space(tangent_out)
                        tangents['in' ][:] = tangent_in [:]
                        tangents['out'][:] = tangent_out[:]

                    _apply_tangents(scl_fcurves, scl_keyframes, scl_tangents)

        # 特に4.4/4.5は再代入しないと反映されないため
        anim.action = action

        if found_tangents:
            self.reporter.report(type={'INFO'}, message="Found the following tangent values:")
            for f1, f2 in found_tangents:
                self.reporter.report(type={'INFO'}, message=f_tip_('f1 = {float1}, f2 = {float2}', float1=f1, float2=f2))
            self.reporter.report(type={'INFO'}, message="Found the above tangent values.")  
            self.reporter.report(type={'WARNING'}, message=f_tip_("Found {count} large tangents. Blender animation may not interpolate properly. See log for more info.", count=len(found_tangents)))  
        if found_unknown:
            self.reporter.report(type={'INFO'}, message="Found the following unknown channel IDs:")
            for channel_id in found_unknown:
                self.reporter.report(type={'INFO'}, message=f_tip_('id = {id}', id=channel_id))
            self.reporter.report(type={'INFO'}, message="Found the above unknown channel IDs.")  
            self.reporter.report(type={'WARNING'}, message=f_tip_("Found {count} unknown channel IDs. Blender animation may be missing some keyframes. See log for more info.", count=len(found_unknown)))

        if self.set_frame:
            context.scene.frame_start = 0
            context.scene.frame_end = math.ceil(max_frame)
            context.scene.frame_set(0)

        bpy.context.view_layer.update()

    def get_bone_keyframe_data(self, found_unknown, bone_data):
        locs = {}
        loc_tangents = {}
        quats = {}
        quat_tangents = {}
        scls = {}
        scl_tangents = {}
        found_unknown = []
        
        for channel_id, channel_data in bone_data['channels'].items():
            rotIdTypes = [
                Anm.ChannelIdType.LocalRotationX,
                Anm.ChannelIdType.LocalRotationY,
                Anm.ChannelIdType.LocalRotationZ,
                Anm.ChannelIdType.LocalRotationW
            ]
            locIdTypes = [
                Anm.ChannelIdType.LocalPositionX,
                Anm.ChannelIdType.LocalPositionY,
                Anm.ChannelIdType.LocalPositionZ
            ]
            sclIdTypes = [
                Anm.ChannelIdType.ExLocalScaleX,
                Anm.ChannelIdType.ExLocalScaleY,
                Anm.ChannelIdType.ExLocalScaleZ
            ]
            
            if channel_id in rotIdTypes:
                for data in channel_data:
                    frame = data['frame']
                    if frame not in quats:
                        quats[frame] = [None, None, None, None]
                    if frame not in quat_tangents:
                        quat_tangents[frame] = {'in': [None, None, None, None], 'out': [None, None, None, None]}

                    if   channel_id == Anm.ChannelIdType.LocalRotationW:
                        quats        [frame]       [0] = data['f0']
                        quat_tangents[frame]['in' ][0] = data['f1']
                        quat_tangents[frame]['out'][0] = data['f2']
                    elif channel_id == Anm.ChannelIdType.LocalRotationX:
                        quats        [frame]       [1] = data['f0']
                        quat_tangents[frame]['in' ][1] = data['f1']
                        quat_tangents[frame]['out'][1] = data['f2']
                    elif channel_id == Anm.ChannelIdType.LocalRotationY:
                        quats        [frame]       [2] = data['f0']
                        quat_tangents[frame]['in' ][2] = data['f1']
                        quat_tangents[frame]['out'][2] = data['f2']
                    elif channel_id == Anm.ChannelIdType.LocalRotationZ:
                        quats        [frame]       [3] = data['f0']
                        quat_tangents[frame]['in' ][3] = data['f1']
                        quat_tangents[frame]['out'][3] = data['f2']        

            elif channel_id in locIdTypes:
                for data in channel_data:
                    frame = data['frame']
                    if frame not in locs:
                        locs[frame] = [None, None, None]
                    if frame not in loc_tangents:
                        loc_tangents[frame] = {'in': [None, None, None], 'out': [None, None, None]}

                    if   channel_id == Anm.ChannelIdType.LocalPositionX:
                        locs        [frame]       [0] = data['f0']
                        loc_tangents[frame]['in' ][0] = data['f1']
                        loc_tangents[frame]['out'][0] = data['f2']
                    elif channel_id == Anm.ChannelIdType.LocalPositionY:
                        locs        [frame]       [1] = data['f0']
                        loc_tangents[frame]['in' ][1] = data['f1']
                        loc_tangents[frame]['out'][1] = data['f2']
                    elif channel_id == Anm.ChannelIdType.LocalPositionZ:
                        locs        [frame]       [2] = data['f0']
                        loc_tangents[frame]['in' ][2] = data['f1']
                        loc_tangents[frame]['out'][2] = data['f2']
                        
            elif channel_id in sclIdTypes:
                for data in channel_data:
                    frame = data['frame']
                    if frame not in scls:
                        scls[frame] = [None, None, None]
                    if frame not in scl_tangents:
                        scl_tangents[frame] = {'in': [None, None, None], 'out': [None, None, None]}

                    if   channel_id == Anm.ChannelIdType.ExLocalScaleX:
                        scls        [frame]       [0] = data['f0']
                        scl_tangents[frame]['in' ][0] = data['f1']
                        scl_tangents[frame]['out'][0] = data['f2']
                    elif channel_id == Anm.ChannelIdType.ExLocalScaleY:
                        scls        [frame]       [1] = data['f0']
                        scl_tangents[frame]['in' ][1] = data['f1']
                        scl_tangents[frame]['out'][1] = data['f2']
                    elif channel_id == Anm.ChannelIdType.ExLocalScaleZ:
                        scls        [frame]       [2] = data['f0']
                        scl_tangents[frame]['in' ][2] = data['f1']
                        scl_tangents[frame]['out'][2] = data['f2']

            elif channel_id not in found_unknown:
                found_unknown.append(channel_id)
                self.reporter.report(type={'INFO'}, message=f_tip_("Unknown channel id {num}", num=channel_id))
                
        return locs, loc_tangents, quats, quat_tangents, scls, scl_tangents, found_unknown

    def import_anm_data_to_text(self, context, anm_data):
        if 'AnmData' in context.blend_data.texts:
            txt = context.blend_data.texts['AnmData']
            txt.clear()
        else:
            txt = context.blend_data.texts.new('AnmData')

        # json変換不能なキーが含まれているための調整
        serializable_anm_data =  {}
        for bone, data in anm_data.items():
            new_data = dict(data)
            if 'channels' in new_data:
                ch = new_data['channels']
                new_data['channels'] = {str(c): v for c, v in ch.items()}
            serializable_anm_data[bone] = new_data

        import json
        # XXX : CAUTION : XXX : This is EXTREMELY SLOW!!!
        txt.write( json.dumps(serializable_anm_data, ensure_ascii=False, indent=2) )

    def read_anm_data_OLD(self, file):
        ext = common.read_str(file)
        if ext != 'CM3D2_ANIM':
            raise CM3D2ImportError("これはカスタムメイド3D2のモーションファイルではありません")
        anm_version = struct.unpack('<i', file.read(4))[0]
        first_channel_id = struct.unpack('<B', file.read(1))[0]
        if first_channel_id != 1:
            raise CM3D2ImportError(f_tip_("Unexpected first channel id = {id} (should be 1).", id=first_channel_id))

        
        anm_data = {}
        for anim_data_index in range(9**9):
            path = common.read_str(file)
            
            base_bone_name = path.split('/')[-1]
            if base_bone_name not in anm_data:
                anm_data[base_bone_name] = {'path': path}
                anm_data[base_bone_name]['channels'] = {}

            for channel_index in range(9**9):
                channel_id = struct.unpack('<B', file.read(1))[0]
                channel_id_str = channel_id
                if channel_id <= 1:
                    break
                anm_data[base_bone_name]['channels'][channel_id_str] = []
                channel_data_count = struct.unpack('<i', file.read(4))[0]
                for channel_data_index in range(channel_data_count):
                    frame = struct.unpack('<f', file.read(4))[0]
                    data = struct.unpack('<3f', file.read(4 * 3))

                    anm_data[base_bone_name]['channels'][channel_id_str].append({'frame': frame, 'f0': data[0], 'f1': data[1], 'f2': data[2]})

            if channel_id == 0:
                break
        return anm_data

    def read_anm_data(self, filepath: str, only_first_frame: bool = False):
        anm_data = {}
        
        try:
            with open(filepath, 'rb') as file:
                anm = deserialize_from_file(Anm, file)
        except FormatException as ex:  # type: ignore
            raise CM3D2ImportError(ex.Message) from ex  # type: ignore
        
        ext = anm.signature
        anm_version = anm.version

        for track in anm.tracks:
            path = track.path

            base_bone_name = path.split('/')[-1]
            if base_bone_name not in anm_data:
                anm_data[base_bone_name] = {'path': path}
                anm_data[base_bone_name]['channels'] = {}

            for channel in track.channels:
                channel: Anm.Channel
                channel_id = channel.channelId
                channel_id_str = channel_id
                anm_data[base_bone_name]['channels'][channel_id_str] = []
                keyframes = [channel.keyframes[0]] if (only_first_frame and len(channel.keyframes)) else channel.keyframes
                for keyframe in keyframes:
                    keyframe: Anm.Keyframe
                    anm_data[base_bone_name]['channels'][channel_id_str].append({
                        'frame': keyframe.time,
                        'f0': keyframe.value,
                        'f1': keyframe.inTangent,
                        'f2': keyframe.outTangent
                    })

        return anm_data

    def _queue_append_keyframe(self, fcurve: bpy.types.FCurve, frame: float, value: float, 
                         keyframe_type: Literal['KEYFRAME', 'BREAKDOWN', 'MOVING_HOLD', 'EXTREME', 'JITTER']):
        # This is slow
        #keyframe = fcurve.keyframe_points.insert(
        #    frame         = frame * fps                     , 
        #    value         = result_quat[fcurve.array_index] , 
        #    options       = {'FAST'}                        , 
        #    keyframe_type = keyframe_type
        #)
        
        # This is faster
        if fcurve not in self._keyframe_queue.keys():
            self._keyframe_queue[fcurve] = []
        self._keyframe_queue[fcurve].append(((frame, value), keyframe_type))
        
    def _create_keyframes_in_queue(self):
        for fcurve, keyframe_data in self._keyframe_queue.items():
            fcurve.keyframe_points.add(len(keyframe_data))
            for keyframe, data in zip(fcurve.keyframe_points, keyframe_data):
                keyframe.co   = data[0]
                keyframe.type = data[1]
            fcurve.update()
        self._keyframe_queue.clear()
            


# メニューに登録する関数
def menu_func(self, context):
    self.layout.operator(CNV_OT_import_cm3d2_anm.bl_idname, icon_value=common.kiss_icon())
