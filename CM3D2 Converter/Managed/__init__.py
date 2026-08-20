""" Importing this module will ensure that pythonnet is properly initialized,
    and that assembly references have been added.
"""

from pathlib import Path as _Path
from typing import TYPE_CHECKING

_MANAGED_DIR = _Path(__file__).parent.absolute()
_LOADED = False

import pythonnet as _pythonnet

def load():
    global _LOADED
    if not _pythonnet._LOADED:
        _pythonnet.set_runtime('netfx')
    _pythonnet.load()
    _LOADED = True
    _add_references()


def unload() -> bool:
    """Returns true if the runtime was successfuly unloaded."""
    global _LOADED
    if not _LOADED:
        return True
    try:
        _pythonnet.unload()
        _LOADED = False
    except RuntimeError:
        return False
    return True

def reload():
    """Reload the runtime and managed assemblies"""
    import importlib
    if _LOADED:
        unload()
    importlib.reload(_pythonnet)
    load()

def _add_references():
    if TYPE_CHECKING:
        class clr():
            @staticmethod
            def AddReference(dll_name: str):
                """Reference the specified dll"""
    else:
        import clr
    from System.IO import FileLoadException  # type: ignore
    from System.Reflection import Assembly  # type: ignore

    try:
        _add_reference("CM3D2.Serialization.dll", clr)
        _add_reference("COM3D2.LiveLink.dll", clr)
    except FileLoadException:  # type: ignore
        _copy_unsafe_dll('CM3D2.Serialization.dll')
        _copy_unsafe_dll('COM3D2.LiveLink.dll')
        _copy_unsafe_dll('System.Threading.dll')
        _add_reference("CM3D2.Serialization.dll", clr)
        _add_reference("COM3D2.LiveLink.dll", clr)

def _add_reference(filename: str, clr):
    dll_path = str((_MANAGED_DIR / filename).absolute())
    clr.AddReference(dll_path)

def _copy_unsafe_dll(filename: str):
    """If the addon is unzipped and placed directly in the addons folder,
    the dlls will be marked as originating from a remote source.
    Windows will refuse to load these dlls.
    Try working around this by copying it.
    """
    import os
    import shutil
    dll_path = str((_MANAGED_DIR / filename).absolute())
    bak_path = dll_path + '.bak'
    if os.path.exists(bak_path):
        os.remove(bak_path)
    shutil.move(dll_path, bak_path)
    shutil.copy(bak_path, dll_path)
    try:
        os.remove(bak_path)
    except OSError as ex:
        import warnings
        warnings.warn(str(ex), RuntimeWarning)
