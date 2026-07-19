try:
    import CM3D2_Converter
    from CM3D2_Converter import *
    __file__ = CM3D2_Converter.__file__

except: # pylint:disable=bare-except
    import importlib
    import sys
    from pathlib import Path
    sys.path.append( str(Path(__file__).parent.parent) )
    cm3d2converter = importlib.import_module('CM3D2 Converter')
    __file__ = cm3d2converter.__file__
    __all__ = []
    for k in dir(cm3d2converter):
        v = getattr(cm3d2converter, k)
        __all__.append(k)
        locals()[k] = v
    #__all__ = cm3d2converter.__all__

#import bpy
#register()
