import os
from dotenv import load_dotenv
from pathlib import Path


BLENDER_SPEC_MAP = {
    "3.4": {"python": "3.10", "bpy": "3.4.0", "find-links": "https://download.blender.org/pypi/bpy/"},
    "3.5": {"python": "3.10", "bpy": "3.5.0", "find-links": "https://download.blender.org/pypi/bpy/"},
    "3.6": {"python": "3.10", "bpy": "3.6.0", "find-links": "https://download.blender.org/pypi/bpy/"},
    "4.0": {"python": "3.10", "bpy": "4.0.0", "find-links": "https://download.blender.org/pypi/bpy/"},
    "4.1": {"python": "3.11", "bpy": "4.1.0", "find-links": "https://download.blender.org/pypi/bpy/"},
    "4.2": {"python": "3.11", "bpy": "4.2.21"},
    "4.3": {"python": "3.11", "bpy": "4.3.0"},
    "4.4": {"python": "3.11", "bpy": "4.4.0"},
    "4.5": {"python": "3.11", "bpy": "4.5.10"},
    "5.0": {"python": "3.11", "bpy": "5.0.1"},
    "5.1": {"python": "3.13", "bpy": "5.1.2"},
    #"5.2": {"python": "3.13", "bpy": "5.2.0"},
}

load_dotenv(Path(__file__).parent / ".env")
BLENDER_PATH_FMT: str = os.environ.get("BLENDER_PATH_FMT", "")
BLENDER_VERSIONS: list[str] = os.environ.get("BLENDER_VERSIONS", "").split(" ")
MAX_WORKER_NUM: int = int(os.environ.get("MAX_WORKER_NUM", 5))
VENV_PATH_FMT:str  = "venvs/venv_{}/Scripts/python.exe"
