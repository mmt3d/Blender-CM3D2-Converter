from __future__ import annotations

import bpy
import os
from pathlib import Path
import sys
import tempfile
from typing import TYPE_CHECKING, Literal, overload

from . import common
from . import compat
from . anm_export import AnmBuilder

from COM3D2.LiveLink import *
from CM3D2.Serialization import CM3D2Serializer
from System.IO import MemoryStream

if TYPE_CHECKING:
    # This stub can be easially generated with https://www.javainuse.com/csharp2py
    
    class LiveLinkCore:
        def __init__(self):
            pass
        @property
        def Address(self):
            pass
        @property
        def IsClient(self):
            pass
        @property
        def IsConnected(self):
            pass
        @property
        def IsServer(self):
            pass
        def Disconnect(self):
            pass
        def Dispose(self):
            pass
        def Flush(self):
            pass
        def ReadAll(self):
            pass
        def ReadString(self):
            pass
        @overload
        def SendBytes(self, bytes):
            pass
        @overload
        def SendBytes(self, bytes, count):
            pass
        def SendString(self, value):
            pass
        def StartClient(self, address = "com3d2.livelink"):
            pass
        def StartServer(self, address = "com3d2.livelink"):
            pass
        def TryReadMessage(self, message):
            pass
        def WaitForConnection(self, timeout = 1000):
            pass


@compat.BlRegister()
class COM3D2LiveLinkSettings(bpy.types.PropertyGroup):
    send_animation_max_frames: bpy.props.IntProperty(name="Max Frames to Send", default=500, min=1, soft_max=10000)
    anm_is_remove_unkeyed_bone: bpy.props.BoolProperty(name="Remove Unkeyed Bones", default=False)

@compat.BlRegister()
class COM3D2LiveLinkState(bpy.types.PropertyGroup):
    is_link_pose: bpy.props.BoolProperty("Link Pose is Active", default=False, options={'SKIP_SAVE'})

    #_active_livelink_core: LiveLinkCore = None

    #@property
    #def active_core(self) -> LiveLinkCore:
    #    cls = self.__class__
    #    return cls._active_livelink_core  # pylint:disable=protected-access

    #@active_core.setter
    #def active_core(self, value: LiveLinkCore):
    #    cls = self.__class__
    #    cls._active_livelink_core = value  # pylint:disable=protected-access


if TYPE_CHECKING:
    class WindowManager(bpy.types.WindowManager):
        com3d2_livelink_settings: COM3D2LiveLinkSettings
        com3d2_livelink_state: COM3D2LiveLinkState
else:
    from bpy.types import WindowManager


def _get_active_core() -> LiveLinkCore:
    return _set_active_core.core

def _set_active_core(value: LiveLinkCore):
    _set_active_core.core = value

_set_active_core.core: LiveLinkCore = None


@compat.BlRegister()
class VIEW3D_PT_com3d2_livelink(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport under the "COM3D2" tab"""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "COM3D2"
    bl_label = "LiveLink"

    def draw(self, context):
        self.draw_livelink_controls(context, self.layout)
        self.layout.separator()
        self.draw_model_controls(context, self.layout)
        self.layout.separator()
        self.draw_animation_controls(context, self.layout)

    def draw_livelink_controls(self, context: bpy.types.Context, layout: bpy.types.UILayout):
        core = _get_active_core()
        col = layout.column()
        if core is None:
            col.operator(COM3D2LIVELINK_OT_start_server.bl_idname)
            row = col.row()
            row.alignment = 'RIGHT'
            row.label(text="Server not running")
        else:
            col.operator_context = 'INVOKE_DEFAULT'
            col.operator(COM3D2LIVELINK_OT_stop_server.bl_idname)
            row = col.row()
            row.alignment = 'RIGHT'
            row.label(text="Connected" if (core is not None and core.IsConnected)
                      else "Not connected")

    def draw_model_controls(self, context: bpy.types.Context, layout: bpy.types.UILayout):
        layout.label(text='Model', icon='MESH_DATA')
        layout.operator(COM3D2LIVELINK_OT_send_model.bl_idname)
        
    def draw_animation_controls(self, context: bpy.types.Context, layout: bpy.types.UILayout):
        wm: WindowManager = context.window_manager
        core = _get_active_core()
        
        layout.label(text='Animation', icon='ANIM_DATA')
        if not wm.com3d2_livelink_state.is_link_pose:
            layout.operator(COM3D2LIVELINK_OT_link_pose.bl_idname)
        else:
            layout.operator(COM3D2LIVELINK_OT_unlink_pose.bl_idname)
        
        col = layout.column()
        col.enabled = bpy.ops.com3d2livelink.send_animation.poll()
        col.prop(wm.com3d2_livelink_settings, 'anm_is_remove_unkeyed_bone')
        col.prop(wm.com3d2_livelink_settings, 'send_animation_max_frames')
        send_animation_opr = layout.operator(COM3D2LIVELINK_OT_send_animation.bl_idname)
        send_animation_opr.max_frames = wm.com3d2_livelink_settings.send_animation_max_frames
        send_animation_opr.is_remove_unkeyed_bone = wm.com3d2_livelink_settings.anm_is_remove_unkeyed_bone


@compat.BlRegister()
class COM3D2LIVELINK_OT_start_server(bpy.types.Operator):
    """Start the LiveLink server"""
    bl_idname = "com3d2livelink.start_server"
    bl_label = "Start LiveLink"
    bl_options = {'REGISTER'}

    address: bpy.props.StringProperty("Address", default='com3d2.livelink')
    wait_for_connection: bpy.props.BoolProperty("Wait For Connection", default=False)
    
    @classmethod
    def poll(cls, context):
        core = _get_active_core()
        if not core:
            return True
        cls.poll_message_set("The LiveLink server is already running")
        return not core.IsServer

    def execute(self, context):
        core = _get_active_core()
        
        if core and core.IsServer:
            core.Disconnect()
        elif core is None:
            core = LiveLinkCore()
            _set_active_core(core)
        core.StartServer(self.address)
        
        if self.wait_for_connection:
            core.WaitForConnection()
        
        return {'FINISHED'}


@compat.BlRegister()
class COM3D2LIVELINK_OT_stop_server(bpy.types.Operator):
    """Stop the LiveLink server"""
    bl_idname = 'com3d2livelink.stop_server'
    bl_label = "Stop LiveLink"
    bl_options = {'REGISTER'}
    
    @classmethod
    def poll(cls, context):
        core = _get_active_core()
        if core is None:
            cls.poll_message_set("LiveLink core is not initialized.")
            return False
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=500)

    def draw(self, context):
        layout = self.layout
        core = _get_active_core()
        if core.IsConnected:
            layout.label(text="⚠ WARNING ⚠")
            layout.label(text="Stopping the server may crash Blender, the client, or both.")
            layout.label(text="This action is only safe if the client is already disconnected.")
            layout.label(text="Are you sure you want to try disconnecting?")
        else:
            layout.label(text="Shutdown LiveLink server?")

    def execute(self, context):
        core = _get_active_core()
        core.Disconnect()
        _set_active_core(None)
        return {'FINISHED'}


@compat.BlRegister()
class COM3D2LIVELINK_OT_wait_for_connection(bpy.types.Operator):
    """Wait for a connection from a LiveLink client"""
    bl_idname = 'com3d2livelink.wait_for_connection'
    bl_label = "Wait for Connection"
    bl_options = {'REGISTER'}
    
    @classmethod
    def poll(cls, context):
        core = _get_active_core()
        if not core:
            return False
        return True

    def execute(self, context):
        core = _get_active_core()
        
        core.WaitForConnection()
        
        return {'FINISHED'}


@compat.BlRegister()
class COM3D2LIVELINK_OT_send_animation(bpy.types.Operator):
    """Send an animation to connected LiveLink client"""
    bl_idname = "com3d2livelink.send_animation"
    bl_label = "Send Animation"
    bl_options = {'REGISTER'}
    
    max_frames: bpy.props.IntProperty(name="Maximum Frames to Send", default=1000, min=1, soft_max=10000)
    is_remove_unkeyed_bone: bpy.props.BoolProperty(name="Remove Unkeyed Bones", default=False)

    @classmethod
    def poll(cls, context):
        core = _get_active_core()
        if not core or not core.IsConnected:
            return False
        
        obj = context.active_object
        return obj and obj.type == 'ARMATURE'

    def execute(self, context):
        core = _get_active_core()
        
        if bpy.ops.com3d2livelink.unlink_pose.poll():
            bpy.ops.com3d2livelink.unlink_pose()
            
        current_frame = context.scene.frame_current
        
        builder = AnmBuilder(reporter=self)
        builder.frame_start            = context.scene.frame_current
        builder.frame_end              = min(context.scene.frame_end, builder.frame_start + self.max_frames)
        builder.export_method          = 'ALL'
        builder.is_visual_transform    = True
        builder.is_remove_unkeyed_bone = self.is_remove_unkeyed_bone
        
        anm = builder.build_anm(context)
        
        serializer = CM3D2Serializer()
        memory_stream = MemoryStream()
        serializer.Serialize(memory_stream, anm)
        core.SendBytes(memory_stream.GetBuffer(), memory_stream.Length)
        core.Flush()
        
        context.scene.frame_current = current_frame
            
        return {'FINISHED'}


@compat.BlRegister()
class COM3D2LIVELINK_OT_link_pose(bpy.types.Operator):
    """Operator which runs its self from a timer"""
    bl_idname = 'com3d2livelink.link_pose'
    bl_label = "Link Pose"
    bl_options = {'REGISTER'}
    
    timer = None
    
    @classmethod
    def poll(cls, context):
        core = _get_active_core()
        if not core or not core.IsConnected:
            return False
        obj: bpy.types.Object = context.active_object
        return obj and obj.type == 'ARMATURE' and obj.mode == 'POSE'
        
    def modal(self, context, event):
        state: COM3D2LiveLinkState = context.window_manager.com3d2_livelink_state
        core = _get_active_core()
        
        
        if not self.poll(context):
            self.cancel(context)
            return {'CANCELLED'}
        
        if not state.is_link_pose:
            return {'CANCELLED'}
        
        if event.type == 'TIMER':
            self.update_pose(context)
            
        return {'PASS_THROUGH'}

    def execute(self, context):
        wm: bpy.types.WindowManager = context.window_manager
        state: COM3D2LiveLinkState = wm.com3d2_livelink_state
        self.timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        state.is_link_pose = True
        self.update_pose(context)
        return {'RUNNING_MODAL'}

    def update_pose(self, context: bpy.types.Context):
        wm: bpy.types.WindowManager = context.window_manager
        core = _get_active_core()
        
        builder = AnmBuilder(reporter=self)
        builder.no_set_frame        = True
        builder.frame_start         = context.scene.frame_current
        builder.frame_end           = context.scene.frame_current
        builder.export_method       = 'ALL'
        builder.is_visual_transform = True
        builder.is_remove_unkeyed_bone = wm.com3d2_livelink_settings.anm_is_remove_unkeyed_bone
        
        anm = builder.build_anm(context)
        
        serializer = CM3D2Serializer()
        memory_stream = MemoryStream()
        serializer.Serialize(memory_stream, anm)
        core.SendBytes(memory_stream.GetBuffer(), memory_stream.Length)
        core.Flush()
    
    def cancel(self, context):
        wm: bpy.types.WindowManager = context.window_manager
        state: COM3D2LiveLinkState = wm.com3d2_livelink_state
        wm.event_timer_remove(self.timer)
        state.is_link_pose = False


@compat.BlRegister()
class COM3D2LIVELINK_OT_unlink_pose(bpy.types.Operator):
    """Operator which runs its self from a timer"""
    bl_idname = 'com3d2livelink.unlink_pose'
    bl_label = "Unlink Pose"
    bl_options = {'REGISTER'}
    
    timer = None
    
    @classmethod
    def poll(cls, context):
        state = context.window_manager.com3d2_livelink_state
        core = _get_active_core()
        
        if core is None or not core.IsConnected:
            return False
        return state.is_link_pose

    def execute(self, context):
        state = context.window_manager.com3d2_livelink_state
        state.is_link_pose = False
        return {'FINISHED'}


@compat.BlRegister()
class COM3D2LIVELINK_OT_send_model(bpy.types.Operator):
    """Send a model to the connected LiveLink client"""
    bl_idname = 'com3d2livelink.send_model'
    bl_label = "Send Model"
    bl_options = {'REGISTER'}
    
    timer = None
    
    @classmethod
    def poll(cls, context):
        core = _get_active_core()
        if core is None or not core.IsConnected:
            return False
        with context.temp_override():
            return bpy.ops.export_mesh.export_cm3d2_model.poll()

    def execute(self, context):
        core = _get_active_core()
        fd, filepath = tempfile.mkstemp('.model')
        try:
            os.close(fd)
            bpy.ops.export_mesh.export_cm3d2_model(filepath=filepath)
            with open(filepath, mode='rb') as file:
                core.SendBytes(file.read())
        finally:
            os.remove(filepath)
        return {'FINISHED'}
