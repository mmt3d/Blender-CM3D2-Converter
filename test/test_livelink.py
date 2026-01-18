import bpy
import subprocess
import os
from pathlib import Path

from blenderunittest import BlenderTestCase
from profilehelpers import ProfileLog

import cm3d2converter

class LiveLinkClientCLI:
    exe_path = Path(cm3d2converter.Managed.__file__).parent / 'COM3D2.LiveLink.CLI.exe'

    def __init__(self, address: str = 'com3d2.livelink'):
        print(self.exe_path)
        self.address = address
        self.process = subprocess.Popen(
            [f'{self.exe_path}', '--client', address],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    def __del__(self):
        self.process.terminate()
        self.process.wait()
        self.process.stdout.close()
        self.process.stderr.close()

class TestLiveLink(BlenderTestCase):
    def setUp(self):
        super().setUp()
        self.address = f'com3d2.livelink.{os.getpid()}'
        bpy.ops.com3d2livelink.start_server(address=self.address, wait_for_connection=False)
        self.client = LiveLinkClientCLI(self.address)
        bpy.ops.com3d2livelink.wait_for_connection()

    def tearDown(self):
        del self.client
        bpy.ops.com3d2livelink.stop_server()
        super().tearDown()

    def test_send_animation(self):
        tpose_object: bpy.types.Object = bpy.data.objects.get('Tスタンス素体.armature')
        self.activate_object(tpose_object)
        
        bpy.ops.com3d2livelink.send_animation()
    
    def test_link_pose(self):
        tpose_object: bpy.types.Object = bpy.data.objects.get('Tスタンス素体.armature')
        self.activate_object(tpose_object)
        
        bpy.ops.object.mode_set(mode='POSE')
        
        with ProfileLog(self.test_link_pose.__name__):
            bpy.ops.com3d2livelink.link_pose()

    def test_send_model(self):
        bpy.ops.import_mesh.import_cm3d2_model(filepath=f'{self.resources_dir}/body001.model')
        bpy.ops.com3d2livelink.send_model()
