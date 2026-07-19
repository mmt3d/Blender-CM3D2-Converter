from pathlib import Path
import bpy
from . import common, compat

TEMPLATES_PATH = Path(__file__).parent / 'templates'

# メニュー等に項目追加
@compat.BlRegister(append_to=bpy.types.TEXT_MT_templates)
def menu_func(self: bpy.types.Menu, context: bpy.types.Context):
    self.layout.menu(TEXT_MT_templates_cm3d2_converter.bl_idname,
                     icon_value=common.KISS_ICON)


@compat.BlRegister()
class TEXT_MT_templates_cm3d2_converter(bpy.types.Menu):
    bl_idname = 'TEXT_MT_templates_cm3d2_converter'
    bl_label = "CM3D2 Converter (third-party)"

    def draw(self, context):
        self.path_menu(
            [str(TEMPLATES_PATH)],
            'text.open',
            props_default={'internal': True},
            filter_ext=lambda ext: (ext.lower() in ['.py'])
        )

