import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from unittest import TestCase
import numpy as np

if TYPE_CHECKING:
    import bpy
    from mathutils import Matrix, Quaternion, Vector
    from numpy._typing import ArrayLike

class BlenderTestCase(TestCase):
    is_cm3d2converter_registered = False
    
    @property
    def cm3d2converter_directory(self) -> Path:
        project_dir = Path(__file__).parent.parent
        if (project_dir / 'CM3D2_Converter').exists():
            return project_dir / 'CM3D2_Converter'
        else:
            return project_dir / 'CM3D2 Converter'

    @property
    def blend_file_path(self) -> str:
        return str(self.cm3d2converter_directory / 'append_data.blend')

    @property
    def resources_dir(self) -> str:
        return str(Path(__file__).parent / 'resources')

    @property
    def output_dir(self) -> str:
        path = Path(__file__).parent / 'output' / self.__class__.__name__
        if not path.exists():
            path.mkdir(parents=True)
        return str(path)

    @property
    def pid(self) -> int:
        return os.getpid()

    @staticmethod
    def activate_object(obj: 'bpy.types.Object'):
        """Activate the object, ensuring that it is visible first."""
        import bpy
        collections: list[bpy.types.LayerCollection] = obj.users_collection
        layer_collection = None
        for child in bpy.context.view_layer.layer_collection.children:
            child: bpy.types.LayerCollection
            if child.collection.name == collections[0].name:
                layer_collection = child
                break
        bpy.context.view_layer.active_layer_collection = layer_collection
        layer_collection.hide_viewport = False
        layer_collection.exclude = False
        bpy.context.view_layer.update()
        bpy.context.view_layer.objects.active = obj

    def setUp(self):
        super().setUp()
        import bpy
        bpy.ops.wm.open_mainfile(filepath=self.blend_file_path)
        if not BlenderTestCase.is_cm3d2converter_registered:
            try:
                import importlib
                cm3d2converter = importlib.import_module(self.cm3d2converter_directory.name)
                cm3d2converter.register()
                cm3d2converter.common.preferences().backup_ext = ''
            except Exception as ex:
                print(ex)
            finally:
                BlenderTestCase.is_cm3d2converter_registered = True

    def tearDown(self):
        for root, __, files in os.walk(Path(__file__).parent / 'output'):
            for file in files:
                if f"_{self.pid}." in file:
                    os.remove(os.path.join(root, file))

    def assertOperatorFinished(self, result: set[Literal['RUNNING_MODAL', 'CANCELLED', 'FINISHED', 'PASS_THROUGH']],
                               msg=None):
        if 'FINISHED' not in result:
            msg = f" : {msg}" if not msg is None else ""
            self.fail(f"Operator did not finish (returned {result})" + msg)
        
    
    def assertArrayAlmostEqual(self, first: 'ArrayLike', second: 'ArrayLike', *,
                               rtol=1.e-5, atol=1.e-8, equal_nan=False, msg=None):
        """Fail if the two arrays are not element-wise equal within a tolerance."""
        throw = False

        if (len(first) != len(second)):
            throw = True
        elif not np.allclose(first, second, rtol, atol, equal_nan):
            throw = True

        if throw:
            msg = f" : {msg}" if not msg is None else ""
            self.fail(f"{first} != {second}" + msg)

    def assertVectorAlmostEqual(self, first: 'Vector', second: 'Vector', *,
                                rtol=1.e-5, atol=1.e-8, equal_nan=False, msg=None):
        """Fail if the two vectors are not element-wise equal within a tolerance."""
        self.assertArrayAlmostEqual(first, second, rtol=rtol, atol=atol, equal_nan=equal_nan, msg=msg)

    def assertQuaternionAlmostEqual(self, first: 'Quaternion', second: 'Quaternion', *,
                                rtol=1.e-5, atol=1.e-8, equal_nan=False, msg=None):
        """Fail if the two quaternions are not element-wise equal within a tolerance."""
        self.assertArrayAlmostEqual(first, second, rtol=rtol, atol=atol, equal_nan=equal_nan, msg=msg)
    
    def assertMatrixAlmostEqual(self, first: 'Matrix', second: 'Matrix', *,
                                rtol=1.e-5, atol=1.e-8, equal_nan=False, msg=None):
        """Fail if the two quaternions are not element-wise equal within a tolerance."""
        self.assertArrayAlmostEqual(first, second, rtol=rtol, atol=atol, equal_nan=equal_nan, msg=msg)

    
class BlenderTest(BlenderTestCase):
    
    def test_register(self):
        if BlenderTestCase.is_cm3d2converter_registered:
            return
        import sys
        import importlib
        sys.path.append(self.cm3d2converter_directory.parent)
        cm3d2converter = importlib.import_module(self.cm3d2converter_directory.name)
        cm3d2converter.register()
    
