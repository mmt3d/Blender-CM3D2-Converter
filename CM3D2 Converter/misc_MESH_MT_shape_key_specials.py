# 「プロパティ」エリア → 「メッシュデータ」タブ → 「シェイプキー」パネル → ▼ボタン
import time
import bpy
import bmesh
import mathutils
import traceback
import abc
from . import common
from . import compat
from . import model_export
from .translations import *


# メニュー等に項目追加
def menu_func(self, context):
    icon_id = common.kiss_icon()
    self.layout.separator()
    sub = self.layout.column()
    self.layout.label(text="CM3D2 Converter", icon_value=icon_id)
    sub.separator()
    sub.operator('object.change_base_shape_key', icon='SHAPEKEY_DATA')
    sub.operator('object.multiply_shape_key', icon_value=icon_id)
    sub.operator('object.blur_shape_key', icon_value=icon_id)
    sub.separator()
    sub.operator('object.copy_shape_key_values', icon_value=icon_id)
    sub.separator()
    sub.operator('object.quick_shape_key_transfer', icon_value=icon_id)
    sub.operator('object.precision_shape_key_transfer', icon_value=icon_id)
    sub.operator('object.weighted_shape_key_transfer', icon_value=icon_id)
    sub.separator()



class transfer_shape_key_iter:
    index = -1

    target_ob = None
    source_ob = None

    binded_shape_key = None
    binded_shape_key_data = None

    #target_mat = None
    #source_mat = None

    source_iter = None

    source_shape_key_data = None
    target_shape_key_data = None

    def __init__(self, target_ob, source_ob, binded_shape_key=None, only_selected=False):
        self.target_ob = target_ob
        self.source_ob = source_ob
        self.binded_shape_key = binded_shape_key or self.source_ob.data.shape_keys.key_blocks[0]
        self.only_selected = only_selected

    def __iter__(self):
        self.index = -1
        if self.source_iter:
            self.source_iter = iter(self.source_iter)

        #self.target_mat = self.target_ob.matrix_world
        #self.source_mat = self.source_ob.matrix_world

        if self.source_ob and self.source_ob.data.shape_keys:
            binded_index = self.source_ob.data.shape_keys.key_blocks.find(self.binded_shape_key.name)
            #self.binded_shape_key_data = bmesh.new(use_operators=False)
            #self.binded_shape_key_data.from_mesh(self.source_ob.data, use_shape_key=True, shape_key_index=binded_index)
            #self.binded_shape_key_data.verts.ensure_lookup_table()
            self.binded_shape_key_data = self.binded_shape_key.data
            if self.only_selected and not compat.IS_LT51:
                self.source_iter = iter(filter(lambda x: x.select, self.source_ob.data.shape_keys.key_blocks))
            else:
                self.source_iter = iter(self.source_ob.data.shape_keys.key_blocks)
        return self

    def __next__(self):
        target_me = self.target_ob.data
        source_me = self.source_ob.data

        target_shape_key = None
        source_shape_key = next(self.source_iter, None)
        if not source_shape_key:
            raise StopIteration
        
        self.index += 1

        if target_me.shape_keys:
            if source_shape_key.name in target_me.shape_keys.key_blocks:
                target_shape_key = target_me.shape_keys.key_blocks[source_shape_key.name]
            else:
                target_shape_key = self.target_ob.shape_key_add(name=source_shape_key.name, from_mix=False)
        else:
            target_shape_key = self.target_ob.shape_key_add(name=source_shape_key.name, from_mix=False)

        relative_key_name = source_shape_key.relative_key.name

        rel_key = target_me.shape_keys.key_blocks.get(relative_key_name)
        if rel_key:
            target_shape_key.relative_key = rel_key
        
        if not self.target_ob.active_shape_key_index == 0:
            target_me.shape_keys.key_blocks[self.target_ob.active_shape_key_index].value = 0.0
        if not self.source_ob.active_shape_key_index == 0:
            source_me.shape_keys.key_blocks[self.source_ob.active_shape_key_index].value = 0.0

        target_index = target_me.shape_keys.key_blocks.find(target_shape_key.name)
        source_index = source_me.shape_keys.key_blocks.find(source_shape_key.name)

        self.target_ob.active_shape_key_index = target_index
        self.source_ob.active_shape_key_index = source_index

        target_shape_key.value = 1.0
        source_shape_key.value = 1.0
        
        #source_shape_key_data = [compat.mul3(self.source_mat, source_shape_key.data[v.index].co, self.target_mat) - compat.mul3(self.source_mat, source_me.vertices[v.index].co, self.target_mat) for v in source_me.vertices]
        #for i, v in enumerate(self.source_bind_data):
        #    shape_co = compat.mul3(self.source_mat, source_shape_key.data[i].co, self.target_mat)
        #    mesh_co  = compat.mul3(self.source_mat, self.source_bind_data[i].co, self.target_mat)
        #    self.source_shape_key_data[i] = shape_co - mesh_co

        #self.target_shape_key_data = bmesh.from_edit_mesh(self.target_ob.data)
        #self.source_shape_key_data = bmesh.from_edit_mesh(self.source_ob.data)
        #self.source_shape_key_data = bmesh.new(use_operators=False)
        #self.source_shape_key_data.from_mesh(self.source_ob.data, use_shape_key=True, shape_key_index=source_index)

        #self.target_shape_key_data.verts.ensure_lookup_table()
        #self.source_shape_key_data.verts.ensure_lookup_table()

        self.source_shape_key_data = source_shape_key.data
        self.target_shape_key_data = target_shape_key.data

        # 処理後は0に戻す
        target_shape_key.value = 0.0
        source_shape_key.value = 0.0

        return self.index, target_shape_key, self.binded_shape_key_data, self.source_shape_key_data, self.target_shape_key_data

    # update() will free resources for the current iteration of a loop, but not the loop itself.
    def update(self, destructive=False):
        pass
        #if self.target_shape_key_data and self.target_shape_key_data.is_valid:
            #bmesh.update_edit_mesh(self.target_ob.data, loop_triangles=True, destructive=destructive)
            #self.target_shape_key_data.free()
            #pass

        #if self.source_shape_key_data and self.source_shape_key_data.is_valid:
            #bmesh.update_edit_mesh(self.source_ob.data, loop_triangles=True, destructive=destructive)
            #self.source_shape_key_data.free()
            #pass

    # free() will release all resources for the loop, leaving it unable to run unless iter() is used again.
    def free(self, destructive=False):
        pass
        #self.update()
        #if self.binded_shape_key_data and self.binded_shape_key_data.is_valid:
            #bmesh.update_edit_mesh(self.source_ob.data, loop_triangles=True, destructive=destructive)
            #self.binded_shape_key_data.free()


class shape_key_transfer_op(bpy.types.Operator):
    is_first_remove_all: bpy.props.BoolProperty(name="最初に全シェイプキーを削除", default=False)
    is_remove_empty: bpy.props.BoolProperty(name="変形のないシェイプキーを削除", default=True)
    is_bind_current_mix: bpy.props.BoolProperty(name="Bind to current source mix", default=False)
    subdivide_number: bpy.props.IntProperty(name="参照元の分割", default=1, min=0, max=10, soft_min=0, soft_max=10)
    only_selected: bpy.props.BoolProperty(name="選択したシェイプキーのみ転送", default=True)

    target_ob: bpy.types.Object | None = None
    source_ob: bpy.types.Object | None = None
    og_source_ob: bpy.types.Object | None = None
    _start_time: float = 0.0
    _timer: bpy.types.Timer | None = None
    is_finished: bool = False
    is_canceled: bool = False
    pre_mode: str | None = None
    pre_selected: list[bpy.types.Object] | None = None
    pre_active: bpy.types.Object | None = None
    binded_shape_key: bpy.types.ShapeKey | None = None
    kd: mathutils.kdtree.KDTree | None = None
    is_shapeds: dict = {}

    def draw(self, context):
        self.layout.prop(self, 'is_first_remove_all', icon='ERROR'        )
        if not compat.IS_LT51:
            self.layout.prop(self, 'only_selected', icon='KEY_MENU')
        self.layout.prop(self, 'subdivide_number'   , icon='LATTICE_DATA' )
        self.layout.prop(self, 'is_remove_empty'    , icon='X'            )
        self.layout.prop(self, 'is_bind_current_mix', icon='AUTOMERGE_OFF')
    
    def execute(self, context):
        self.pre_selected = list(context.selected_objects)
        self.pre_mode = context.mode
        
        self.target_ob, self.source_ob, self.og_source_ob = common.get_target_and_source_ob(context, copySource=True)
        print(f"returned {self.source_ob.data.shape_keys}")

        bpy.ops.object.mode_set(mode='OBJECT')
        compat.set_hide(self.og_source_ob, True)

        self._start_time = time.time()
        self._timer = None
        self.is_finished = False
        self.is_canceled = False

        self.binded_shape_key = None
        self.source_bind_data = None
        self.kd = None
        self.is_shapeds = {}

        try:
            self.prepare(context)
        
        except Exception as ex:
            if not self.options.is_invoke:
                #self.cleanup(context)
                raise RuntimeError("Error while preparing shapekey transfer.")
            self.is_canceled = True
            traceback.print_exc()
            self.report(type={'ERROR'}, message="Error while preparing shapekey transfer.")
            self.cancel(context)
            return {'FINISHED'}
        
        compat.set_active(context, self.target_ob)
        
        if self.options.is_invoke:
            # run asynchronously
            wm = context.window_manager
            self._timer = wm.event_timer_add(1.0/60.0, window=context.window)
            wm.modal_handler_add(self)
            self.report(type={'INFO'}, message="Press ESC to cancel shape key transfer")
            return {'RUNNING_MODAL'}
        else:
            # run synchronously
            try:
                while not self.is_finished:
                    self.is_finished = self.loop(context)
                self.finish(context)
                return {'FINISHED'}
            finally:
                self.cleanup(context)
                    
                    
            
    def modal(self, context, event):
        if event.type == 'ESC':
            self.is_canceled = 'WARNING'
        if not event.type == 'TIMER':
            return {'PASS_THROUGH'}
        
        #print("Run Modal")

        if self.is_canceled:
            #print("Canceled")
            try:
                self.cancel(context)
            except:
                traceback.print_exc()
                self.report(type={'ERROR'}, message="Error while canceling shapekey transfer.")
            finally:
                return {'FINISHED'}

        if not self.is_canceled and not self.is_finished:
            #print("Loop")
            try:
                self.is_finished = self.loop(context)
            except:
                self.is_canceled = True
                traceback.print_exc()
                self.report(type={'ERROR'}, message="Error while performing shapekey transfer.")
            finally:
                return {'PASS_THROUGH'}

        else:
            #print("Finish")
            try:
                self.finish(context)
            except:
                self.is_canceled = True
                traceback.print_exc()
                self.report(type={'ERROR'}, message="Error while finishing shapekey transfer.")
                return {'PASS_THROUGH'}
            finally:
                self.cleanup(context)
                diff_time = time.time() - self._start_time
                self.report(type={'INFO'}, message=f_tip_("{:.2f} Seconds", diff_time))
                return {'FINISHED'}

    def prepare(self, context):
        target_ob = self.target_ob
        source_ob = self.source_ob
        target_me: bpy.types.Mesh = self.target_ob.data
        source_me: bpy.types.Mesh = self.source_ob.data
        print(f"prepare source_me = {source_me}")
        print(f"prepare source_me.shape_keys = {source_me.shape_keys}")
        

        bpy.ops.object.select_all(action='DESELECT')

        compat.set_active(context, source_ob)
        compat.set_select(source_ob, select=True)
        #compat.set_select(source_og_ob, False)
        #compat.set_select(target_ob, False)
        
        if target_ob.matrix_world != source_ob.matrix_world:
            print(f"prepare: transform")
            # transform source's mesh now so theres no need to worry about it later
            matrix_source_to_target = compat.mul(target_ob.matrix_world.inverted_safe(), source_ob.matrix_world)
            source_me.transform(matrix_source_to_target, shape_keys=True)
            source_ob.matrix_world = target_ob.matrix_world

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.subdivide(number_cuts=self.subdivide_number, smoothness=0.0, quadcorner='STRAIGHT_CUT', fractal=0.0, fractal_along_normal=0.0, seed=0)
        bpy.ops.object.mode_set(mode='OBJECT')

        if self.is_first_remove_all:
            try:
                target_ob.active_shape_key_index = 1
                target_me.shape_keys = None
                #bpy.ops.object.shape_key_remove(all=True)
            except:
                pass
            finally:
                target_ob.active_shape_key_index = 0
        else:
            if target_me.shape_keys:
                for i, key in enumerate(target_me.shape_keys.key_blocks):
                    if i == 0:
                        continue
                    else:
                        key.value = 0.0
            target_ob.active_shape_key_index = 0

        if self.is_bind_current_mix:
            source_basis = source_me.shape_keys.key_blocks[0]
            
            old_basis = target_me.shape_keys and next(iter(target_me.shape_keys.key_blocks), False) or target_ob.shape_key_add()
            old_basis.name = '__old_basis__' + old_basis.name
            new_basis = target_ob.shape_key_add(name=source_basis.name)

            self.binded_shape_key = source_ob.shape_key_add(name='__bind_shape_key', from_mix=True)
            self.source_bind_data = self.binded_shape_key.data
            
            compat.set_active(context, target_ob)
            target_ob.active_shape_key_index = target_me.shape_keys.key_blocks.find(new_basis.name)
            # TOP指定でindex=1になるケースは、さらにもう一度UP
            bpy.ops.object.shape_key_move(type='TOP')
            if target_ob.active_shape_key_index == 1:
                bpy.ops.object.shape_key_move(type='UP')
            
            old_basis.relative_key = new_basis
            
            source_ob.active_shape_key_index = source_me.shape_keys.key_blocks.find(self.binded_shape_key.name)

        else:
            source_ob.active_shape_key_index = 0
            self.source_bind_data = source_me.vertices

        #print(len(source_ob.data.vertices), len(self.source_bind_data))
        self.kd = mathutils.kdtree.KDTree(len(self.source_bind_data))
        print(f"prepare {source_me.shape_keys}")
        for index, vert in enumerate(self.source_bind_data):
            co = compat.mul(source_ob.matrix_world, vert.co)
            self.kd.insert(co, index)
        self.kd.balance()

        for i, key in enumerate(source_me.shape_keys.key_blocks):
            if i == 0:
                continue
            else:
                key.value = 0.0

    @abc.abstractmethod
    def loop(self, context) -> bool | None: ...
    
    def finish(self, context):
        target_me = self.target_ob.data
        
        if self.is_remove_empty:
            for source_shape_key_name, is_shaped in reversed( list(self.is_shapeds.items()) ):
                if not is_shaped:
                    target_shape_key = target_me.shape_keys.key_blocks.get(source_shape_key_name)
                    if not target_shape_key:
                        continue
                    key_blocks_values = target_me.shape_keys.key_blocks.values()
                    is_used = False
                    for key in key_blocks_values:
                        if key.relative_key == target_shape_key:
                            is_used = True
                            break
                    if not is_used:
                        self.target_ob.shape_key_remove(target_shape_key)

        self.target_ob.active_shape_key_index = 0

    def cancel(self, context):
        report_type = (self.is_canceled == 'WARNING' and 'WARNING') or 'ERROR'
        self.report(type={report_type}, message="Shape key transfer canceled. Results may not be as expected. Use Undo / Ctrl Z to revert changes")
        self.cleanup(context)

    def cleanup(self, context):
        if self.target_ob:
            compat.set_active(context, self.target_ob)

        if self.og_source_ob:
            compat.set_hide(self.og_source_ob, False)

        print(f"Remove {self.source_ob}")
        source_me = self.source_ob and self.source_ob.data
        if source_me:
            common.remove_data([self.source_ob, source_me])
        elif self.source_ob:
            common.remove_data([self.source_ob])

        if self._timer:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)

        if self.pre_mode and context.object:
            bpy.ops.object.mode_set(mode=self.pre_mode)
            
        if self.pre_selected:
            for ob in self.pre_selected:
                compat.set_select(ob, True)

        self.target_ob = None
        self.source_ob = None

        self._timer = None

        self.pre_mode = None
        self.pre_selected = None

        self.binded_shape_key = None
        self.kd = None
        self.is_shapeds = {}



@compat.BlRegister()
class CNV_OT_quick_shape_key_transfer(shape_key_transfer_op):
    bl_idname = 'object.quick_shape_key_transfer'
    bl_label = "クイック・シェイプキー転送"
    bl_description = "アクティブなメッシュに他の選択メッシュのシェイプキーを高速で転送します"
    bl_options = {'REGISTER', 'UNDO'}

    step_size: bpy.props.IntProperty(name="Step Size (low = quality, high = speed)", default=1, min=1, max=100, soft_min=1, soft_max=10, step=1)

    near_vert_indexs = []
    my_iter = None

    @classmethod
    def poll(cls, context):
        obs = context.selected_objects
        if len(obs) == 2:
            active_ob = context.active_object
            for ob in obs:
                if ob.type != 'MESH':
                    return False
                if ob.data.shape_keys and ob.name != active_ob.name:
                    return True
        return False

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        shape_key_transfer_op.draw(self, context)
        self.layout.prop(self, 'step_size')

    def prepare(self, context):
        super().prepare(context)

        target_me = self.target_ob.data
        source_me = self.source_ob.data
        
        self.near_vert_indexs = list( range(len(target_me.vertices)) )

        for v in target_me.vertices:
            near_co = compat.mul(self.target_ob.matrix_world, v.co) #v.co
            self.near_vert_indexs[v.index] = self.kd.find(near_co)[1]
        
        self.my_iter = iter( transfer_shape_key_iter(self.target_ob, self.source_ob, self.binded_shape_key, self.only_selected) )
        context.window_manager.progress_begin( 0, len(source_me.shape_keys.key_blocks) * len(target_me.vertices) )
        context.window_manager.progress_update( 0 )
    
    def loop(self, context):
        source_shape_key_index, target_shape_key, binded_shape_key_data, source_shape_key_data, target_shape_key_data = next(self.my_iter, (-1, None, None, None, None))
        #print(source_shape_key_index, target_shape_key, binded_shape_key_data, source_shape_key_data, target_shape_key_data)
        if not target_shape_key:
            context.window_manager.progress_end()
            return True

        progress = source_shape_key_index * len(self.target_ob.data.vertices)

        def check(index):
            near_vert_index = self.near_vert_indexs[index]
            near_shape_co = source_shape_key_data[near_vert_index].co - binded_shape_key_data[near_vert_index].co

            context.window_manager.progress_update( progress + index )
            
            if abs(near_shape_co.length) > 2e-126: # 2e-126 is the smallest float != 0
                target_shape_key_data[index].co += near_shape_co
                return True

        is_changed = False
        just_changed = False
        found_more = False
        for i in range(0, len(target_shape_key_data), self.step_size):
            
            if check(i) or found_more:
                is_changed = True
                found_more = False
                if not just_changed:
                    for j in range(i-self.step_size+1, i):
                        if j < len(target_shape_key_data) and j > 0:
                            found_more = check(j) or found_more
                for k in range(i+1, i+self.step_size):
                    if k < len(target_shape_key_data) and k > 0:
                        found_more = check(k) or found_more
                just_changed = True
            else:
                just_changed = False
        
        if not self.is_shapeds.get(target_shape_key.name):
            self.is_shapeds[target_shape_key.name] = is_changed
        self.my_iter.update() # only call this when done with current iteration.
    
    def cleanup(self, context):
        self.near_vert_indexs = []
        self.my_iter.free()
        self.my_iter = None
        shape_key_transfer_op.cleanup(self, context)



@compat.BlRegister()
class CNV_OT_precision_shape_key_transfer(shape_key_transfer_op):
    bl_idname = 'object.precision_shape_key_transfer'
    bl_label = "空間ぼかし・シェイプキー転送"
    bl_description = "アクティブなメッシュに他の選択メッシュのシェイプキーを遠いほどぼかして転送します"
    bl_options = {'REGISTER', 'UNDO'}

    step_size: bpy.props.IntProperty(name="Step Size (low = quality, high = speed)", default=1, min=1, max=100, soft_min=1, soft_max=10, step=1)
    extend_range: bpy.props.FloatProperty(name="範囲倍率", default=1.1, min=1.0001, max=5.0, soft_min=1.0001, soft_max=5.0, step=10, precision=2)

    
    near_vert_data = []
    near_vert_multi_total = []
    my_iter = None

    #source_raw_data = None
    #binded_raw_data = None
    #target_raw_data = None
    
    @classmethod
    def poll(cls, context):
        obs = context.selected_objects
        if len(obs) == 2:
            active_ob = context.active_object
            for ob in obs:
                if ob.type != 'MESH':
                    return False
                if ob.data.shape_keys and ob.name != active_ob.name:
                    return True
        return False

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        shape_key_transfer_op.draw(self, context)
        self.layout.prop(self, 'step_size')
        self.layout.prop(self, 'extend_range', icon='PROP_ON')

    # todo: 不要なはず、意図的に名称変更されている
    #  ベースクラスのexecuteがサブクラスのprepare/loopを呼ぶ設計
    def xexecute(self, context):
        start_time = time.time()

        target_ob, source_ob = common.get_target_and_source_ob(context, copySource=True)
        target_me = target_ob.data
        source_me = source_ob.ldata

        pre_mode = target_ob.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        try:
            kd = self.prepare_sks_transfer(context, target_ob, source_ob)

            context.window_manager.progress_begin(0, len(target_me.vertices))
            progress_reduce = len(target_me.vertices) // 200 + 1
            near_vert_data = []
            near_vert_multi_total = []
            near_vert_multi_total_append = near_vert_multi_total.append
            
            mat1, mat2 = source_ob.matrix_world, target_ob.matrix_world
            source_shape_key_data = [compat.mul3(mat1, source_shape_key.data[v.index].co, mat2) - compat.mul3(mat1, source_me.vertices[v.index].co, mat2) for v in source_me.vertices]
            
            for vert in target_me.vertices:
                new_vert_data = []
                near_vert_data.append(new_vert_data)
                near_vert_data_append = new_vert_data.append

                target_co = compat.mul(target_ob.matrix_world, vert.co)
                mini_co, mini_index, mini_dist = kd.find(target_co)
                radius = mini_dist * self.extend_range
                diff_radius = radius - mini_dist

                multi_total = 0.0
                for co, index, dist in kd.find_range(target_co, radius):
                    if 0 < diff_radius:
                        multi = (diff_radius - (dist - mini_dist)) / diff_radius
                    else:
                        multi = 1.0
                    near_vert_data_append((index, multi))
                    multi_total += multi
                near_vert_multi_total_append(multi_total)

                if vert.index % progress_reduce == 0:
                    context.window_manager.progress_update(vert.index)
            context.window_manager.progress_end()

            is_shapeds = {}
            context.window_manager.progress_begin(0, len(source_me.shape_keys.key_blocks) * len(target_me.vertices))
            context.window_manager.progress_update(0)

            for source_shape_key_index, source_shape_key, target_shape_key in self.enumerate_transfer_sks(context, target_ob, source_ob):
                for target_vert in target_me.vertices:

                    if 0 < near_vert_multi_total[target_vert.index]:

                        total_diff_co = mathutils.Vector((0, 0, 0))

                        for near_index, near_multi in near_vert_data[target_vert.index]:
                            total_diff_co += source_shape_key_data[near_index] * near_multi

                        average_diff_co = total_diff_co / near_vert_multi_total[target_vert.index]

                    else:
                        average_diff_co = mathutils.Vector((0, 0, 0))

                    target_shape_key.data[target_vert.index].co = target_me.vertices[target_vert.index].co + average_diff_co
                    is_shapeds[target_shape_key.name] = is_shapeds.get(target_shape_key.name) or 0.01 < average_diff_co.length

                    context.window_manager.progress_update((source_shape_key_index+1) * (target_me.vertices+1))
                #context.window_manager.progress_update(source_shape_key_index)
            context.window_manager.progress_end()

            self.finish_sks_transfer(context, target_ob, source_ob, is_shapeds)
        
        except:
            traceback.print_exc()
            self.report(type={'ERROR'}, message="Error while transfering shapekeys. Results may not be as expected. Use Undo / Ctrl Z to revert changes")

        finally:
            self.cleanup_sks_transfer(context, target_ob, source_ob, pre_mode)

        diff_time = time.time() - start_time
        self.report(type={'INFO'}, message=f_tip_("{:.2f} Seconds", diff_time))
        return {'FINISHED'}

    def prepare(self, context):
        super().prepare(context)

        target_me = self.target_ob.data
        source_me = self.source_ob.data

        context.window_manager.progress_begin(0, len(target_me.vertices))
        progress_reduce = len(target_me.vertices) // 200 + 1
        self.near_vert_data = []
        self.near_vert_multi_total = []
        near_vert_multi_total_append = self.near_vert_multi_total.append
            
        for vert in target_me.vertices:
            new_vert_data = []
            self.near_vert_data.append(new_vert_data)
            self.near_vert_data_append = new_vert_data.append

            target_co = compat.mul(self.target_ob.matrix_world, vert.co) #vert.co
            mini_co, mini_index, mini_dist = self.kd.find(target_co)
            radius = mini_dist * self.extend_range
            diff_radius = radius - mini_dist

            multi_total = 0.0
            for co, index, dist in self.kd.find_range(target_co, radius):
                if 0 < diff_radius:
                    multi = (diff_radius - (dist - mini_dist)) / diff_radius
                else:
                    multi = 1.0
                self.near_vert_data_append((index, multi))
                multi_total += multi
            near_vert_multi_total_append(multi_total)

            if vert.index % progress_reduce == 0:
                context.window_manager.progress_update(vert.index)
        context.window_manager.progress_end()

        self.my_iter = iter(transfer_shape_key_iter(self.target_ob, self.source_ob, binded_shape_key=self.binded_shape_key, only_selected=self.only_selected))

        #self.source_raw_data = numpy.ndarray(shape=(len(source_me.vertices), 3), dtype=float, order='C')
        #self.target_raw_data = numpy.ndarray(shape=(len(target_me.vertices), 3), dtype=float, order='C')

        #self.binded_raw_data = numpy.ndarray(shape=len(self.source_bind_data)*3, dtype=float, order='C')
        #self.source_bind_data.foreach_get('co', self.binded_raw_data)
        #self.binded_raw_data.resize(self.binded_raw_data.size//3, 3)

        context.window_manager.progress_begin(0, len(source_me.shape_keys.key_blocks) * len(target_me.vertices))
        context.window_manager.progress_update(0)

    def loop(self, context):
        #bpy.ops.object.mode_set(mode='OBJECT')
        source_shape_key_index, target_shape_key, binded_shape_key_data, source_shape_key_data, target_shape_key_data = next(self.my_iter, (-1, None, None, None, None))
        if not target_shape_key:
            context.window_manager.progress_end()
            return True
        
        #print("Loop for " + target_shape_key.name)

        #context.window_manager.progress_begin( 0, len(self.source_ob.shape_keys.key_blocks) * len(target_ob.data.vertices) )
        progress = source_shape_key_index * len(self.target_ob.data.vertices)
        #context.window_manager.progress_update( progress )

        diff_data = [None] * len(source_shape_key_data)
        near_diff_co = mathutils.Vector.Fill(3, 0) # Creates a vector of length 3 filled with 0's
        def check(index, near_diff_co=near_diff_co):
            near_diff_co.zero() # This should be faster than creating a new vector every time

            if self.near_vert_multi_total[index] > 0:
                for near_index, near_multi in self.near_vert_data[index]:
                    diff_data[near_index] = diff_data[near_index] or source_shape_key_data[near_index].co - binded_shape_key_data[near_index].co
                    near_diff_co += diff_data[near_index] * near_multi

                near_diff_co /= self.near_vert_multi_total[index]
            
            context.window_manager.progress_update( progress + index )

            if near_diff_co.length > 2e-126: # 2e-126 is the smallest float != 0
                target_shape_key_data[index].co += near_diff_co
                return True

        is_changed = False
        just_changed = False
        if self.step_size > 1:
            found_more = False
            for i in range(0, len(target_shape_key_data), self.step_size):
                
                if check(i) or found_more:
                    is_changed = True
                    found_more = False
                    if not just_changed:
                        for j in range(i-self.step_size+1, i):
                            if j < len(target_shape_key_data) and j > 0:
                                found_more = check(j) or found_more
                    for k in range(i+1, i+self.step_size):
                        if k < len(target_shape_key_data) and k > 0:
                            found_more = check(k) or found_more
                    just_changed = True
                else:
                    just_changed = False
        
        else: # if self.step_size == 1:
            for index, binded_vert, source_vert in zip(range(len(diff_data)), binded_shape_key_data, source_shape_key_data):
                diff_data[index] = source_vert.co - binded_vert.co
                if diff_data[index].length > 2e-126:
                    just_changed = True
            
            if just_changed:
                for target_vert, near_indices, near_total in zip(target_shape_key_data, self.near_vert_data, self.near_vert_multi_total):
                    near_diff_co.zero() # This should be faster than creating a new vector every time

                    if near_total > 0:
                        for near_index, near_multi in near_indices:
                            near_diff_co += diff_data[near_index] * near_multi

                        near_diff_co /= near_total

                    if near_diff_co.length > 2e-126: # 2e-126 is the smallest float != 0
                        target_vert.co += near_diff_co
                        is_changed = True
                    
                    progress += 1
                    context.window_manager.progress_update( progress )
            else:
                context.window_manager.progress_update( progress + len(target_shape_key_data) )

        self.is_shapeds[target_shape_key.name] = self.is_shapeds.get(target_shape_key.name) or is_changed
        self.my_iter.update() # only call this when done with current iteration.
        #bpy.ops.object.mode_set(mode='SCULPT') # Preview shape keys while transfering

    def cleanup(self, context):
        self.near_vert_data = []
        self.near_vert_multi_total = []
        self.my_iter = None
        #self.source_raw_data = None
        #self.binded_raw_data = None
        #self.target_raw_data = None
        shape_key_transfer_op.cleanup(self, context)


@compat.BlRegister()
class CNV_UL_vgroups_selector(bpy.types.UIList):

    use_filter_name_reverse: bpy.props.BoolProperty(name="Reverse Name", default=False, options=set(), description="Reverse name filtering")
    use_filter_deform: bpy.props.BoolProperty(name="Only Deform", default=False, options=set(), description="Only show deforming vertex groups")
    use_filter_deform_reverse: bpy.props.BoolProperty(name="Other", default=False, options=set(), description="Only show non-deforming vertex groups")
    use_filter_empty: bpy.props.BoolProperty(name="Filter Empty", default=False, options=set(), description="Whether to filter empty vertex groups")
    use_filter_empty_reverse: bpy.props.BoolProperty(name="Reverse Empty", default=False, options=set(), description="Reverse empty filtering" )
    order_mode: bpy.props.EnumProperty(name="Order by", items=[('NAME', "Name", "Sort groups by name (case-insensitive)"), ('IMPORTANCE', "Importance", "Sort groups by average weight")], default='NAME')
    use_filter_orderby_invert: bpy.props.BoolProperty(name="Order by Invert", default=False, options=set(), description="Invert the sort by order")

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index, flt_flag):
        # ユーザにはpreferredをチェック操作させ、結果はフィルタ反映したものをvalueで取得する想定
        row = layout.row(align=True)
        row.prop(item, 'preferred', text=item.name, icon_value=icon)
        if self.order_mode == 'IMPORTANCE':
            sub = row.row()
            sub.alignment = 'RIGHT'
            sub.label(text=f"{item.sort0:.4f}")

    def draw_filter(self, context, layout):
        row = layout.row()

        subrow = row.row(align=True)
        subrow.prop(self, 'filter_name', text="", icon='VIEWZOOM')
        icon = 'ZOOM_OUT' if self.use_filter_name_reverse else 'ZOOM_IN'
        subrow.prop(self, 'use_filter_name_reverse', text="", icon=icon)

        subrow = row.row(align=True)
        subrow.prop(self, 'use_filter_deform', toggle=True)
        icon = 'ZOOM_OUT' if self.use_filter_deform_reverse else 'ZOOM_IN'
        subrow.prop(self, 'use_filter_deform_reverse', text="", icon=icon)

        row = layout.row(align=True)
        row.prop(self, 'order_mode')
        icon = 'TRIA_UP' if self.use_filter_orderby_invert else 'TRIA_DOWN'
        row.prop(self, 'use_filter_orderby_invert', text="", icon=icon)

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        helper_funcs = bpy.types.UI_UL_list
        flt_flags = [self.bitflag_filter_item] * len(items)
        flt_neworder = []

        # 文字列検索
        if self.filter_name:
            flt_flags = helper_funcs.filter_items_by_name(
                self.filter_name, self.bitflag_filter_item, items, 'name',
                reverse=self.use_filter_name_reverse)

        # Deform フィルタ
        if self.use_filter_deform:
            for i, it in enumerate(items):
                if not (bool(getattr(it, 'filter0', False)) ^ self.use_filter_deform_reverse):
                    flt_flags[i] &= ~self.bitflag_filter_item

        # 並び替え
        if self.order_mode == 'NAME':
            sort_data = [(i, it) for i, it in enumerate(items)]
            key = lambda x: (getattr(x[1], 'name', '') or '').lower()
            reverse = self.use_filter_orderby_invert
            flt_neworder = helper_funcs.sort_items_helper(sort_data, key=key, reverse=reverse)
        elif self.order_mode == 'IMPORTANCE':
            sort_data = [(i, it) for i, it in enumerate(items)]
            key = lambda x: getattr(x[1], 'sort0', 0.0)
            reverse = not self.use_filter_orderby_invert
            flt_neworder = helper_funcs.sort_items_helper(sort_data, key=key, reverse=reverse)

        # フィルタ結果とユーザ選択結果をvalueに反映
        for i, it in enumerate(items):
            it.value = bool(flt_flags[i] & self.bitflag_filter_item) and it.preferred

        return flt_flags, flt_neworder


@compat.BlRegister()
class CNV_OT_weighted_shape_key_transfer(shape_key_transfer_op):
    bl_idname = 'object.weighted_shape_key_transfer'
    bl_label = "Weighted shape key transfer"
    bl_description = "Transfers the shape keys of other selected mesh to the active mesh, using matching vertex groups as masks"
    bl_options = {'REGISTER', 'UNDO'}

    step_size: bpy.props.IntProperty(name="Step Size (low = quality, high = speed)", default=1, min=1, max=100, soft_min=1, soft_max=10, step=1)
    extend_range: bpy.props.FloatProperty(name="Range magnification", default=1.1, min=1.0001, max=5.0, soft_min=1.0001, soft_max=5.0, step=10, precision=2)

    near_vert_data = []
    near_vert_multi_total = []
    my_iter = None

    matched_vgroups = []
    using_vgroups: bpy.props.CollectionProperty(type=common.CNV_SelectorItem)
    active_vgroup: bpy.props.IntProperty(name="Active Vertex Group", default=0)

    @classmethod
    def poll(cls, context):
        obs = context.selected_objects
        if len(obs) == 2:
            active_ob = context.active_object
            for ob in obs:
                if ob.type != 'MESH':
                    return False
                if ob.data.shape_keys and ob.name != active_ob.name:
                    return True
        return False

    def invoke(self , context, event):
        target_ob, source_ob = common.get_target_and_source_ob(context)
        self.matched_vgroups = common.values_of_matched_keys(target_ob.vertex_groups, source_ob.vertex_groups)
        armature_ob = target_ob.find_armature() or source_ob.find_armature()
        armature = armature_ob and armature_ob.data or False
        bone_data_ob = (target_ob.get('LocalBoneData:0') and target_ob) or (source_ob.get('LocalBoneData:0') and source_ob) or None
        local_bone_names = []
        if bone_data_ob:
            local_bone_data = model_export.CNV_OT_export_cm3d2_model.local_bone_data_parser(model_export.CNV_OT_export_cm3d2_model.indexed_data_generator(bone_data_ob, prefix='LocalBoneData:'))
            local_bone_names = [ bone['name'] for bone in local_bone_data ]

        importance_map = {vg.index: [0.0, 0] for vg, _ in self.matched_vgroups}
        for v in target_ob.data.vertices:
            for g in v.groups:
                if g.group in importance_map:
                    importance_map[g.group][0] += g.weight  # 合計ウェイト
                    importance_map[g.group][1] += 1  # 該当頂点数

        for index, vgs in enumerate(self.matched_vgroups):
            target_vg, source_vg = vgs
            vg_name = target_vg.name
            if self.using_vgroups.get(vg_name):
                continue
            new_prop = self.using_vgroups.add()
            new_prop.name = vg_name
            new_prop.index = index
            new_prop.value = True
            if armature and armature.get(vg_name) or vg_name in local_bone_names:
                new_prop.filter0 = True
            total_w, count = importance_map.get(target_vg.index, [0.0, 0])
            new_prop.sort0 = (total_w / count) if count > 0 else 0.0

        return CNV_OT_precision_shape_key_transfer.invoke(self, context, event)

    def draw(self, context):
        CNV_OT_precision_shape_key_transfer.draw(self, context)
        self.layout.template_list('CNV_UL_vgroups_selector', "", self, 'using_vgroups', self, 'active_vgroup')
        self.layout.label(text="Show filters", icon='FILE_PARENT')
        
    def prepare(self, context):
        shape_key_transfer_op.prepare(self, context)

        target_me = self.target_ob.data
        source_me = self.source_ob.data

        self.matched_vgroups = [ ( self.target_ob.vertex_groups.get(vg.name), self.source_ob.vertex_groups.get(vg.name) ) for vg in self.using_vgroups if vg.value]

        context.window_manager.progress_begin(0, len(target_me.vertices))
        progress_reduce = len(target_me.vertices) // 200 + 1
        self.near_vert_data = []
        self.near_vert_multi_total = []
        near_vert_multi_total_append = self.near_vert_multi_total.append
        
        for vert in target_me.vertices:
            new_vert_data = []
            self.near_vert_data.append(new_vert_data)
            self.near_vert_data_append = new_vert_data.append

            target_co = compat.mul(self.target_ob.matrix_world, vert.co) #vert.co
            mini_co, mini_index, mini_dist = self.kd.find(target_co)
            radius = mini_dist * self.extend_range
            diff_radius = radius - mini_dist

            multi_total = 0.0
            for co, index, dist in self.kd.find_range(target_co, radius):
                if 0 < diff_radius:
                    multi = (diff_radius - (dist - mini_dist)) / diff_radius
                else:
                    multi = 1.0

                avg_weight_match = 0
                for target_vg, source_vg in self.matched_vgroups:
                    target_weight = 0
                    try:
                        target_weight = target_vg.weight(vert.index)
                    except:
                        pass
                    source_weight = 0
                    try:
                        source_weight = source_vg.weight(index)
                    except:
                        pass
                    avg_weight_match += -abs(source_weight - target_weight) + target_weight
                if avg_weight_match > 1:
                    avg_weight_match = 1
                elif avg_weight_match < 0:
                    avg_weight_match = 0

                multi *= avg_weight_match
                self.near_vert_data_append((index, multi))
                multi_total += multi
            near_vert_multi_total_append(multi_total)

            if vert.index % progress_reduce == 0:
                context.window_manager.progress_update(vert.index)
        context.window_manager.progress_end()

        self.my_iter = iter(transfer_shape_key_iter(self.target_ob, self.source_ob, binded_shape_key=self.binded_shape_key, only_selected=self.only_selected))

        #self.source_raw_data = numpy.ndarray(shape=(len(source_me.vertices), 3), dtype=float, order='C')
        #self.target_raw_data = numpy.ndarray(shape=(len(target_me.vertices), 3), dtype=float, order='C')

        #self.binded_raw_data = numpy.ndarray(shape=len(self.source_bind_data)*3, dtype=float, order='C')
        #self.source_bind_data.foreach_get('co', self.binded_raw_data)
        #self.binded_raw_data.resize(self.binded_raw_data.size//3, 3)

        context.window_manager.progress_begin(0, len(source_me.shape_keys.key_blocks) * len(target_me.vertices))
        context.window_manager.progress_update(0)       
      
    loop = CNV_OT_precision_shape_key_transfer.loop
    cleanup = CNV_OT_precision_shape_key_transfer.cleanup



@compat.BlRegister()
class CNV_OT_multiply_shape_key(bpy.types.Operator):
    bl_idname = 'object.multiply_shape_key'
    bl_label = "シェイプキーの変形に乗算"
    bl_description = "シェイプキーの変形に数値を乗算し、変形の強度を増減させます"
    bl_options = {'REGISTER', 'UNDO'}

    multi: bpy.props.FloatProperty(name="倍率", description="シェイプキーの拡大率です", default=1.1, min=-10, max=10, soft_min=-10, soft_max=10, step=10, precision=2)
    items = [
        ('ACTIVE', "アクティブのみ", "", 'HAND', 1),
        ('UP', "アクティブより上", "", 'TRIA_UP_BAR', 2),
        ('DOWN', "アクティブより下", "", 'TRIA_DOWN_BAR', 3),
        ('ALL', "全て", "", 'ARROW_LEFTRIGHT', 4),
    ]
    mode: bpy.props.EnumProperty(items=items, name="対象", default='ACTIVE')

    @classmethod
    def poll(cls, context):
        if context.active_object:
            ob = context.active_object
            if ob.type == 'MESH':
                return ob.active_shape_key
        return False

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'multi', icon='ARROW_LEFTRIGHT')
        self.layout.prop(self, 'mode', icon='VIEWZOOM')

    def execute(self, context):
        ob = context.active_object
        me = ob.data
        shape_keys = me.shape_keys
        pre_mode = ob.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        target_shapes = []
        if self.mode == 'ACTIVE':
            target_shapes.append(ob.active_shape_key)
        elif self.mode == 'UP':
            for index, key_block in enumerate(shape_keys.key_blocks):
                if index <= ob.active_shape_key_index:
                    target_shapes.append(key_block)
        elif self.mode == 'UP':
            for index, key_block in enumerate(shape_keys.key_blocks):
                if ob.active_shape_key_index <= index:
                    target_shapes.append(key_block)
        elif self.mode == 'ALL':
            for key_block in shape_keys.key_blocks:
                target_shapes.append(key_block)

        for shape in target_shapes:
            data = shape.data
            for i, vert in enumerate(me.vertices):
                diff = data[i].co - vert.co
                diff *= self.multi
                data[i].co = vert.co + diff
        bpy.ops.object.mode_set(mode=pre_mode)
        return {'FINISHED'}



@compat.BlRegister()
class CNV_OT_blur_shape_key(bpy.types.Operator):
    bl_idname = 'object.blur_shape_key'
    bl_label = "シェイプキーぼかし"
    bl_description = "アクティブ、もしくは全てのシェイプキーをぼかします"
    bl_options = {'REGISTER', 'UNDO'}

    items = [
        ('ACTIVE', "アクティブのみ", "", 'HAND', 1),
        ('UP', "アクティブより上", "", 'TRIA_UP_BAR', 2),
        ('DOWN', "アクティブより下", "", 'TRIA_DOWN_BAR', 3),
        ('ALL', "全て", "", 'ARROW_LEFTRIGHT', 4),
    ]
    target: bpy.props.EnumProperty(items=items, name="対象", default='ACTIVE')
    radius: bpy.props.FloatProperty(name="範囲倍率", default=3, min=0.1, max=50, soft_min=0.1, soft_max=50, step=50, precision=2)
    strength: bpy.props.IntProperty(name="強さ", default=1, min=1, max=10, soft_min=1, soft_max=10)
    items_2 = [
        ('BOTH', "増減両方", "", 'AUTOMERGE_ON', 1),
        ('ADD', "増加のみ", "", 'TRIA_UP', 2),
        ('SUB', "減少のみ", "", 'TRIA_DOWN', 3),
    ]
    effect: bpy.props.EnumProperty(items=items_2, name="ぼかし効果", default='BOTH')
    items_3 = [
        ('LINER', "ライナー", "", 'LINCURVE', 1),
        ('SMOOTH1', "スムーズ1", "", 'SMOOTHCURVE', 2),
        ('SMOOTH2', "スムーズ2", "", 'SMOOTHCURVE', 3),
    ]
    blend: bpy.props.EnumProperty(items=items_3, name="減衰タイプ", default='LINER')

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob and ob.type == 'MESH':
            me = ob.data
            return me.shape_keys
        return False

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'target', icon='VIEWZOOM')
        self.layout.prop(self, 'radius', icon='RADIOBUT_OFF')
        self.layout.prop(self, 'strength', icon='ARROW_LEFTRIGHT')
        self.layout.prop(self, 'effect', icon='NODE_TEXTURE')
        self.layout.prop(self, 'blend', icon='IPO_SINE')

    def execute(self, context):
        ob = context.active_object
        me = ob.data

        pre_mode = ob.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        bm = bmesh.new()
        bm.from_mesh(me)
        edge_lengths = [e.calc_length() for e in bm.edges]
        bm.free()

        edge_lengths.sort()
        average_edge_length = sum(edge_lengths) / len(edge_lengths)
        center_index = int((len(edge_lengths) - 1) / 2.0)
        average_edge_length = (average_edge_length + edge_lengths[center_index]) / 2
        radius = average_edge_length * self.radius

        context.window_manager.progress_begin(0, len(me.vertices))
        progress_reduce = len(me.vertices) // 200 + 1
        near_vert_data = []
        kd = mathutils.kdtree.KDTree(len(me.vertices))
        for vert in me.vertices:
            kd.insert(vert.co.copy(), vert.index)
        kd.balance()
        for vert in me.vertices:
            near_vert_data.append([])
            near_vert_data_append = near_vert_data[-1].append
            for co, index, dist in kd.find_range(vert.co, radius):
                multi = (radius - dist) / radius
                if self.blend == 'SMOOTH1':
                    multi = common.in_out_quad_blend(multi)
                elif self.blend == 'SMOOTH2':
                    multi = common.bezier_blend(multi)
                near_vert_data_append((index, multi))
            if vert.index % progress_reduce == 0:
                context.window_manager.progress_update(vert.index)
        context.window_manager.progress_end()

        target_shape_keys = []
        if self.target == 'ACTIVE':
            target_shape_keys.append(ob.active_shape_key)
        elif self.target == 'UP':
            for index, shape_key in enumerate(me.shape_keys.key_blocks):
                if index <= ob.active_shape_key_index:
                    target_shape_keys.append(shape_key)
        elif self.target == 'DOWN':
            for index, shape_key in enumerate(me.shape_keys.key_blocks):
                if ob.active_shape_key_index <= index:
                    target_shape_keys.append(shape_key)
        elif self.target == 'ALL':
            for index, shape_key in enumerate(me.shape_keys.key_blocks):
                target_shape_keys.append(shape_key)

        progress_total = len(target_shape_keys) * self.strength * len(me.vertices)
        context.window_manager.progress_begin(0, progress_total)
        progress_reduce = progress_total // 200 + 1
        progress_count = 0
        for strength_count in range(self.strength):
            for shape_key in target_shape_keys:

                shapes = []
                shapes_append = shapes.append
                for index, vert in enumerate(me.vertices):
                    co = shape_key.data[index].co - vert.co
                    shapes_append(co)

                for vert in me.vertices:

                    target_shape = shapes[vert.index]

                    total_shape = mathutils.Vector()
                    total_multi = 0.0
                    for index, multi in near_vert_data[vert.index]:
                        co = shapes[index]
                        if self.effect == 'ADD':
                            if target_shape.length <= co.length:
                                total_shape += co * multi
                                total_multi += multi
                        elif self.effect == 'SUB':
                            if co.length <= target_shape.length:
                                total_shape += co * multi
                                total_multi += multi
                        else:
                            total_shape += co * multi
                            total_multi += multi

                    if 0 < total_multi:
                        average_shape = total_shape / total_multi
                    else:
                        average_shape = mathutils.Vector()

                    shape_key.data[vert.index].co = vert.co + average_shape

                    progress_count += 1
                    if progress_count % progress_reduce == 0:
                        context.window_manager.progress_update(progress_count)

        context.window_manager.progress_end()
        bpy.ops.object.mode_set(mode=pre_mode)
        return {'FINISHED'}



@compat.BlRegister()
class CNV_OT_change_base_shape_key(bpy.types.Operator):
    bl_idname = 'object.change_base_shape_key'
    bl_label = "このシェイプキーをベースに"
    bl_description = "アクティブなシェイプキーを他のシェイプキーのベースにします"
    bl_options = {'REGISTER', 'UNDO'}

    is_deform_mesh: bpy.props.BoolProperty(name="素メッシュを調整", default=True)
    is_deform_other_shape: bpy.props.BoolProperty(name="他シェイプを調整", default=True)

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob and ob.type == 'MESH' and 1 <= ob.active_shape_key_index

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'is_deform_mesh', icon='MESH_DATA')
        self.layout.prop(self, 'is_deform_other_shape', icon='SHAPEKEY_DATA')

    def execute(self, context):
        ob = context.active_object
        me = ob.data

        pre_mode = ob.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        target_shape_key = ob.active_shape_key
        old_shape_key = me.shape_keys.key_blocks[0]

        # TOP指定でindex=1になるケースは、さらにもう一度UP
        bpy.ops.object.shape_key_move(type='TOP')
        if ob.active_shape_key_index == 1:
            bpy.ops.object.shape_key_move(type='UP')

        target_shape_key.relative_key = target_shape_key
        old_shape_key.relative_key = target_shape_key

        if self.is_deform_mesh:
            for vert in me.vertices:
                vert.co = target_shape_key.data[vert.index].co.copy()

        if self.is_deform_other_shape:
            for shape_key in me.shape_keys.key_blocks:
                if shape_key.name == target_shape_key.name or shape_key.name == old_shape_key.name:
                    continue
                if shape_key.relative_key.name == old_shape_key.name:
                    shape_key.relative_key = target_shape_key
                    for vert in me.vertices:
                        diff_co = target_shape_key.data[vert.index].co - old_shape_key.data[vert.index].co
                        shape_key.data[vert.index].co = shape_key.data[vert.index].co + diff_co

        bpy.ops.object.mode_set(mode=pre_mode)
        return {'FINISHED'}



@compat.BlRegister()
class CNV_OT_copy_shape_key_values(bpy.types.Operator):
    bl_idname = 'object.copy_shape_key_values'
    bl_label = "Copy shape key values"
    bl_description = "Copy the shape key values from the other selected mesh"
    bl_options = {'REGISTER', 'UNDO'}

    use_drivers: bpy.props.BoolProperty(name="Apply as drivers", default=False)

    @classmethod
    def poll(cls, context):
        obs = context.selected_objects
        if len(obs) == 2:
            active_ob = context.active_object
            for ob in obs:
                if ob.type != 'MESH':
                    return False
                if ob.data.shape_keys and ob.name != active_ob.name:
                    return True
        return False

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'use_drivers', icon='DRIVER')

    def execute(self, context):
        target_ob, source_ob = common.get_target_and_source_ob(context)
        
        source_sks = source_ob.data.shape_keys.key_blocks
        target_sks = target_ob.data.shape_keys.key_blocks
        for source_sk, target_sk in common.values_of_matched_keys(source_sks, target_sks):
            if not self.use_drivers:
                target_sk.value = source_sk.value
            else:
                driver = target_sk.driver_add('value').driver
                driver.type = 'AVERAGE'

                driver_var = driver.variables.new() if len(driver.variables) < 1 else driver.variables[0]
                driver_var.type = 'SINGLE_PROP'

                driver_target = driver_var.targets[0]
                driver_target.id_type = 'KEY'
                driver_target.id = source_sk.id_data
                driver_target.data_path = source_sk.path_from_id('value')
            
        
        return {'FINISHED'}


@bpy.app.handlers.persistent
def shape_key_change_handler(scene, depsgraph):
    """
    シェイプキー値増減時に複数選択中の別メッシュの同名シェイプキーも変更するハンドラ
    """
    if not depsgraph.id_type_updated('KEY'):
        return

    active = bpy.context.active_object
    if not active or active.type != 'MESH' or not active.data.shape_keys:
        return

    key = active.active_shape_key
    if not key:
        return

    for ob in bpy.context.selected_objects:
        if ob == active or ob.type != 'MESH' or not ob.data.shape_keys:
            continue

        target_keys = ob.data.shape_keys.key_blocks
        if key.name in target_keys:
            if target_keys[key.name].value != key.value:
                target_keys[key.name].value = key.value


def register():
    common.handler_append(bpy.app.handlers.depsgraph_update_post, shape_key_change_handler)


def unregister():
    common.handler_remove(bpy.app.handlers.depsgraph_update_post, shape_key_change_handler)
