import bpy
import bpy_extras
import mathutils
import inspect
from types import FunctionType
import functools
import warnings


IS_LT34 = not hasattr(bpy.app, 'version') or bpy.app.version < (3, 4)
IS_LT40 = not hasattr(bpy.app, 'version') or bpy.app.version < (4, 0)
IS_LT41 = not hasattr(bpy.app, 'version') or bpy.app.version < (4, 1)
IS_LT42 = not hasattr(bpy.app, 'version') or bpy.app.version < (4, 2)
IS_LT44 = not hasattr(bpy.app, 'version') or bpy.app.version < (4, 4)
IS_LT50 = not hasattr(bpy.app, 'version') or bpy.app.version < (5, 0)
IS_LT51 = not hasattr(bpy.app, 'version') or bpy.app.version < (5, 1)

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


def get_tex_image(context, node_name=None):
    mate = context.material
    if mate and mate.use_nodes:
        node = mate.node_tree.nodes.get(node_name)
        if node and node.type == 'TEX_IMAGE':
            return node.image

    return None


def set_show_bone_colors(arm: bpy.types.Armature, show: bool):
    if IS_LT40:
        arm.show_group_colors = show
    else:
        arm.show_bone_colors = show


def calc_normals_split(mesh: bpy.types.Mesh):
    # update automatically since Blender 4.1
    if IS_LT41:
        mesh.calc_normals_split()


def enable_use_auto_smooth(mesh: bpy.types.Mesh):
    if IS_LT41:
        mesh.use_auto_smooth = True


def new_socket(node_tree, name, in_out, socket_type):
    """ノードソケット生成の互換性サポート"""
    if IS_LT40:
        sockets = node_tree.inputs if in_out == 'INPUT' else node_tree.outputs
        return sockets.new(name=name, type=socket_type)
    else:
        return node_tree.interface.new_socket(name=name, in_out=in_out, socket_type=socket_type)


def map_shader_node(type, inputs: dict = None):
    """シェーダーノード扱いの互換性サポート"""
    socket_map = {}
    inputs = inputs if inputs is not None else {}
    if IS_LT50:
        if type == 'ShaderNodeBrightContrast':
            socket_map = {'Brightness': 'Bright'}
        elif type == 'ShaderNodeMixShader':
            socket_map = {'Factor': 'Fac'}
    if IS_LT40:
        if type == 'ShaderNodeAttribute':
            socket_map = {'Factor': 'Fac'}
    if IS_LT34:
        if type == 'ShaderNodeMix':
            type = 'ShaderNodeMixRGB'
            socket_map = {'Factor': 'Fac', 'A': 'Color1', 'B': 'Color2', 'Result': 'Color'}
            for key in ['A', 'B']:
                if key in inputs and isinstance(inputs[key], (int, float)):
                    inputs[key] = (inputs[key], inputs[key], inputs[key], 1.0)
    return type, socket_map, inputs


def set_transparent(mate: bpy.types.Material, transparent: bool):
    """透過モード切り替えの互換性サポート"""
    if transparent:
        # 5.1 で透過BSDF＋main/shadow塗分け・光沢BSDFの組み合わせで不透明部が黒や赤になる事象があり、やむを得ずディザとする
        mate.blend_method = 'BLEND' if IS_LT51 else 'HASHED'
    else:
        mate.blend_method = 'OPAQUE' if IS_LT42 else 'BLEND'

    # モード関係なく透過重ね合わせは基本的にONにしておき、透過ソート問題が起きる時のみ手動でOFFにしてもらう方針
    if IS_LT42:
        mate.show_transparent_back = True
    else:
        mate.use_transparency_overlap = True


def get_fcurves(action: bpy.types.Action, slot_name: str, clear: bool = False):
    """Fカーブリスト取得の互換性サポート"""
    if IS_LT44:
        fcurves = action.fcurves
        if clear:
            for fcurve in fcurves:
                fcurves.remove(fcurve)
        return fcurves
    else:
        if clear:
            for slot in action.slots:
                action.slots.remove(slot)
        slot = action.slots.get(slot_name)
        if not slot:
            slot = action.slots.new(name=slot_name, id_type='OBJECT')
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(action, slot)
        if not cb:
            if IS_LT50:
                layer = action.layers[0] if action.layers else action.layers.new(name=slot_name)
                strip = layer.strips[0] if layer.strips else layer.strips.new()
                cb = strip.channelbag(slot, ensure=True)
            else:
                cb = anim_utils.action_ensure_channelbag_for_slot(action, slot)
        return cb.fcurves


def fcurves_new(fcurves: bpy.types.FCurve, data_path: str, index: int = 0, group_name: str = ''):
    """Fカーブ生成の互換性サポート"""
    if IS_LT44:
        return fcurves.new(data_path=data_path, index=index, action_group=group_name)
    elif IS_LT50:
        return fcurves.new(data_path=data_path, index=index)
    else:
        return fcurves.new(data_path=data_path, index=index, group_name=group_name)


def get_selected_pose_bones(context: bpy.types.Context):
    """選択ポーズボーン取得の互換性サポート"""
    if IS_LT50:
        return context.selected_pose_bones
    else:
        return [b for o in context.selected_objects for b in o.pose.bones if b.select]


def set_select_pose_bones(bones: list[bpy.types.PoseBone], select: bool = True):
    """ポーズボーン選択の互換性サポート"""
    for bone in bones:
        if IS_LT50:
            bone.bone.select = select
        else:
            bone.select = select
