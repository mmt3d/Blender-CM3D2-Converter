# -*- coding: utf-8 -*-
import bpy
import bpy_extras
import re
import struct
import os
import mathutils
import traceback
import numpy as np
import inspect
from typing import Any, Optional, Callable, Protocol, TypeVar, ParamSpec, TYPE_CHECKING
from types import FunctionType
import functools


# LEGAY: version less than 2.80
IS_LEGACY = not hasattr(bpy.app, 'version') or bpy.app.version < (2, 80)

UILayoutDrawer = bpy.types.Header | bpy.types.Menu | bpy.types.Panel


class BlRegister:
    classes: list[type] = []
    functions: dict[type[UILayoutDrawer], list[FunctionType]] = {}
    
    def __init__(self, append_to: type[UILayoutDrawer] = None, only_legacy: bool = False, **kwargs):
        self.append_to = append_to
        self.only_legacy = only_legacy

    def __call__(self, obj: type | FunctionType) -> object:
        """This method is invoked when using the decorator @BlRegister()"""
        if self.only_legacy:
            return obj
        if inspect.isclass(obj):
            BlRegister.classes.append(obj)
        elif inspect.isfunction(obj):
            if self.append_to not in BlRegister.functions:
                BlRegister.functions[self.append_to] = []
            BlRegister.functions[self.append_to].append(obj)
        return obj
    
    @classmethod
    def register(cls):
        for cls1 in cls.classes:
            bpy.utils.register_class(cls1)
        for ui_layout_drawer, draw_functions in cls.functions.items():
            for func in draw_functions:
                ui_layout_drawer.append(func)

    @classmethod
    def unregister(cls):
        for cls1 in reversed(cls.classes):
            bpy.utils.unregister_class(cls1)
        for ui_layout_drawer, draw_functions in cls.functions.items():
            for func in draw_functions:
                ui_layout_drawer.remove(func)

    @classmethod
    def cleanup(cls):
        cls.classes.clear()
        cls.functions.clear()


import functools
import inspect
import warnings

string_types = (type(b''), type(u''))


def deprecated(target_or_reason: str | type | FunctionType):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    
    The ``@deprecated`` decorator is used either with a reason...
    ```
    @deprecated("please, use another function")
    def old_function(x, y):
        pass
    ```
    ...or without a reason
    ```
    @deprecated
    def old_function(x, y):
        pass
    ```
    """
    target = None
    reason = None
    if isinstance(target_or_reason, str):
        reason = target_or_reason
    elif inspect.isclass(target_or_reason) or inspect.isfunction(target_or_reason):
        target = target_or_reason
    else:
        raise TypeError(repr(type(target_or_reason)))
        
    def decorator(func):
        if inspect.isclass(func):
            msg = f"Call to deprecated class {func.__name__}."
        else:
            msg = f"Call to deprecated function {func.__name__}."
        if reason is not None:
            msg += f" {reason}"
        @functools.wraps(func)
        def func_wrapper(*args, **kwargs):
            warnings.simplefilter('always', DeprecationWarning)
            warnings.warn(msg, category=DeprecationWarning, stacklevel=2)
            warnings.simplefilter('default', DeprecationWarning)
            return func(*args, **kwargs)
        return func_wrapper
    
    if reason is not None:
        return decorator
    elif target is not None:
        return decorator(target)
    else:
        raise TypeError(repr(type(target_or_reason)))



def layout_split(layout, factor=0.0, align=False):
    if IS_LEGACY:
        return layout.split(percentage=factor, align=align)

    return layout.split(factor=factor, align=align)


def get_active():
    if IS_LEGACY:
        return bpy.context.scene.objects.active

    return bpy.context.view_layer.objects.active

def get_active(context):
    if IS_LEGACY:
        return context.scene.objects.active

    return context.view_layer.objects.active


def set_active(context, obj):
    if IS_LEGACY:
        context.scene.objects.active = obj
    else:
        context.view_layer.objects.active = obj


def get_active_uv(me):
    if IS_LEGACY:
        uvs = me.uv_textures
    else:
        uvs = me.uv_layers
    return uvs.active


def set_display_type(ob, disp_type):
    if IS_LEGACY:
        ob.draw_type = disp_type
    else:
        ob.display_type = disp_type


def get_select(obj: bpy.types.Object) -> bool:
    if IS_LEGACY:
        return obj.select

    return obj.select_get()


def set_select(obj: bpy.types.Object, select: bool) -> None:
    if IS_LEGACY:
        obj.select = select
    else:
        obj.select_set(select)


def is_select(*args) -> bool:
    """すべてが選択状態であるかを判定する."""
    if IS_LEGACY:
        return all(arg.select for arg in args)

    return all(arg.select_get() for arg in args)


def get_hide(obj: bpy.types.Object) -> bool:
    if IS_LEGACY:
        return obj.hide

    return obj.hide_viewport


def set_hide(obj: bpy.types.Object, hide: bool):
    if IS_LEGACY:
        obj.hide = hide

    else:
        obj.hide_viewport = hide


def link(scene: bpy.types.Scene, obj: bpy.types.Object):
    if IS_LEGACY:
        scene.objects.link(obj)
    elif bpy.context.collection:
        bpy.context.collection.objects.link(obj)
    else:
        scene.collection.objects.link(obj)


def unlink(scene: bpy.types.Scene, obj: bpy.types.Object):
    if IS_LEGACY:
        scene.objects.unlink(obj)
    else:
        for collection in obj.users_collection:
            collection.objects.unlink(obj)


def get_cursor_loc(context):
    if IS_LEGACY:
        return context.space_data.cursor_location
    else:
        return context.scene.cursor.location


def get_lights(blend_data):
    if IS_LEGACY:
        return blend_data.iamps
    else:
        return blend_data.lights


def mul(x, y):
    if IS_LEGACY:
        return x * y

    return x @ y


def mul3(x, y, z):
    if IS_LEGACY:
        return x * y * z

    return x @ y @ z


def mul4(w, x, y, z):
    if IS_LEGACY:
        return w * x * y * z

    return w @ x @ y @ z

def transform_inverse(m: mathutils.Matrix) -> mathutils.Matrix:
    """Returns the inverse of a 4x4 transformation matrix
    with the translation handled properly"""
    inv_m = m.copy()
    inv_m.translation = mathutils.Vector((0,0,0))
    inv_m.invert()
    inv_m.translation = mul(inv_m.to_3x3(), -m.translation)
    return inv_m


CM_TO_BL_SPACE_MAT4 = mul(
    bpy_extras.io_utils.axis_conversion(from_forward='Z', from_up='Y', to_forward='-Y', to_up='Z').to_4x4(),
    mathutils.Matrix.Scale(-1, 4, (1, 0, 0))
)
BL_TO_CM_SPACE_MAT4 = CM_TO_BL_SPACE_MAT4.inverted()
CM_TO_BL_SPACE_QUAT = CM_TO_BL_SPACE_MAT4.to_quaternion()
BL_TO_CM_SPACE_QUAT = BL_TO_CM_SPACE_MAT4.to_quaternion()
def convert_cm_to_bl_space(x, lossless=True):
    if type(x) == mathutils.Quaternion:
        raise TypeError('Quaternion space conversions not supported')
    elif lossless and type(x) == mathutils.Vector:
        return mathutils.Vector((-x.x, -x.z, x.y))
    else:
        return mul(CM_TO_BL_SPACE_MAT4, x)
def convert_bl_to_cm_space(x, lossless=True):
    if type(x) == mathutils.Quaternion:
        raise TypeError('Quaternion space conversions not supported')
    elif lossless and len(x) == 3:
        return mathutils.Vector((-x[0], x[2], -x[1]))
    else:
        return mul(BL_TO_CM_SPACE_MAT4, x)
def convert_cm_to_bl_local_space(x):
    if type(x) == mathutils.Quaternion:
        raise TypeError('Quaternion space conversions not supported')
    else:
        return mul(x, BL_TO_CM_SPACE_MAT4)
def convert_bl_to_cm_local_space(x):
    if type(x) == mathutils.Quaternion:
        raise TypeError('Quaternion space conversions not supported')
    else:
        return mul(x, CM_TO_BL_SPACE_MAT4)


CM_TO_BL_BONE_ROTATION_MAT4 = mul(
    bpy_extras.io_utils.axis_conversion(from_forward='Z', from_up='-X', to_forward='Y', to_up='Z').to_4x4(),
    mathutils.Matrix.Scale(-1, 4, (1, 0, 0))
)
BL_TO_CM_BONE_ROTATION_MAT4 = CM_TO_BL_BONE_ROTATION_MAT4.inverted()
CM_TO_BL_BONE_ROTATION_QUAT = CM_TO_BL_BONE_ROTATION_MAT4.to_quaternion()
BL_TO_CM_BONE_ROTATION_QUAT = BL_TO_CM_BONE_ROTATION_MAT4.to_quaternion()
def convert_cm_to_bl_bone_rotation(x):
    if type(x) == mathutils.Quaternion:
        raise TypeError('Quaternion space conversions not supported')
    else:
        return mul(x, CM_TO_BL_BONE_ROTATION_MAT4)
def convert_bl_to_cm_bone_rotation(x):
    if type(x) == mathutils.Quaternion:
        raise TypeError('Quaternion space conversions not supported')
    else:
        return mul(x, BL_TO_CM_BONE_ROTATION_MAT4)


#CM_TO_BL_BONE_SPACE_MAT4 = mul(
#    bpy_extras.io_utils.axis_conversion(from_forward='-X', from_up='Y', to_forward='Y', to_up='Z').to_4x4(),
#    mathutils.Matrix.Scale(-1, 4, (0, 0, 1))
#)
CM_TO_BL_BONE_SPACE_MAT4 = CM_TO_BL_BONE_ROTATION_MAT4.inverted()
BL_TO_CM_BONE_SPACE_MAT4 = CM_TO_BL_BONE_SPACE_MAT4.inverted()
CM_TO_BL_BONE_SPACE_QUAT = CM_TO_BL_BONE_SPACE_MAT4.to_quaternion()
BL_TO_CM_BONE_SPACE_QUAT = BL_TO_CM_BONE_SPACE_MAT4.to_quaternion()
def convert_cm_to_bl_bone_space(x):
    if type(x) == mathutils.Quaternion:
        raise TypeError('Quaternion space conversions not supported')
    else:
        return mul(CM_TO_BL_BONE_SPACE_MAT4, x)
def convert_bl_to_cm_bone_space(x):
    if type(x) == mathutils.Quaternion:
        raise TypeError('Quaternion space conversions not supported')
    else:
        return mul(BL_TO_CM_BONE_SPACE_MAT4, x)


CM_TO_BL_WIDE_SLIDER_SPACE_MAT4 = mul(
    bpy_extras.io_utils.axis_conversion(from_forward='X', from_up='Y', to_forward='Y', to_up='Z').to_4x4(),
    mathutils.Matrix.Scale(-1, 4, (0, 1, 0))
)
BL_TO_CM_WIDE_SLIDER_SPACE_MAT4 = CM_TO_BL_WIDE_SLIDER_SPACE_MAT4.inverted()
CM_TO_BL_WIDE_SLIDER_SPACE_QUAT = CM_TO_BL_WIDE_SLIDER_SPACE_MAT4.to_quaternion()
BL_TO_CM_WIDE_SLIDER_SPACE_QUAT = BL_TO_CM_WIDE_SLIDER_SPACE_MAT4.to_quaternion()
def convert_cm_to_bl_wide_slider_space(x):
    if type(x) == mathutils.Quaternion:
        raise TypeError('Quaternion space conversions not supported')
    else:
        return mul(CM_TO_BL_WIDE_SLIDER_SPACE_MAT4, x)
def convert_bl_to_cm_wide_slider_space(x):
    if type(x) == mathutils.Quaternion:
        raise TypeError('Quaternion space conversions not supported')
    else:
        return mul(BL_TO_CM_WIDE_SLIDER_SPACE_MAT4, x)


CM_TO_BL_SLIDER_SPACE_MAT4 = bpy_extras.io_utils.axis_conversion(from_forward='X', from_up='Y', to_forward='Y', to_up='Z').to_4x4()
BL_TO_CM_SLIDER_SPACE_MAT4 = CM_TO_BL_SLIDER_SPACE_MAT4.inverted()
CM_TO_BL_SLIDER_SPACE_QUAT = CM_TO_BL_SLIDER_SPACE_MAT4.to_quaternion()
BL_TO_CM_SLIDER_SPACE_QUAT = BL_TO_CM_SLIDER_SPACE_MAT4.to_quaternion()
def convert_cm_to_bl_slider_space(x):
    if type(x) == mathutils.Quaternion:
        raise TypeError('Quaternion space conversions not supported')
    else:
        return mul(CM_TO_BL_SLIDER_SPACE_MAT4, x)
def convert_bl_to_cm_slider_space(x):
    if type(x) == mathutils.Quaternion:
        raise TypeError('Quaternion space conversions not supported')
    else:
        return mul(BL_TO_CM_SLIDER_SPACE_MAT4, x)



def set_bone_matrix(bone, mat):
    bone.matrix = mat.copy()
    #axis, angle = mat.to_quaternion().to_axis_angle()
    #bone.roll = angle
    if not IS_LEGACY and isinstance(bone, bpy.types.EditBone):
        #print("Bone align_roll: ", (mat[0][0],mat[1][0],mat[2][0]))
        bone.align_roll((mat[0][2],mat[1][2],mat[2][2]))
    #print("bone: ", bone.matrix)
    #print("mat:  ", mat)


BL28_TO_LEGACY_ICON = {
    # Renamed in 2.80               
    'ADD'                          : 'ZOOMIN'             ,  
    'REMOVE'                       : 'ZOOMOUT'            ,  
    'FILE_NEW'                     : 'NEW'                ,  
    'SHADING_BBOX'                 : 'BBOX'               ,  
    'SHADING_TEXTURE'              : 'POTATO'             , #'TEXTURE_SHADED',  
    'SHADING_RENDERED'             : 'SMOOTH'             ,  
    'SHADING_SOLID'                : 'SOLID'              ,  
    'SHADING_WIRE'                 : 'WIRE'               ,  
    'XRAY'                         : 'ORTHO'              ,  
    'PROPERTIES'                   : 'BUTS'               ,  
    'IMAGE'                        : 'IMAGE_COL'          ,  
    'OUTLINER'                     : 'OOPS'               ,  
    'GRAPH'                        : 'IPO'                ,  
    'PREFERENCES'                  : 'SCRIPTWIN'          ,  
    'PIVOT_CURSOR'                 : 'CURSOR'             ,  
    'PIVOT_INDIVIDUAL'             : 'ROTATECOLLECTION'   ,  
    'PIVOT_MEDIAN'                 : 'ROTATECENTER'       ,  
    'PIVOT_ACTIVE'                 : 'ROTACTIVE'          ,  
    'WINDOW'                       : 'FULLSCREEN'         ,  
    'LIGHT'                        : 'LAMP'               ,  
    'LIGHT_DATA'                   : 'LAMP_DATA'          ,  
    'OUTLINER_OB_LIGHT'            : 'OUTLINER_OB_LAMP'   ,  
    'OUTLINER_DATA_LIGHT'          : 'OUTLINER_DATA_LAMP' ,  
    'LIGHT_POINT'                  : 'LAMP_POINT'         ,  
    'LIGHT_SUN'                    : 'LAMP_SUN'           ,  
    'LIGHT_SPOT'                   : 'LAMP_SPOT'          ,  
    'LIGHT_HEMI'                   : 'LAMP_HEMI'          ,  
    'LIGHT_AREA'                   : 'LAMP_AREA'          ,  
    'HIDE_OFF'                     : 'VISIBLE_IPO_ON'     ,  
    'HIDE_ON'                      : 'VISIBLE_IPO_OFF'    ,  

    # Added in 2.80
    'ALEMBIC'                      : None                 ,
    'ALIGN_BOTTOM'                 : None                 ,  
    'ALIGN_CENTER'                 : None                 ,  
    'ALIGN_FLUSH'                  : None                 ,  
    'ALIGN_JUSTIFY'                : None                 ,  
    'ALIGN_LEFT'                   : None                 ,  
    'ALIGN_MIDDLE'                 : None                 ,  
    'ALIGN_RIGHT'                  : None                 ,  
    'ALIGN_TOP'                    : None                 ,  
    'ASSET_MANAGER'                : None                 ,  
    'BOLD'                         : None                 ,  
    'DECORATE'                     : None                 ,  
    'DECORATE_ANIMATE'             : None                 ,  
    'DECORATE_DRIVER'              : None                 ,  
    'DECORATE_KEYFRAME'            : None                 ,  
    'DECORATE_LIBRARY_OVERRIDE'    : None                 ,  
    'DECORATE_LINKED'              : None                 ,  
    'DECORATE_LOCKED'              : None                 ,  
    'DECORATE_OVERRIDE'            : None                 ,  
    'DECORATE_UNLOCKED'            : None                 ,  
    'DRIVER_DISTANCE'              : None                 ,  
    'DRIVER_ROTATIONAL_DIFFERENCE' : None                 ,  
    'DRIVER_TRANSFORM'             : None                 ,  
    'DUPLICATE'                    : None                 ,  
    'FACE_MAPS'                    : None                 ,
    'FAKE_USER_OFF'                : None                 ,
    'FAKE_USER_ON'                 : None                 ,
    'GP_MULTIFRAME_EDITING'        : None                 ,
    'GP_ONLY_DSELECTED'            : None                 ,
    'GP_SELECT_POINTS'             : None                 ,
    'GP_SELECT_STROKES'            : None                 ,
    'GREASEPENCIL'                 : None                 ,
    'HEART'                        : None                 ,
    'ITALIC'                       : None                 ,
    'LIBRARY_DATA_OVERRIDE'        : None                 ,
    'LIGHTPROBE_CUBEMAP'           : None                 ,
    'LIGHTPROBE_GRID'              : None                 ,
    'LIGHTPROBE_PLANAR'            : None                 ,
    'LINE_DATA'                    : None                 ,
    'MATCLOTH'                     : None                 ,
    'MATFLUID'                     : None                 ,
    'MATSHADERBALL'                : None                 ,
    'MOD OPACITY'                  : None                 ,
    'MOD_HUE_SATURATION'           : None                 ,
    'MOD_INSTANCE'                 : None                 ,
    'MOD_NOISE'                    : None                 ,
    'MOD_OFFSET'                   : None                 ,
    'MOD_PARTICLE_INSTANCE'        : None                 ,
    'MOD_SIMPLIFY'                 : None                 ,
    'MOD_THICKNESS'                : None                 ,
    'MOD_TIME'                     : None                 ,
    'MODIFIER_OFF'                 : None                 ,
    'MODIFIER_ON'                  : None                 ,
    'MOUSE_LMB'                    : None                 ,
    'MOUSE_LMB_DRAG'               : None                 ,
    'MOUSE_MMB'                    : None                 ,
    'MOUSE_MMB_DRAG'               : None                 ,
    'MOUSE_MOVE'                   : None                 ,
    'MOUSE_RMB'                    : None                 ,
    'MOUSE_RMB_DRAG'               : None                 ,
    'NORMALS_FACE'                 : None                 ,
    'NORMALS_VERTEX'               : 'MATCAP_23'          ,
    'NORMALS_VERTEX_FACE'          : 'MATCAP_23'          ,
    'OBJECT_ORIGIN'                : None                 ,
    'ONIONSKIN_OFF'                : None                 ,
    'ONIONSKIN_ON'                 : None                 ,
    'ORIENTATION_GIMBAL'           : None                 ,
    'ORIENTATION_GLOBAL'           : None                 ,
    'ORIENTATION_LOCAL'            : None                 ,
    'ORIENTATION_NORMAL'           : None                 ,
    'ORIENTATION_VIEW'             : None                 ,
    'OUTLINER_DATA_GREASEPENCIL'   : None                 ,
    'OUTLINER_OB_IMAGE'            : None                 ,
    'OUTLINER_OB_LIGHTPROBE'       : None                 ,
    'OVERLAY'                      : None                 ,
    'PRESET'                       : None                 ,
    'PRESET_NEW'                   : None                 ,
    'SEALED'                       : None                 ,
    'SETTINGS'                     : None                 ,
    'SHADERFX'                     : None                 ,
    'SMALL_CAPS'                   : None                 ,
    'SYSTEM'                       : None                 ,
    'THREE_DOTS'                   : None                 ,
    'TOOL_SETTINGS'                : None                 ,
    'TRACKING'                     : None                 ,

    # Other
    #'ARROW_LEFTRIGHT'              : 'MAN_SCALE'         ,
    #'FILE_FOLDER'                  : 'FILESEL'           ,
    #'FILEBROWSER'                  : 'FILESEL'           ,
    #'FILE_IMAGE'                   : 'IMAGE_COL'         ,
    #'MOD_DATA_TRANSFER'            : 'RETOPO'            ,
    #'BRUSH_SOFTEN'                 : 'MATCAP_19'         ,
    #'CLIPUV_DEHLT'                 : 'MATCAP_24'         ,
    #'MESH_CIRCLE'                  : 'MATCAP_24'         ,
    #'VIS_SEL_01'                   : 'VISIBLE_IPO_OFF'   ,
    #'VIS_SEL_11'                   : 'VISIBLE_IPO_ON'    ,
    #'BRUSH_TEXFILL'                : 'MATCAP_05'         ,
    #'NODE_MATERIAL'                : 'MATCAP_05'         ,
    #'HOLDOUT_ON'                   : 'MATCAP_13'         ,
}

LEGACY_TO_BL28_ICON = {
    # Renamed in 2.80
    'ZOOMIN'                       : 'ADD'                ,  
    'ZOOMOUT'                      : 'REMOVE'             ,  
    'NEW'                          : 'FILE_NEW'           ,  
    'BBOX'                         : 'SHADING_BBOX'       ,  
    'POTATO'                       : 'SHADING_TEXTURE'    , #'TEXTURE_SHADED',  
    'SMOOTH'                       : 'SHADING_RENDERED'   ,  
    'SOLID'                        : 'SHADING_SOLID'      ,  
    'WIRE'                         : 'SHADING_WIRE'       ,  
    'ORTHO'                        : 'XRAY'               ,  
    'BUTS'                         : 'PROPERTIES'         ,  
    'IMAGE_COL'                    : 'IMAGE'              ,  
    'OOPS'                         : 'OUTLINER'           ,  
    'IPO'                          : 'GRAPH'              ,  
    'SCRIPTWIN'                    : 'PREFERENCES'        ,  
    'CURSOR'                       : 'PIVOT_CURSOR'       ,  
    'ROTATECOLLECTION'             : 'PIVOT_INDIVIDUAL'   ,  
    'ROTATECENTER'                 : 'PIVOT_MEDIAN'       ,  
    'ROTACTIVE'                    : 'PIVOT_ACTIVE'       ,  
    'FULLSCREEN'                   : 'WINDOW'             ,  
    'LAMP'                         : 'LIGHT'              ,  
    'LAMP_DATA'                    : 'LIGHT_DATA'         ,  
    'OUTLINER_OB_LAMP'             : 'OUTLINER_OB_LIGHT'  ,  
    'OUTLINER_DATA_LAMP'           : 'OUTLINER_DATA_LIGHT',  
    'LAMP_POINT'                   : 'LIGHT_POINT'        ,  
    'LAMP_SUN'                     : 'LIGHT_SUN'          ,  
    'LAMP_SPOT'                    : 'LIGHT_SPOT'         ,  
    'LAMP_HEMI'                    : 'LIGHT_HEMI'         ,  
    'LAMP_AREA'                    : 'LIGHT_AREA'         ,  
    'VISIBLE_IPO_ON'               : 'HIDE_OFF'           ,  
    'VISIBLE_IPO_OFF'              : 'HIDE_ON'            ,  
                                                          
    # Removed in 2.80              
    'LINK_AREA'                    : 'LINKED'             ,
    'PLUG'                         : 'PLUGIN'             ,
    'EDIT'                         : None                 , 
    'GAME'                         : None                 , 
    'RADIO'                        : None                 ,
    'DOTSUP'                       : 'DOT'                ,
    'DOTSDOWN'                     : 'DOT'                ,
    'LINK'                         : 'LAYER_USED'         , #(maybe use DOT, LAYER_ACTIVE or LAYER_USED)
    'INLINK'                       : None                 ,  
    'GO_LEFT'                      : None                 ,
    'TEMPERATURE'                  : None                 ,
    'SNAP_SURFACE'                 : None                 ,
    'MANIPUL'                      : None                 ,
    'BORDER_LASSO'                 : None                 ,
    'MAN_TRANS'                    : None                 ,
    'MAN_ROT'                      : None                 ,
    'MAN_SCALE'                    : None                 ,
    'RENDER_REGION'                : None                 ,
    'RECOVER_AUTO'                 : None                 ,
    'SAVE_COPY'                    : None                 ,
    'OPEN_RECENT'                  : None                 ,
    'LOAD_FACTORY'                 : None                 ,
    'ALIGN'                        : None                 ,
    'SPACE2'                       : None                 ,
    'ROTATE'                       : None                 ,
    'SAVE_AS'                      : None                 ,
    'BORDER_RECT'                  : None                 ,
}                                                          

def icon(key):
    if IS_LEGACY:
        # 対応アイコンがdictにない場合はNONEとする
        return BL28_TO_LEGACY_ICON.get(key, key) or 'NONE'
    else:
        return LEGACY_TO_BL28_ICON.get(key, key) or 'NONE'
        
    return key


def region_type():
    if IS_LEGACY:
        return 'TOOLS'

    return 'UI'


def pref_type():
    if IS_LEGACY:
        return 'USER_PREFERENCES'

    return 'PREFERENCES'


def get_prefs(context):
    if IS_LEGACY:
        return context.user_preferences

    return context.preferences


def get_system(context):
    if IS_LEGACY:
        return get_prefs(context).system

    return get_prefs(context).view


def get_tex_image(context, node_name=None):
    if IS_LEGACY:
        if hasattr(context, 'texture'):
            tex = context.texture
            if tex:
                return tex.image
    else:
        mate = context.material
        if mate and mate.use_nodes:
            node = mate.node_tree.nodes.get(node_name)
            if node and node.type == 'TEX_IMAGE':
                return node.image

    return None



# Property Subtypes
# Blender 2.91 = [‘NONE’, ‘FILEPATH’ , ‘DIRPATH’ , ‘FILENAME’, ‘BYTESTRING’, ‘PASSWORD’, ‘PIXEL’, ‘UNSIGNED’, ‘PERCENTAGE’, ‘FACTOR’, ‘ANGLE’, ‘TIME’, ‘DISTANCE’, ‘DISTANCE_CAMERA’, ‘POWER’, ‘TEMPERATURE’, ‘COLOR’, ‘TRANSLATION’, ‘DIRECTION’, ‘VELOCITY’, ‘ACCELERATION’, ‘MATRIX’, ‘EULER’, ‘QUATERNION’, ‘AXISANGLE’, ‘XYZ’, ‘XYZ_LENGTH’, ‘COLOR_GAMMA’, ‘COORDS’     , ‘LAYER’, ‘LAYER_MEMBER’    ]
# Blender 2.80 = [‘NONE’, ‘FILE_PATH’, ‘DIR_PATH’,                                       ‘PIXEL’, ‘UNSIGNED’, ‘PERCENTAGE’, ‘FACTOR’, ‘ANGLE’, ‘TIME’, ‘DISTANCE’,                                            ‘COLOR’, ‘TRANSLATION’, ‘DIRECTION’,                             ‘MATRIX’, ‘EULER’, ‘QUATERNION’,              ‘XYZ’,               ‘COLOR_GAMMA’, ‘COORDINATES’, ‘LAYER’, ‘LAYER_MEMBERSHIP’]
# Blender 2.78 = [‘NONE’, ‘FILE_PATH’, ‘DIR_PATH’,                                       ‘PIXEL’, ‘UNSIGNED’, ‘PERCENTAGE’, ‘FACTOR’, ‘ANGLE’, ‘TIME’, ‘DISTANCE’,                                            ‘COLOR’, ‘TRANSLATION’, ‘DIRECTION’,                             ‘MATRIX’, ‘EULER’, ‘QUATERNION’,              ‘XYZ’,               ‘COLOR_GAMMA’, ‘COORDINATES’, ‘LAYER’, ‘LAYER_MEMBERSHIP’]

BL29_TO_BL28_SUBTYPE = {
    #'NONE'           : 'NONE'            ,
    'FILEPATH'        : 'FILE_PATH'       ,
    'DIRPATH'         : 'DIR_PATH'        ,
    'FILENAME'        : None              ,
    'BYTESTRING'      : None              ,
    'PASSWORD'        : None              ,
    #'PIXEL'          : 'PIXEL'           ,
    #'UNSIGNED'       : 'UNSIGNED'        ,
    #'PERCENTAGE'     : 'PERCENTAGE'      ,
    #'FACTOR'         : 'FACTOR'          ,
    #'ANGLE'          : 'ANGLE'           ,
    #'TIME'           : 'TIME'            ,
    #'DISTANCE'       : 'DISTANCE'        , 
    'DISTANCE_CAMERA' : 'DISTANCE'        , 
    'POWER'           : None              , 
    'TEMPERATURE'     : None              , 
    #'COLOR'          : 'COLOR'           , 
    #'TRANSLATION'    : 'TRANSLATION'     , 
    #'DIRECTION'      : 'DIRECTION'       , 
    'VELOCITY'        : 'XYZ'             , 
    'ACCELERATION'    : 'XYZ'             , 
    #'MATRIX'         : 'MATRIX'          , 
    #'EULER'          : 'EULER'           , 
    #'QUATERNION'     : 'QUATERNION'      , 
    'AXISANGLE'       : 'XYZ'             , 
    #'XYZ'            : 'XYZ'             , 
    'XYZ_LENGTH'      : 'XYZ'             , 
    #'COLOR_GAMMA'    : 'COLOR_GAMMA'     , 
    'COORDS'          : 'COORDINATES'     , 
    #'LAYER'          : 'LAYER'           , 
    'LAYER_MEMBER'    : 'LAYER_MEMBERSHIP', 
}

def subtype(key):
    if bpy.app.version < (2, 91):
        return BL29_TO_BL28_SUBTYPE.get(key, key) or 'NONE'
    return key


# Property Units
# Blender 2.91 = [‘NONE’, ‘LENGTH’, ‘AREA’, ‘VOLUME’, ‘ROTATION’, ‘TIME’, ‘VELOCITY’, ‘ACCELERATION’, ‘MASS’, ‘CAMERA’, ‘POWER’, ‘TEMPERATURE’]
# Blender 2.80 = [‘NONE’, ‘LENGTH’, ‘AREA’, ‘VOLUME’, ‘ROTATION’, ‘TIME’, ‘VELOCITY’, ‘ACCELERATION’, ‘MASS’, ‘CAMERA’, ‘POWER’]
# Blender 2.78 = [‘NONE’, ‘LENGTH’, ‘AREA’, ‘VOLUME’, ‘ROTATION’, ‘TIME’, ‘VELOCITY’, ‘ACCELERATION’,         ‘CAMERA’]

BL29_TO_LEGACY_UNIT = {
    'MASS'        : None,
    'POWER'       : None,
    'TEMPERATURE' : None,
}

BL29_TO_BL28_UNIT = {
    'TEMPERATURE' : None,
}

def unit(key):
    if IS_LEGACY:
        return BL29_TO_LEGACY_UNIT.get(key, key) or 'NONE'
    elif bpy.app.version < (2, 91):
        return BL29_TO_BL28_UNIT.get(key, key) or 'NONE'
    return key