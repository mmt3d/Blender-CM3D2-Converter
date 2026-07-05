# 画面上部 (「情報」エリア → ヘッダー) → ヘルプ
import re
import xml.etree.ElementTree as ET
from urllib.request import urlopen
import bpy
from . import bl_info, common, compat
from .translations import *


# メニュー等に項目追加
def menu_func(self, context):
    icon_id = common.kiss_icon()
    self.layout.separator()
    self.layout.operator('wm.check_cm3d2_converter_version', icon_value=icon_id)
    self.layout.operator('wm.open_cm3d2_converter_releases', icon_value=icon_id)
    self.layout.operator('wm.show_cm3d2_converter_preference', icon_value=icon_id)


RELEASES: dict = {'entries': [], 'error': None}


def fetch_release_entries():

    global RELEASES
    RELEASES = {'entries': [], 'error': None}

    def html2text(html):
        """HTMLタグ除去"""
        if not html:
            return []
        li_html = re.sub(r'<li>', '・', html)
        raw_text = re.sub(r'<[^>]+>', '', li_html)
        return '\n'.join([line.strip() for line in raw_text.splitlines() if line.strip()])

    try:
        response = urlopen(common.RELEASES_ATOM)
        xml_data = response.read().decode('utf-8')
        tree = ET.fromstring(xml_data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        for entry in tree.findall('atom:entry', ns):
            title_node = entry.find('atom:title', ns)
            link_node = entry.find('atom:link', ns)
            content_node = entry.find('atom:content', ns)
            if title_node is not None and link_node is not None:
                title = title_node.text.strip() if title_node.text else ''
                url = link_node.attrib.get('href', '')
                raw_content = content_node.text if content_node is not None else ''
                RELEASES['entries'].append((title, url, html2text(raw_content)))
    except (OSError, SyntaxError, AttributeError, ValueError) as e:
        RELEASES['error'] = str(e)


@compat.BlRegister()
class INFO_MT_help_CM3D2_Converter_CheckVersion(bpy.types.Operator):
    bl_idname = 'wm.check_cm3d2_converter_version'
    bl_label = "CM3D2 Converterの最新版チェック"

    current_ver: tuple = (0, 0, 0)
    latest_ver: tuple = (0, 0, 0)

    def invoke(self, context, event):
        self.current_ver = bl_info['version']
        # github releses.atom を読み込みRELEASESに取り込む
        fetch_release_entries()
        latest_ver_str = RELEASES['entries'][0][0].replace('v', '')
        self.latest_ver = tuple(map(int, latest_ver_str.split('.')))
        if self.latest_ver > self.current_ver:
            return context.window_manager.invoke_props_dialog(self)
        else:
            return context.window_manager.invoke_popup(self)

    def draw(self, context):
        current_ver_str = '.'.join(map(str, self.current_ver))
        latest_ver_str = '.'.join(map(str, self.latest_ver))
        if self.latest_ver > self.current_ver:
            self.layout.label(text=f_("更新があります: {} → {}", current_ver_str, latest_ver_str))
        else:
            self.layout.label(text=f_("最新版がインストールされています: {}", current_ver_str))

    def execute(self, context):
        if self.latest_ver > self.current_ver:
            # エクステンション管理画面を開く
            bpy.ops.wm.show_cm3d2_converter_extension()
        return {'FINISHED'}


@compat.BlRegister()
class INFO_MT_help_CM3D2_Converter_Releases(bpy.types.Operator):
    bl_idname = 'wm.open_cm3d2_converter_releases'
    bl_label = "CM3D2 Converterのリリース履歴"

    def invoke(self, context, event):
        # github releses.atom を読み込みRELEASESに取り込む
        fetch_release_entries()
        bpy.ops.wm.call_menu(name=INFO_MT_help_CM3D2_Converter_Releases_Menu.bl_idname)
        return {'FINISHED'}


@compat.BlRegister()
class INFO_MT_help_CM3D2_Converter_Releases_Menu(bpy.types.Menu):
    bl_idname = 'INFO_MT_help_CM3D2_Converter_Releases_Menu'
    bl_label = "CM3D2 Converterのリリース履歴"

    def draw(self, context):
        if RELEASES['error']:
            self.layout.label(text="リリース情報取得エラー", icon='ERROR')
            self.layout.label(text=RELEASES['error'])
            return

        for title, url, content in RELEASES['entries']:
            self.layout.operator('wm.url_open', text=title, icon='URL').url = url
            common.wrap_label(self.layout, content)
            self.layout.separator()


@compat.BlRegister()
class CNV_OT_show_cm3d2_converter_preference(bpy.types.Operator):
    bl_idname = 'wm.show_cm3d2_converter_preference'
    bl_label = "CM3D2 Converterの設定画面を開く"
    bl_description = "CM3D2 Converterアドオンの設定画面を表示します"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.screen.userpref_show()
        area = common.get_request_area(context, 'PREFERENCES')
        if area:
            bpy.ops.preferences.addon_show(module=__package__)
        else:
            self.report(type={'ERROR'}, message="表示できるエリアが見つかりませんでした")
            return {'CANCELLED'}
        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_show_cm3d2_converter_extension(bpy.types.Operator):
    bl_idname = 'wm.show_cm3d2_converter_extension'
    bl_label = "CM3D2 Converterのエクステンション管理を表示"
    bl_description = "CM3D2 Converterエクステンションの管理画面を表示します"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        bpy.ops.screen.userpref_show()
        area = common.get_request_area(context, 'PREFERENCES')
        if area:
            context.preferences.active_section = 'EXTENSIONS'
            context.window_manager.extension_search = __package__
            context.window_manager.extension_type = 'ADDON'
        else:
            self.report(type={'ERROR'}, message="表示できるエリアが見つかりませんでした")
            return {'CANCELLED'}
        return {'FINISHED'}
