# 画面上部 (「情報」エリア → ヘッダー) → ヘルプ
import os
import re
import sys
import urllib.request
import zipfile
import subprocess
import datetime
import xml.sax.saxutils
import addon_utils
import bpy
import traceback
import shutil
import hashlib
import random
from pathlib import Path

from . import common
from . import compat
from .translations.pgettext_functions import *

from . import Managed


# メニュー等に項目追加
def menu_func(self, context):
    icon_id = common.kiss_icon()
    self.layout.separator()
    self.layout.operator('script.update_cm3d2_converter', icon_value=icon_id)
    self.layout.operator('wm.call_menu', icon_value=icon_id, text=INFO_MT_help_CM3D2_Converter_RSS.bl_label).name = INFO_MT_help_CM3D2_Converter_RSS.bl_idname
    self.layout.operator('wm.show_cm3d2_converter_preference', icon_value=icon_id)
    # self.layout.operator('wm.call_menu', icon_value=icon_id, text=INFO_MT_help_cm3d2_converter_reload_notice.bl_label).name = INFO_MT_help_cm3d2_converter_reload_notice.bl_idname


# 更新履歴メニュー
@compat.BlRegister()
class INFO_MT_help_CM3D2_Converter_RSS(bpy.types.Menu):
    bl_idname = 'INFO_MT_help_CM3D2_Converter_RSS'
    bl_label = "CM3D2 Converterの更新履歴"

    def draw(self, context):
        try:
            response = urllib.request.urlopen(common.URL_ATOM.format(branch=common.BRANCH))
            html = response.read().decode('utf-8')
            titles = re.findall(r'\<title\>[　\s]*([^　\s][^\<]*[^　\s])[　\s]*\<\/title\>', html)[1:] # matches: <title> something </title>
            updates = re.findall(r'\<updated\>([^\<\>]*)\<\/updated\>', html)[1:]
            links = re.findall(r'<link [^\<\>]*href="([^"]+)"/>', html)[2:]
            #version_datetime = datetime.datetime.strptime(str(common.bl_info["version"][0]) + "," + str(common.bl_info["version"][1]) + "," + str(common.bl_info["version"][2]) + "," + str(common.bl_info["version"][3]) + "," + str(common.bl_info["version"][4]) + "," + str(common.bl_info["version"][5]), '%Y,%m,{},%H,%M,{}')
            numbers_in_version = 0
            sub_version = None
            year = 2000
            month = 1
            day = 1
            hour = 0
            minute = 0
            second = 0
            ms = 0
            for version_sub_value in common.bl_info["version"]:
                number = None
                if   type(version_sub_value) is int:
                    number = version_sub_value
                elif type(version_sub_value) is float:
                    number = version_sub_value
                elif type(version_sub_value) is str:
                    match = re.match(r'(\d+)\.?(.*)', version_sub_value)
                    if match:
                        number = int(match.group(1))
                        sub_str = match.group(2)
                        if sub_str:
                            sub_version = sum( ord(char) << 8*(len(sub_str)-byte-1) for byte, char in enumerate(sub_str) )
                if number:
                    if   numbers_in_version == 0:
                        year   = number
                    elif numbers_in_version == 1:
                        month  = number
                    elif numbers_in_version == 2:
                        day    = number
                    elif numbers_in_version == 3:
                        hour   = number
                    elif numbers_in_version == 4:
                        minute = number
                    elif numbers_in_version == 5:
                        second = number
                    numbers_in_version += 1
                
            version_datetime = datetime.datetime(year, month, day, hour, minute, second, ms)


            output_data = []
            update_diffs = []
            for title, update, link in zip(titles, updates, links):
                title = xml.sax.saxutils.unescape(title, {'&quot;': '"'})

                rss_datetime = datetime.datetime.strptime(update, '%Y-%m-%dT%H:%M:%SZ') + datetime.timedelta(hours=9)
                diff_seconds = datetime.datetime.now() - rss_datetime
                icon = 'SORTTIME'
                if 60 * 60 * 24 * 7 < diff_seconds.total_seconds():
                    icon = 'NLA'
                elif 60 * 60 * 24 * 3 < diff_seconds.total_seconds():
                    icon = 'COLLAPSEMENU'
                elif 60 * 60 * 24 < diff_seconds.total_seconds():
                    icon = 'TIME'
                elif 60 * 60 < diff_seconds.total_seconds():
                    icon = 'RECOVER_LAST'
                else:
                    icon = 'PREVIEW_RANGE'

                if 60 * 60 * 24 <= diff_seconds.total_seconds():
                    date_str = f_iface_("{}日前", int(diff_seconds.total_seconds() / 60 / 60 / 24))
                elif 60 * 60 <= diff_seconds.total_seconds():
                    date_str = f_iface_("{}時間前", int(diff_seconds.total_seconds() / 60 / 60))
                elif 60 <= diff_seconds.total_seconds():
                    date_str = f_iface_("{}分前", int(diff_seconds.total_seconds() / 60))
                else:
                    date_str = f_iface_("{}秒前", diff_seconds.total_seconds())

                text = "(" + date_str + ") " + title

                update_diff = abs((version_datetime - rss_datetime).total_seconds())

                output_data.append((text, icon, link, update_diff))
                update_diffs.append(update_diff)

            min_update_diff = sorted(update_diffs)[0]
            for text, icon, link, update_diff in output_data:

                if update_diff == min_update_diff:
                    if update_diff < 30:
                        text = "Now! " + text
                    icon = 'QUESTION'

                self.layout.operator('wm.url_open', text=text, icon=icon).url = link
        except:
            traceback.print_exc()
            self.layout.label(text="更新の取得に失敗しました", icon='ERROR')


@compat.BlRegister()
class CNV_OT_update_cm3d2_converter(bpy.types.Operator):
    bl_idname = 'script.update_cm3d2_converter'
    bl_label = "CM3D2 Converterを更新「luv」バージョン"
    bl_description = "GitHubから最新版のCM3D2 Converterアドオンをダウンロードし上書き更新します"
    bl_options = {'REGISTER'}

    is_restart: bpy.props.BoolProperty(name="更新後にBlenderを再起動", default=compat.IS_LEGACY)
    is_toggle_console: bpy.props.BoolProperty(name="再起動後にコンソールを閉じる", default=True)

    items = [
        ('current', f_iface_("Current ({branch})", branch=common.BRANCH), ""),
        ('bl_28'  , "bl_28", ""),
        ('testing', "testing", ""),
    ]
    branch: bpy.props.EnumProperty(items=items, name="Branch", default='current')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.menu('INFO_MT_help_CM3D2_Converter_RSS', icon='INFO')
        layout.separator()
        layout.prop(self, 'branch')
        col = layout.column()
        col.prop(self, 'is_restart', icon='BLENDER')
        row = col.row()
        row.prop(self, 'is_toggle_console', icon='CONSOLE')
        row.enabled = self.is_restart

    def execute(self, context):
        branch = self.branch
        if branch == 'current':
            branch = common.BRANCH
        zip_path = Path(bpy.app.tempdir) / f"Blender-CM3D2-Converter-{branch}.zip"
        addon_path = Path(__file__).parent

        response = urllib.request.urlopen(common.URL_MODULE.format(branch=branch))
        zip_file = open(zip_path, 'wb')
        zip_file.write(response.read())
        zip_file.close()
        
        zip_file = zipfile.ZipFile(zip_path, 'r')
        sub_dir = ""
        for path in zip_file.namelist():
            if not sub_dir and os.path.split(os.path.split(path)[0])[1] in ("CM3D2 Converter", "CM3D2_Converter"):
                sub_dir = path
                continue
            if not sub_dir or sub_dir not in path:
                continue
            relative_path = Path(path).relative_to(sub_dir)
            real_path = addon_path / relative_path
            
            # If it is a file
            if os.path.basename(path): # is a file
                file = None
                try:
                    file = open(str(real_path), 'wb') # open() will automatically create it if it does not exist
                except:
                    file = None
                    # Check if the file needs to be updated first
                    with open(str(real_path), 'rb') as old_file:
                        old_hash = hashlib.md5(old_file.read()    ).hexdigest()
                        new_hash = hashlib.md5(zip_file.read(path)).hexdigest()
                    if old_hash != new_hash:
                        # self.is_restart = True
                        if 'Managed' in path:
                            Managed.unload()
                        old_dir = addon_path / '_old'
                        if not old_dir.exists():
                            os.mkdir(old_dir)
                        move_path = old_dir / f'~{random.randint(0, 999999)}.{real_path.name}'
                        shutil.move(real_path, move_path)
                        file = open(str(real_path), 'wb')
                if file is not None:
                    file.write(zip_file.read(path))
                    file.close()
                    
            # If it is a missing directory
            elif not real_path.exists():
                os.mkdir(real_path)

        zip_file.close()

        if self.is_restart:
            filepath = bpy.data.filepath
            command_line = [sys.argv[0]]
            if filepath:
                command_line.append(filepath)
            if self.is_toggle_console:
                py = os.path.join(os.path.dirname(__file__), "console_toggle.py")
                command_line.append('-P')
                command_line.append(py)

            subprocess.Popen(command_line)
            bpy.ops.wm.quit_blender()
        else:
            if compat.IS_LEGACY:
                self.report(type={'INFO'}, message="Blender-CM3D2-Converterを更新しました、再起動して下さい")
            else:
                bpy.ops.preferences.addon_refresh()
                bpy.ops.wm.call_menu(name=INFO_MT_help_cm3d2_converter_reload_notice.bl_idname)
                self.report(type={'INFO'}, message="Blender-CM3D2-Converter updated successfully. Reload scripts to apply changes.")
        return {'FINISHED'}


@compat.BlRegister()
class CNV_OT_show_cm3d2_converter_preference(bpy.types.Operator):
    bl_idname = 'wm.show_cm3d2_converter_preference'
    bl_label = "CM3D2 Converterの設定画面を開く"
    bl_description = "CM3D2 Converterアドオンの設定画面を表示します"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        my_info = None
        for module in addon_utils.modules():
            info = addon_utils.module_bl_info(module)
            if info['name'] == common.ADDON_NAME:
                my_info = info
                break
        bpy.ops.screen.userpref_show()
        area = common.get_request_area(context, compat.pref_type())
        if area and my_info:
            compat.get_prefs(context).active_section = 'ADDONS'
            context.window_manager.addon_search = my_info['name']
            context.window_manager.addon_filter = 'All'
            if 'COMMUNITY' not in context.window_manager.addon_support:
                context.window_manager.addon_support = {'OFFICIAL', 'COMMUNITY'}
            if not my_info['show_expanded']:
                if compat.IS_LEGACY:
                    bpy.ops.wm.addon_expand(module=__package__)
                else:
                    bpy.ops.preferences.addon_expand(module=__package__)
        else:
            self.report(type={'ERROR'}, message="表示できるエリアが見つかりませんでした")
            return {'CANCELLED'}
        return {'FINISHED'}


@compat.BlRegister()
class INFO_MT_help_cm3d2_converter_reload_notice(bpy.types.Menu):
    bl_idname = 'INFO_MT_help_cm3d2_converter_reload_notice'
    bl_label = "CM3D2 Converter Reload Notice"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Scripts must be reloaded to apply changes.")
        layout.label(text="Top Bar > Blender Logo > System > Reload Scripts")
        # layout.separator()
        # layout.operator('wm.call_menu', text="Show me").name = 'TOPBAR_MT_blender_system'