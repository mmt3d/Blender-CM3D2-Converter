import os, sys, subprocess
import bpy

def install_package():
    # path to python.exe
    python_exe = os.path.join(sys.prefix, 'bin', 'python.exe')
    target = os.path.join(bpy.utils.script_path_user(), 'addons', 'modules')
    requirements_txt = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    
    # upgrade pip
    subprocess.call([python_exe, '-m', 'ensurepip'])
    subprocess.call([python_exe, '-m', 'pip', 'install', '--upgrade', 'pip'])
 
    # install required packages
    subprocess.call([python_exe, '-m', 'pip', 'install', '-r', requirements_txt, '-t', target])

def check_module(module_name: str) -> bool:
    try:
        module = __import__(module_name)
    except ModuleNotFoundError as e:
        return False
    return True