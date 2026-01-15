# 「プロパティ」エリア → 「メッシュデータ」タブ → 「頂点グループ」パネル → ▼ボタン
import time
import bpy
import bmesh
import mathutils
from . import common
from . import compat
from .translations.pgettext_functions import *


# メニュー等に項目追加
def menu_func(self, context):
    icon_id = common.kiss_icon()
    self.layout.separator()
    self.layout.operator('geometry.attribute_from_custom_normals', icon_value=icon_id)
    if (self.__class__.__name__ == 'MESH_MT_attribute_context_menu'):
        self.layout.operator('geometry.attribute_convert_normals', icon_value=icon_id)
    #self.layout.operator('geometry.attribute_from_custom_normals', icon_value=compat.icon('NORMALS_VERTEX_FACE'))


@compat.BlRegister()
class CNV_OT_attribute_from_custom_normals(bpy.types.Operator):
    bl_idname = 'geometry.attribute_from_custom_normals'
    bl_label = "From Custom Normals"
    bl_description = "Creates a new attribute from the custom split normals"
    bl_options = {'REGISTER', 'UNDO'}

    items = [
        ('FLOAT_VECTOR', "Vector"     , "3D vector with floating point values"     , 'NONE', 1),
        ('FLOAT_COLOR' , "Float Color", "RGBA color with floating point precisions", 'NONE', 2),
        ('BYTE_COLOR'  , "Byte Color" , "RGBA color with 8-bit precision"          , 'NONE', 3),
    ]

    data_type: bpy.props.EnumProperty(items=items, name="Data Type", default='FLOAT_COLOR')

    @classmethod
    def poll(cls, context):
        obs = context.selected_objects
        active_ob = context.active_object
        if active_ob.type != 'MESH':
            return False
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'data_type')
        pass

    def execute(self, context):
        ob = context.active_object
        me = ob.data

        pre_mode = ob.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        me.calc_normals_split()

        attribute = me.attributes.new('custom_normals', self.data_type, 'CORNER')

        for key in attribute.data.keys():
            print(repr(key))

        for loop_index, loop in enumerate(me.loops):
            if isinstance(attribute, bpy.types.FloatVectorAttribute):
                attribute.data[loop_index].vector = loop.normal
            else:
                attribute.data[loop_index].color = ( # convert from range(-1, 1) to range(0, 1)
                    loop.normal[0] * 0.5 + 0.5,
                    loop.normal[1] * 0.5 + 0.5,
                    loop.normal[2] * 0.5 + 0.5,
                    1,
                )

        
        
        bpy.ops.object.mode_set(mode=pre_mode)
        return {'FINISHED'}

@compat.BlRegister()
class CNV_OT_attribute_convert_normals(bpy.types.Operator):
    bl_idname = 'geometry.attribute_convert_normals'
    bl_label = "Convert Normals"
    bl_description = "Converts the data type of the normals attribute"
    bl_options = {'REGISTER', 'UNDO'}

    items = [
        ('FLOAT_VECTOR', "Vector"     , "3D vector with floating point values"     , 'NONE', 1),
        ('FLOAT_COLOR' , "Float Color", "RGBA color with floating point precisions", 'NONE', 2),
        ('BYTE_COLOR'  , "Byte Color" , "RGBA color with 8-bit precision"          , 'NONE', 3),
    ]

    data_type: bpy.props.EnumProperty(items=items, name="Data Type", default='FLOAT_COLOR')

    @classmethod
    def poll(cls, context):
        obs = context.selected_objects
        active_ob = context.active_object
        if active_ob.type != 'MESH':
            return False
        return True

    def invoke(self, context, event):
        me = context.active_object.data

        if isinstance(me.attributes.active, bpy.types.FloatVectorAttribute):
            self.data_type = 'FLOAT_COLOR'
        else:
            self.data_type = 'FLOAT_VECTOR'

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'data_type')
        pass

    def execute(self, context):
        ob = context.active_object
        me = ob.data

        pre_mode = ob.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        old_attribute = me.attributes.active
        name = old_attribute.name

        old_data = [None] * len(me.loops)

        # store old data
        for loop_index, loop in enumerate(me.loops):
            if isinstance(old_attribute, bpy.types.FloatVectorAttribute):
                old_data[loop_index] = old_attribute.data[loop_index].vector
            else:
                color = old_attribute.data[loop_index].color
                old_data[loop_index] = ( # convert from range (0, 1) to range (-1, 1)
                    (color[0] - 0.5) / 0.5,
                    (color[1] - 0.5) / 0.5,
                    (color[2] - 0.5) / 0.5,
                )
        
        # create new attribute
        new_attribute = me.attributes.new(f'temp_{name}', self.data_type, 'CORNER')

        # set new data
        for loop_index, loop in enumerate(me.loops):
            old_loop_data = old_data[loop_index]
            if isinstance(new_attribute, bpy.types.FloatVectorAttribute):
                new_attribute.data[loop_index].vector = old_loop_data
            else:
                new_attribute.data[loop_index].color = ( # convert from range(-1, 1) to range(0, 1)
                    old_loop_data[0] * 0.5 + 0.5,
                    old_loop_data[1] * 0.5 + 0.5,
                    old_loop_data[2] * 0.5 + 0.5,
                    1,
                )
        
        # delete old attribute
        me.attributes.remove(me.attributes[name])

        # restore state
        new_attribute.name = name
        bpy.ops.object.mode_set(mode=pre_mode)
        return {'FINISHED'}