""" Importing this module will ensure that pythonnet is properly initialized,
    and that assembly references have been added.
"""

from pathlib import Path as _Path
from typing import TYPE_CHECKING

_MANAGED_DIR = _Path(__file__).parent.absolute()
_RUNTIME_DLL_DIR: _Path | None = None
_TEMP_DLL_ROOT: _Path | None = None
_LOADED = False

import pythonnet as _pythonnet

def load():
    global _LOADED
    if not _pythonnet._LOADED:
        _pythonnet.set_runtime('netfx')
    _pythonnet.load()
    _prepare_runtime_dlls()
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

    _add_reference("CM3D2.Serialization.dll", clr)
    _add_reference("COM3D2.LiveLink.dll", clr)

def _add_reference(filename: str, clr):
    base_dir = _RUNTIME_DLL_DIR or _MANAGED_DIR
    dll_path = str((base_dir / filename).absolute())
    clr.AddReference(dll_path)


def _prepare_runtime_dlls():
    """
    アドオン更新時のDLLロックを回避するため、DLLを一時ディレクトリにコピーしてから使用する
    """
    import os
    import shutil
    import tempfile
    import time
    from .. import package_version  # type: ignore

    global _RUNTIME_DLL_DIR
    global _TEMP_DLL_ROOT
    if _TEMP_DLL_ROOT is None:
        _TEMP_DLL_ROOT = _Path(tempfile.gettempdir()) / 'cm3d2_converter'
    version_root = _TEMP_DLL_ROOT / package_version
    runtime_dir = version_root / f'{os.getpid()}_{time.time_ns()}'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    for dll_path in _MANAGED_DIR.glob('*.dll'):
        shutil.copy2(str(dll_path), str(runtime_dir / dll_path.name))
    _RUNTIME_DLL_DIR = runtime_dir
    _cleanup_temp_dirs(runtime_dir)


def _cleanup_temp_dirs(active_dir: _Path):
    """
    プロセスごとに一時ディレクトリを作成する方針で増えるため、古いディレクトリを見つけ次第削除する
    """
    import shutil

    if _TEMP_DLL_ROOT is None:
        return
    # 全バージョンディレクトリ内のプロセス終了済みランタイムディレクトリを削除し、空になったバージョンディレクトリも削除する
    for version_dir in _TEMP_DLL_ROOT.iterdir():
        for runtime_dir in version_dir.iterdir():
            if runtime_dir == active_dir:
                continue
            pid = _parse_runtime_dir_pid(runtime_dir.name)
            if pid is not None and _is_process_alive(pid):
                continue
            try:
                shutil.rmtree(runtime_dir)
            except OSError:
                pass
        try:
            next(version_dir.iterdir())
        except StopIteration:
            try:
                version_dir.rmdir()
            except OSError:
                pass


def _parse_runtime_dir_pid(dirname: str) -> int | None:
    """
    ディレクトリ名からpidを抽出する。(形式:"{pid}_{timestamp}")
    """
    return int(dirname.partition('_')[0])


def _is_process_alive(pid: int) -> bool:
    """
    指定プロセスIDが生存しているかを判定する
    ※windows限定かつ依存モジュール(psutil)なしで判定
    """
    import ctypes
    from ctypes import wintypes

    if pid <= 0:
        return False

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        # オープンできない場合、理由が権限不足であれば「存在する」そうでなければ「存在しない」
        return ctypes.get_last_error() == 5

    exit_code = wintypes.DWORD()
    try:
        # ハンドル取れても終了している場合の判定
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)
