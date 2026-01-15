import numpy as np
import bpy
import bmesh
from . import common
from . import compat

@compat.deprecated("The operator this menu displayed is obsolete since Blender 3.3.")
#@compat.BlRegister(append_to=bpy.types.VIEW3D_MT_edit_mesh_merge)
def menu_func(self, context):
    icon_id = common.kiss_icon()
    self.layout.separator()
    self.layout.label(text="CM3D2", icon_value=icon_id)
    self.layout.operator('mesh.remove_and_mark_doubles')

@compat.deprecated("This operator is obsolete since Blender 3.3.")
#@compat.BlRegister()
class CNV_OT_remove_and_mark_doubles(bpy.types.Operator):
    bl_idname = 'mesh.remove_and_mark_doubles'
    bl_label = "Remove and Mark Doubles"
    bl_description = "Remove doubles while marking merged geometry as seams and/or sharp edges"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: bpy.props.FloatProperty(name="Merge Distance", default=0.0001, description="Maximum distance between elements to merge")
    normal_threshold: bpy.props.FloatProperty(name="Normal Angle", default=0.0000, description="Maximum angle between element's normals to mark sharp")
    use_unselected: bpy.props.BoolProperty(name="Unselected", default=False, description="Merge selected to other unselected vertices")
    keep_custom_normals: bpy.props.BoolProperty(name="Keep Custom Normals", default=True, description="Keep custom split normals")
    mark_sharp: bpy.props.BoolProperty(name="Mark Sharp", default=True, description="Mark sharp")
    
    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.type == 'MESH' and ob.mode == 'EDIT'

    def execute(self, context):
        ob = context.active_object
        me = ob.data
        bm = bmesh.from_edit_mesh(me)

        selected_verts = bm.verts if len(bm.select_history) <= 0 else set( filter(lambda v : v.select, bm.verts) )
        search_verts   = bm.verts if self.use_unselected         else selected_verts  
        
        targetmap = bmesh.ops.find_doubles(bm, verts=search_verts, dist=self.threshold,
            keep_verts=selected_verts if self.use_unselected else list())['targetmap']

        selected_edges = bm.edges if len(bm.select_history) <= 0 else set( filter(lambda e : e.verts[0].select or e.verts[1].select, bm.edges) )
        
        # メッシュ整頓
        if me.has_custom_normals:
            layer = bm.loops.layers.float_vector.new('custom_normals.temp')
            self.set_bmlayer_from_custom_normals(bm, layer, me)

        if self.is_sharp:
            pass
        
        # Remove Doubles
        bmesh.ops.weld_verts(bm, targetmap=targetmap)
        bmesh.update_edit_mesh(me)

        if me.has_custom_normals:
            if self.keep_custom_normals:
                self.set_custom_normals_from_bmlayer(bm, layer, me)
            bm.loops.layers.float_vector.remove(layer)
            bmesh.update_edit_mesh(me)
        
        return {'FINISHED'}

    @staticmethod
    def set_bmlayer_from_custom_normals(bm, layer, me):
        me.calc_normals_split()
        for face in bm.faces:
            for loop in face.loops:
                loop[layer] = me.loops[loop.index].normal
      
    @staticmethod          
    def set_custom_normals_from_bmlayer(bm, layer, me):
        custom_normals = np.zeros((len(me.loops), 3))
        for face in bm.faces:
            for loop in face.loops:
                custom_normals[loop.index] = loop[layer]
        me.normals_split_custom_set(custom_normals)
