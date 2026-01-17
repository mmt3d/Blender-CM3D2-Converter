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


UILayoutDrawer = bpy.types.Header | bpy.types.Menu | bpy.types.Panel


class BlRegister:
    classes: list[type] = []
    functions: dict[type[UILayoutDrawer], list[FunctionType]] = {}
    
    def __init__(self, append_to: type[UILayoutDrawer] = None):
        self.append_to = append_to

    def __call__(self, obj: type | FunctionType) -> object:
        """This method is invoked when using the decorator @BlRegister()"""
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
    return layout.split(factor=factor, align=align)


def get_active():
    return bpy.context.view_layer.objects.active

def get_active(context):
    return context.view_layer.objects.active


def set_active(context, obj):
    context.view_layer.objects.active = obj


def get_active_uv(me):
    uvs = me.uv_layers
    return uvs.active


def set_display_type(ob, disp_type):
    ob.display_type = disp_type


def get_select(obj: bpy.types.Object) -> bool:
    return obj.select_get()


def set_select(obj: bpy.types.Object, select: bool) -> None:
    obj.select_set(select)


def is_select(*args) -> bool:
    """すべてが選択状態であるかを判定する."""
    return all(arg.select_get() for arg in args)


def get_hide(obj: bpy.types.Object) -> bool:
    return obj.hide_viewport


def set_hide(obj: bpy.types.Object, hide: bool):
    obj.hide_viewport = hide


def link(scene: bpy.types.Scene, obj: bpy.types.Object):
    if bpy.context.collection:
        bpy.context.collection.objects.link(obj)
    else:
        scene.collection.objects.link(obj)


def unlink(scene: bpy.types.Scene, obj: bpy.types.Object):
    for collection in obj.users_collection:
        collection.objects.unlink(obj)


def get_cursor_loc(context):
    return context.scene.cursor.location


def get_lights(blend_data):
    return blend_data.lights


def mul(x, y):
    return x @ y


def mul3(x, y, z):
    return x @ y @ z


def mul4(w, x, y, z):
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
    if isinstance(bone, bpy.types.EditBone):
        #print("Bone align_roll: ", (mat[0][0],mat[1][0],mat[2][0]))
        bone.align_roll((mat[0][2],mat[1][2],mat[2][2]))
    #print("bone: ", bone.matrix)
    #print("mat:  ", mat)


def region_type():
    return 'UI'


def pref_type():
    return 'PREFERENCES'


def get_prefs(context):
    return context.preferences


def get_system(context):
    return get_prefs(context).view


def get_tex_image(context, node_name=None):
    mate = context.material
    if mate and mate.use_nodes:
        node = mate.node_tree.nodes.get(node_name)
        if node and node.type == 'TEX_IMAGE':
            return node.image

    return None
