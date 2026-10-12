from __future__ import annotations
import ctypes
import os
import threading
from collections.abc import Iterable
from functools import lru_cache

_SDK_LOCK = threading.Lock()
_ERROR_IPC = 2
_REQUEST_FILE_NAME_AND_PATH = 0x00000003


@lru_cache(maxsize=1)
def _load_sdk(dll_path: str):
    """
    Everything SDK DLL を読み込み、使用する関数の引数型と戻り値型を設定する。
    """
    dll = ctypes.WinDLL(dll_path)
    dll.Everything_Reset.argtypes = []
    dll.Everything_Reset.restype = None
    dll.Everything_SetSearchW.argtypes = [ctypes.c_wchar_p]
    dll.Everything_SetSearchW.restype = None
    dll.Everything_SetRequestFlags.argtypes = [ctypes.c_uint32]
    dll.Everything_SetRequestFlags.restype = None
    dll.Everything_SetMax.argtypes = [ctypes.c_uint32]
    dll.Everything_SetMax.restype = None
    dll.Everything_QueryW.argtypes = [ctypes.c_int]
    dll.Everything_QueryW.restype = ctypes.c_int
    dll.Everything_GetLastError.argtypes = []
    dll.Everything_GetLastError.restype = ctypes.c_uint32
    dll.Everything_GetNumResults.argtypes = []
    dll.Everything_GetNumResults.restype = ctypes.c_uint32
    dll.Everything_GetTotResults.argtypes = []
    dll.Everything_GetTotResults.restype = ctypes.c_uint32
    dll.Everything_GetResultFileNameW.argtypes = [ctypes.c_uint32]
    dll.Everything_GetResultFileNameW.restype = ctypes.c_wchar_p
    dll.Everything_GetResultFullPathNameW.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
    dll.Everything_GetResultFullPathNameW.restype = ctypes.c_uint32
    return dll


def _runtime_sdk():
    """
    Managed が一時ディレクトリへコピーした SDK DLL の場所を取得する。
    """
    from . import Managed

    runtime_dir = Managed._RUNTIME_DLL_DIR
    dll_path = runtime_dir / 'Everything64.dll'
    if not dll_path.is_file():
        raise FileNotFoundError(f"Everything SDK DLL not found: {dll_path}")
    return _load_sdk(str(dll_path))


def _result_path(dll, index: int) -> str:
    """
    Everything の検索結果から、長いパスも切り詰めずに取得する。
    """
    length = dll.Everything_GetResultFullPathNameW(index, None, 0)
    if not length:
        raise RuntimeError(f"Unable to retrieve Everything search result (error {dll.Everything_GetLastError()})")
    buffer = ctypes.create_unicode_buffer(length + 1)
    copied = dll.Everything_GetResultFullPathNameW(index, buffer, len(buffer))
    if copied != length:
        raise RuntimeError(f"Unable to retrieve Everything search result (error {dll.Everything_GetLastError()})")
    return buffer.value


def _is_under_root(path: str, root: str) -> bool:
    """
    候補のフルパスが指定された検索ルートの直下または子孫かを判定する。
    """
    normalized_path = os.path.normcase(os.path.normpath(path))
    prefix = os.path.normcase(root.rstrip("\\/") + os.sep)
    return normalized_path.startswith(prefix)


def _query(dll, search_text: str, max_results: int) -> None:
    """
    Everything に問い合わせ、検索結果を SDK 内に保持する。
    """
    dll.Everything_Reset()
    dll.Everything_SetRequestFlags(_REQUEST_FILE_NAME_AND_PATH)
    dll.Everything_SetMax(max_results)
    dll.Everything_SetSearchW(search_text)
    if not dll.Everything_QueryW(1):
        error = dll.Everything_GetLastError()
        if error == _ERROR_IPC:
            raise RuntimeError("Cannot search because Everything is not running")
        raise RuntimeError(f"Everything search failed (error {error})")


def check_connection() -> None:
    """
    ダミー検索を行い、Everything SDK の IPC 疎通を確認する。
    """
    dll = _runtime_sdk()
    with _SDK_LOCK:
        _query(dll, '"__CM3D2_CONVERTER_CONNECTION_CHECK__"', 1)


def find_file_paths(roots: Iterable[os.PathLike[str] | str], file_name: str) -> str | None:
    """
    Everything の索引から同名ファイルを探し、ルート順で最初のパスを返す。
    ファイル名の大文字と小文字は区別しない。見つからなければ None を返す。
    Everything が起動していない場合や SDK DLL が利用できない場合は例外を送出する。
    """
    root_paths = []
    for root in roots:
        if not os.fspath(root):
            continue
        path = os.path.normpath(os.path.abspath(os.fspath(root)))
        if os.path.isdir(path):
            root_paths.append(path)
    if not root_paths:
        return None

    dll = _runtime_sdk()
    wanted_name = file_name.casefold()
    with _SDK_LOCK:
        # 結果数にかかわらず一度だけ検索し、候補をルート順で評価する。
        _query(dll, f'"{file_name}"', 0xFFFFFFFF)
        best_index = len(root_paths)
        best_path = None
        for index in range(dll.Everything_GetNumResults()):
            result_name = dll.Everything_GetResultFileNameW(index)
            if result_name is None or result_name.casefold() != wanted_name:
                continue
            result_path = _result_path(dll, index)
            if not os.path.isfile(result_path):
                continue
            for root_index, root_path in enumerate(root_paths):
                if root_index < best_index and _is_under_root(result_path, root_path):
                    best_index = root_index
                    best_path = result_path
                    if root_index == 0:
                        return best_path
        return best_path
