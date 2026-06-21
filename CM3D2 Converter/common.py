import os
import re
import math
import struct
import shutil
from typing import Any
import bpy
import bmesh
import mathutils
import itertools
import unicodedata
from . import fileutil
from . import compat
from .cm3d2_shader import toon_vector_node_tree, com3d2_shader_node_tree, alpha_mixer_node_tree, bind_light_switch
from .cm3d2_data import Handler, ArcHandler


# アドオン情報
bl_info = {}
ADDON_NAME = 'CM3D2 Converter'
BASE_PATH_TEX = 'Assets/texture/texture/'
BRANCH = 'bl_28'
URL_REPOS = 'https://github.com/luvoid/Blender-CM3D2-Converter/'
URL_ATOM = URL_REPOS + 'commits/{branch}.atom'
URL_MODULE = URL_REPOS + 'archive/{branch}.zip'
KISS_ICON = None
PREFS = None
preview_collections = {}
texpath_dict = {}
texpath_default_dict = {}
COM3D2_SHADER_REV = 1

POSE_DATA_DIR = os.path.join(bpy.utils.user_resource('DATAFILES'), ADDON_NAME, 'pose')
TOON_DATA_DIR = os.path.join(bpy.utils.user_resource('DATAFILES'), ADDON_NAME, 'toon')

re_png = re.compile(r'\.[Pp][Nn][Gg](\.\d{3})?$')
re_serial = re.compile(r'(\.\d{3})$')
re_prefix = re.compile(r'^[\/\.]*')
re_path_prefix = re.compile(r'^assets/', re.I)
re_ext_png = re.compile(r'\.png$', re.I)
re_bone1 = re.compile(r'([_ ])\*([_ ].*)\.([rRlL])$')
re_bone2 = re.compile(r'([_ ])([rRlL])([_ ].*)$')


# このアドオンの設定値群を呼び出す
def preferences():
    global PREFS
    if PREFS is None:
        try:
            PREFS = bpy.context.preferences.addons[__package__].preferences
        except KeyError:
            # This can happen when using Blender-as-a-Module
            # which is how the unit-tests work
            from . import AddonPreferences
            _props = {}
            for k, v in AddonPreferences.__annotations__.items():
                if str(type(v)) == '<class \'_PropertyDeferred\'>':
                    kw: dict = v.keywords
                    default = kw['default'] if 'default' in kw.keys() else None
                    _props[k] = default
            class FakeAddonPreferences:
                def __getattribute__(self, name: str) -> Any:
                    return _props[name]
                def __setattr__(self, name: str, value: Any) -> None:
                    if name not in _props.keys():
                        raise AttributeError(self, name)
                    _props[name] = value
            PREFS = FakeAddonPreferences()
    return PREFS


def scene_properties():
    return bpy.context.scene.cm3d2_converter


def kiss_icon():
    global KISS_ICON
    if KISS_ICON is None:
        KISS_ICON = preview_collections['main']['KISS'].icon_id
    return KISS_ICON


# データ名末尾の「.001」などを削除
def remove_serial_number(name, enable=True):
    return re_serial.sub('', name) if enable else name


# データ名末尾の「.001」などが含まれるか判定
def has_serial_number(name):
    return re_serial.search(name) is not None


# 文字列の左右端から空白を削除
def line_trim(line, enable=True):
    return line.strip(' 　\t\r\n') if enable else line


# CM3D2専用ファイル用の文字列書き込み
def write_str(file, raw_str):
    b_str = format(len(raw_str.encode('utf-8')), 'b')
    for i in range(9):
        if len(b_str) > 7:
            file.write(struct.pack('<B', int('1' + b_str[-7:], 2)))
            b_str = b_str[:-7]
        else:
            file.write(struct.pack('<B', int(b_str, 2)))
            break
    file.write(raw_str.encode('utf-8'))

def pack_str(buffer, raw_str):
    b_str = format(len(raw_str.encode('utf-8')), 'b')
    for i in range(9):
        if 7 < len(b_str):
            buffer = buffer + struct.pack('<B', int('1' + b_str[-7:], 2))
            b_str = b_str[:-7]
        else:
            buffer = buffer + struct.pack('<B', int(b_str, 2))
            break
    buffer = buffer + raw_str.encode('utf-8')
    return buffer


# CM3D2専用ファイル用の文字列読み込み
def read_str(file, total_b=""):
    for i in range(9):
        b_str = format(struct.unpack('<B', file.read(1))[0], '08b')
        total_b = b_str[1:] + total_b
        if b_str[0] == '0':
            break
    return file.read(int(total_b, 2)).decode('utf-8')


# ボーン/ウェイト名を Blender → CM3D2
def encode_bone_name(name, enable=True):
    return re.sub(r'([_ ])\*([_ ].*)\.([rRlL])$', r'\1\3\2', name) if enable and name.count('*') == 1 else name


# ボーン/ウェイト名を CM3D2 → Blender
def decode_bone_name(name, enable=True):
    return re.sub(r'([_ ])([rRlL])([_ ].*)$', r'\1*\3.\2', name) if enable else name


# CM3D2用マテリアルを設定に合わせて装飾
def decorate_material(mate, enable=True):
    if not enable or 'shader1' not in mate:
        return

    shader = mate['shader1']
    mate.preview_render_type  = 'FLAT'
    mate.use_backface_culling = 'Outline' not in shader
    mate.use_nodes = True
    is_transparent = any(x in shader for x in ['Trans', 'Cutout'])
    compat.set_transparent(mate, is_transparent)

    # Toon Vector ノードグループ
    toon_vector_ng = mate.node_tree.nodes.new('ShaderNodeGroup')
    toon_vector_ng.node_tree = toon_vector_node_tree()
    toon_vector_ng.location = (-700,260)

    # light 位置のバインド
    bind_light_switch(toon_vector_ng.inputs.get('Light Switch'))

    # COM3D2 Shader ノードグループ
    com3d2_shader_ng = mate.node_tree.nodes.new('ShaderNodeGroup')
    com3d2_shader_ng.node_tree = com3d2_shader_node_tree()
    com3d2_shader_ng.location = (0,320)
    com3d2_shader_ng.width = 180

    # マテリアル出力ノード
    mate_out = mate.node_tree.nodes.new('ShaderNodeOutputMaterial')
    mate_out.location = (440, 350)

    # 透過モードのノードグループ指定と接続
    if is_transparent:
        alpha_mixer_ng = mate.node_tree.nodes.new('ShaderNodeGroup')
        alpha_mixer_ng.node_tree = alpha_mixer_node_tree()
        alpha_mixer_ng.location = (240, 430)
        main_tex = mate.node_tree.nodes.get('_MainTex')
        if main_tex:
            mate.node_tree.links.new(alpha_mixer_ng.inputs.get('Alpha'), main_tex.outputs.get('Alpha'))
        mate.node_tree.links.new(alpha_mixer_ng.inputs.get('Shader'), com3d2_shader_ng.outputs.get('Shader'))
        mate.node_tree.links.new(mate_out.inputs.get('Surface'), alpha_mixer_ng.outputs.get('Shader'))
    else:
        mate.node_tree.links.new(mate_out.inputs.get('Surface'), com3d2_shader_ng.outputs.get('Shader'))

    # インポートされたマテリアル内各要素ノードからの接続
    shader_prop = Handler.get_shader_prop(mate.get('shader1'))
    names = shader_prop['tex_list'] + shader_prop['col_list'] + shader_prop['f_list']
    for key, node in mate.node_tree.nodes.items():
        if not key.startswith('_'):
            continue
        # 指定シェーダーに関係ないノードがあればリンクを外す
        if key not in names:
            for output in node.outputs:
                for link in list(output.links):
                    mate.node_tree.links.remove(link)
            continue
        # 画像ノードの場合
        if type(node) == bpy.types.ShaderNodeTexImage:
            socket = com3d2_shader_ng.inputs.get(key[1:])
            # 画像ノード => COM3D2 Shader (同名のソケットがあれば)
            if socket:
                mate.node_tree.links.new(socket, node.outputs.get('Color'))
            # Toon Calculation(Toon Mapping UV) => 画像ノードベクトル入力 (Toon画像であれば)
            if 'Toon' in node.name:
                mate.node_tree.links.new(node.inputs.get('Vector'), toon_vector_ng.outputs.get('Toon Vector'))
        else:
            # 他Color/Valueノード => COM3D2 Shader (同名のソケットがあれば)
            input_socket = com3d2_shader_ng.inputs.get(key[1:])
            output_socket = node.outputs.get('Color') or node.outputs.get('Value')
            if input_socket and output_socket:
                mate.node_tree.links.new(input_socket, output_socket)


# 画像のおおよその平均色を取得
def get_image_average_color(img, sample_count=10):
    if not len(img.pixels):
        return mathutils.Color([0, 0, 0])

    pixel_count = img.size[0] * img.size[1]
    channels = img.channels

    max_s = 0.0
    max_s_color, average_color = mathutils.Color([0, 0, 0]), mathutils.Color([0, 0, 0])
    seek_interval = pixel_count / sample_count
    for sample_index in range(sample_count):

        index = int(seek_interval * sample_index) * channels
        color = mathutils.Color(img.pixels[index: index + 3])
        average_color += color
        if max_s < color.s:
            max_s_color, max_s = color, color.s

    average_color /= sample_count
    output_color = (average_color + max_s_color) / 2
    output_color.s *= 1.5
    return max_s_color


# 画像のおおよその平均色を取得 (UV版)
def get_image_average_color_uv(img, me=None, mate_index=-1, sample_count=10):
    if not len(img.pixels): return mathutils.Color([0, 0, 0])

    img_width, img_height, img_channel = img.size[0], img.size[1], img.channels

    bm = bmesh.new()
    bm.from_mesh(me)
    uv_lay = bm.loops.layers.uv.active
    uvs = [l[uv_lay].uv[:] for f in bm.faces if f.material_index == mate_index for l in f.loops]
    bm.free()

    if len(uvs) <= sample_count:
        return get_image_average_color(img)

    average_color = mathutils.Color([0, 0, 0])
    max_s = 0.0
    max_s_color = mathutils.Color([0, 0, 0])
    seek_interval = len(uvs) / sample_count
    for sample_index in range(sample_count):

        uv_index = int(seek_interval * sample_index)
        x, y = uvs[uv_index]

        x = math.modf(x)[0]
        if x < 0.0:
            x += 1.0
        y = math.modf(y)[0]
        if y < 0.0:
            y += 1.0

        x, y = int(x * img_width), int(y * img_height)

        pixel_index = ((y * img_width) + x) * img_channel
        color = mathutils.Color(img.pixels[pixel_index: pixel_index + 3])

        average_color += color
        if max_s < color.s:
            max_s_color, max_s = color, color.s

    average_color /= sample_count
    output_color = (average_color + max_s_color) / 2
    output_color.s *= 1.5
    return output_color


def get_cm3d2_dir():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\KISS\カスタムメイド3D2') as key:
            return winreg.QueryValueEx(key, 'InstallPath')[0]
    except:
        return None


def get_com3d2_dir():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\KISS\カスタムオーダーメイド3D2') as key:
            return winreg.QueryValueEx(key, 'InstallPath')[0]
    except:
        return None


def get_pref_cm3d2_dir():
    """
    COM3D2/CM3D2インストールフォルダのパスを返す。設定値があればそれを優先し、なければレジストリから取得して設定値に保存する。
    CM3D2よりCOM3D2を優先する
    """
    prefs = preferences()
    if prefs.cm3d2_path:
        return prefs.cm3d2_path
    root_dir = get_com3d2_dir() or get_cm3d2_dir()
    if root_dir:
        prefs.cm3d2_path = root_dir
    return root_dir


# CM3D2のインストールフォルダを取得＋α
def default_cm3d2_dir(base_dir: str, file_name: str|None, new_ext: str):
    new_ext = new_ext.strip('.')
    if not base_dir:
        cm3d2_path = get_pref_cm3d2_dir()
        if cm3d2_path:
            base_dir = os.path.join(cm3d2_path, 'GameData', '*.' + new_ext)

        if base_dir is None:
            base_dir = '.'

    if file_name:
        base_dir = os.path.join(os.path.split(base_dir)[0], file_name)
    base_dir = os.path.splitext(base_dir)[0] + '.' + new_ext
    return base_dir


# 一時ファイル書き込みと自動バックアップを行うファイルオブジェクトを返す
def open_temporary(filepath, mode, is_backup=False):
    backup_ext = preferences().backup_ext
    if is_backup and backup_ext:
        backup_filepath = filepath + '.' + backup_ext
    else:
        backup_filepath = None
    return fileutil.TemporaryFileWriter(filepath, mode, backup_filepath=backup_filepath)


# ファイルを上書きするならバックアップ処理
def file_backup(filepath, enable=True):
    backup_ext = preferences().backup_ext
    if enable and backup_ext and os.path.exists(filepath):
        shutil.copyfile(filepath, filepath + '.' + backup_ext)


# サブフォルダを再帰的に検索してリスト化
def find_tex_all_files(dir):
    for root, dirs, files in os.walk(dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext == '.tex' or ext == '.png':
                yield os.path.join(root, f)


# テクスチャ置き場のパスのリストを返す
def get_default_tex_paths():
    prefs = preferences()
    default_paths = [prefs.default_tex_path0, prefs.default_tex_path1, prefs.default_tex_path2, prefs.default_tex_path3]
    if not any(default_paths):
        target_dirs = []
        cm3d2_dir = get_pref_cm3d2_dir()

        if cm3d2_dir:
            target_dirs.append(os.path.join(cm3d2_dir, 'GameData', 'texture'))
            target_dirs.append(os.path.join(cm3d2_dir, 'GameData', 'texture2'))
            target_dirs.append(os.path.join(cm3d2_dir, 'Sybaris', 'GameData'))
            target_dirs.append(os.path.join(cm3d2_dir, 'Mod'))

        # com3d2_dir = prefs.com3d2_path
        # if not com3d2_dir:
        #     com3d2_dir = get_cm3d2_dir()
        # if com3d2_dir:
        #     target_dirs.append(os.path.join(com3d2_dir, 'GameData', 'parts'))
        #     target_dirs.append(os.path.join(com3d2_dir, 'GameData', 'parts2'))
        #     target_dirs.append(os.path.join(com3d2_dir, 'MOD'))

        tex_dirs = [path for path in target_dirs if os.path.isdir(path)]

        for index, path in enumerate(tex_dirs):
            setattr(prefs, 'default_tex_path' + str(index), path)
    else:
        tex_dirs = [getattr(prefs, 'default_tex_path' + str(i)) for i in range(4) if getattr(prefs, 'default_tex_path' + str(i))]

    # toon画像フォルダを追加
    tex_dirs.append(TOON_DATA_DIR)

    return tex_dirs


def get_my_pose_path():
    """
    ゲーム内MyPoseパスを返す
    """
    cm3d2_dir = get_pref_cm3d2_dir()
    if cm3d2_dir:
        return os.path.join(cm3d2_dir, 'PhotoModeData', 'MyPose')
    return None


def extract_toon_tex():
    # for COM3D2
    ArcHandler.extract('parts2?.arc', output_dir=TOON_DATA_DIR, target_files=r'toon.*\.tex')
    # for CM3D2
    ArcHandler.extract('texture[23]?.arc', output_dir=TOON_DATA_DIR, target_files=r'toon.*\.tex')


def add_extra_tex_path(path):
    """
    相対パス系のパスリストを追加する
    """
    props = scene_properties()
    props.import_filepaths.add().name = path


def get_extra_tex_paths():
    """
    相対パス系のパスリストを返す
    """
    base_dirs = []
    prefs = preferences()
    props = scene_properties()
    # models/mate 以下フォルダ・親フォルダ以下の指定
    for filepath in props.import_filepaths:
        base_dir = os.path.dirname(filepath.name)
        if prefs.search_tex_path_scope == 'SAME':
            if base_dir not in base_dirs:
                base_dirs.append(base_dir)
        elif prefs.search_tex_path_scope == 'PARENT':
            parent_dir = os.path.dirname(base_dir)
            if parent_dir not in base_dirs:
                base_dirs.append(parent_dir)
    return base_dirs


# テクスチャ置き場の全ファイルを返す
def get_tex_storage_files():
    files = []
    tex_dirs = get_default_tex_paths()
    for tex_dir in tex_dirs:
        tex_dir = bpy.path.abspath(tex_dir)
        files.extend(find_tex_all_files(tex_dir))
    return files


def get_texpath_dict(reload=False):
    """
    利用可能な全tex/pngファイルdictを返却 (探索パス指定は永続キャッシュ、相対探索は一時キャッシュ扱い)
    """
    global texpath_default_dict, texpath_dict
    if reload:
        texpath_default_dict.clear()
        texpath_dict.clear()
    if texpath_dict:
        return texpath_dict
    if not texpath_default_dict:
        texpath_default_dict = build_texpath_dict(get_default_tex_paths())
    if not texpath_dict:
        texpath_dict = texpath_default_dict | build_texpath_dict(get_extra_tex_paths())
    return texpath_dict


def build_texpath_dict(tex_dirs: list):
    """
    指定ディレクトリパスリストから全tex/pngファイルdictを生成
    """
    path_dict: dict = {}
    for tex_dir in tex_dirs:
        for path in find_tex_all_files(tex_dir):
            path = bpy.path.abspath(path)
            file_name = os.path.basename(path).lower()
            # 先に見つけたファイルを優先
            if file_name not in path_dict:
                path_dict[file_name] = path
    return path_dict


def use_texpath_cache(func):
    """
    modelやmateなどインポート時にテクスチャ探索を必要とする処理メソッド用のデコレータ
    """
    def wrapper(self, context, *args, **kwargs):
        global texpath_dict
        texpath_dict.clear()
        props = scene_properties()
        props.import_filepaths.clear()
        try:
            return func(self, context, *args, **kwargs)
        finally:
            texpath_dict.clear()
            props.import_filepaths.clear()
    return wrapper


def clear_texpath_default_dict(self, context):
    """
    設定で探索パスを変更した際に呼ぶキャッシュクリア処理
    """
    global texpath_default_dict
    texpath_default_dict.clear()


def reload_png(img, texpath_dict, png_name):
    png_path = texpath_dict.get(png_name)
    if png_path:
        img.filepath = png_path
        img.reload()
        return True
    return False


def replace_cm3d2_tex(img, texpath_dict: dict=None, reload_path: bool=True) -> bool:
    """replace tex file.
    pngファイルを先に走査し、見つからなければtexファイルを探す.
    texはpngに展開して読み込みを行う.
    reload_path=Trueの場合、png,texファイルが見つからない場合にキャッシュを再構成し、
    再度検索を行う.

    Parameters:
        img (Image): イメージオブジェクト
        texpath_dict (dict): テクスチャパスのdict (キャッシュ)
        reload_path (bool): 見つからない場合にキャッシュを再読込するか

    Returns:
        bool: tex load successful
    """
    if texpath_dict is None:
        texpath_dict = get_texpath_dict()

    if __replace_cm3d2_tex(img, texpath_dict):
        return True
    if reload_path:
        texpath_dict = get_texpath_dict(True)
        return __replace_cm3d2_tex(img, texpath_dict)
    return False


def __replace_cm3d2_tex(img, texpath_dict: dict) -> bool:
    source_name = remove_serial_number(img.name).lower()

    source_png_name = source_name + '.png'
    if reload_png(img, texpath_dict, source_png_name):
        return True

    source_tex_name = source_name + '.tex'
    tex_path = texpath_dict.get(source_tex_name)
    try:
        if tex_path is None:
            return False
        tex_data = load_cm3d2tex(tex_path)
        if tex_data is None:
            return False
        
        png_path = tex_path[:-4] + '.png'
        with open(png_path, 'wb') as png_file:
            png_file.write(tex_data[-1])
        img.filepath = png_path
        img.reload()
        return True
    except:
        pass
    return False


# texファイルの読み込み
def load_cm3d2tex(path, skip_data=False):

    def _create_dds_header_dxt5(width: int, height: int, data_size: int):
        """DXT5用の最小限 of DDSヘッダ(128バイト)を生成"""
        FLAGS_REQUIRED = 0x00000007 | 0x00001000 | 0x00080000
        CAPS_TEXTURE = 0x00001000

        header = bytearray(128)
        header[0:4] = b'DDS '
        struct.pack_into('<I', header, 4, 124)
        struct.pack_into('<I', header, 8, FLAGS_REQUIRED)
        struct.pack_into('<I', header, 12, height)
        struct.pack_into('<I', header, 16, width)
        struct.pack_into('<I', header, 20, data_size)

        struct.pack_into('<I', header, 76, 32)
        struct.pack_into('<I', header, 80, 0x00000004)
        header[84:88] = b'DXT5'

        struct.pack_into('<I', header, 108, CAPS_TEXTURE)
        return bytes(header)

    def _dds_to_png(data: bytes, width: int, height: int) -> bytes:
        import tempfile
        import zlib
        from py_dds import DDSImage
        dds_header = _create_dds_header_dxt5(width, height, len(data))
        full_dds_data = dds_header + data
        tmp = tempfile.NamedTemporaryFile(suffix='.dss', delete=False)
        try:
            tmp.write(full_dds_data)
            tmp.close()
            dds_tex = DDSImage(tmp.name)
            rgba = bytearray(width * height * 4)

            def pixel_collect_callback(x, y, r, g, b, a):
                idx = (y * width + x) * 4
                rgba[idx] = r
                rgba[idx + 1] = g
                rgba[idx + 2] = b
                rgba[idx + 3] = a

            dds_tex.draw(pixel_collect_callback, mip=0)
        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)
        row_stride = width * 4
        flipped_rows = []

        for y in range(height - 1, -1, -1):
            start = y * row_stride
            end = start + row_stride
            flipped_rows.append(b'\x00' + rgba[start:end])

        scanlines = b''.join(flipped_rows)

        # PNGチャンクの構築
        png_signature = b'\x89PNG\r\n\x1a\n'

        ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
        ihdr_chunk = b'IHDR' + ihdr_data
        ihdr_chunk = struct.pack('>I', len(ihdr_data)) + ihdr_chunk + struct.pack('>I', zlib.crc32(ihdr_chunk))

        idat_data = zlib.compress(scanlines)
        idat_chunk = b'IDAT' + idat_data
        idat_chunk = struct.pack('>I', len(idat_data)) + idat_chunk + struct.pack('>I', zlib.crc32(idat_chunk))

        iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', zlib.crc32(b'IEND'))
        return png_signature + ihdr_chunk + idat_chunk + iend_chunk

    with open(path, 'rb') as file:
        header_ext = read_str(file)
        if header_ext != 'CM3D2_TEX':
            return None
        version = struct.unpack('<i', file.read(4))[0]
        read_str(file)

        # default value
        tex_format = 5
        uv_rects = None
        data = None
        if version >= 1010:
            if version >= 1011:
                num_rect = struct.unpack('<i', file.read(4))[0]
                uv_rects = []
                for i in range(num_rect):
                    # x, y, w, h
                    uv_rects.append(struct.unpack('<4f', file.read(4 * 4)))
            width = struct.unpack('<i', file.read(4))[0]
            height = struct.unpack('<i', file.read(4))[0]
            tex_format = struct.unpack('<i', file.read(4))[0]
            if tex_format == 12 and not skip_data:
                png_size = struct.unpack('<i', file.read(4))[0]
                data = file.read(png_size)
                data = _dds_to_png(data, width, height)
        if not data and  not skip_data:
            png_size = struct.unpack('<i', file.read(4))[0]
            data = file.read(png_size)
        return version, tex_format, uv_rects, data


def create_tex(context, mate, node_name, tex_name=None, filepath=None, cm3d2path=None, tex_map_data=None, replace_tex=False, asis_if_exists=False):
    # if mate.use_nodes is False:
    # 	mate.use_nodes = True
    nodes = mate.node_tree.nodes
    tex = nodes.get(node_name)
    if tex is None:
        tex = mate.node_tree.nodes.new(type='ShaderNodeTexImage')
        tex.name = tex.label = node_name
        tex.show_texture = True
        # 特にtoonテクスチャではベクトル0や1がリピート画像の境界で色補完の影響があるため、延長にする
        tex.extension = 'EXTEND'
    elif asis_if_exists:
        return tex

    if tex_name:
        if tex.image is None:
            if os.path.exists(filepath):
                img = bpy.data.images.load(filepath)
                img.name = tex_name
            else:
                img = bpy.data.images.new(tex_name, 128, 128)
                img.filepath = filepath
            img.source = 'FILE'
            tex.image = img
            img['cm3d2_path'] = cm3d2path
        else:
            img = tex.image
            path = img.get('cm3d2_path')
            if path != cm3d2path:
                img['cm3d2_path'] = cm3d2path
                img.filepath = filepath

        tex_map = tex.texture_mapping
        tex_map.translation[0] = tex_map_data[0]
        tex_map.translation[1] = tex_map_data[1]
        tex_map.scale[0] = tex_map_data[2]
        tex_map.scale[1] = tex_map_data[3]

    # tex.color = tex_data['color'][:3]
    # tex.outputs['Color'].default_value = tex_data['color'][:]
    # tex.outputs['ALpha'].default_value = tex_data['color'][3]

        # tex探し
        if replace_tex:
            replaced = replace_cm3d2_tex(tex.image, reload_path=False)
            # TODO 2.8での実施方法を調査. shader editorで十分？

    return tex


def create_col(context, mate, node_name, color, asis_if_exists=False):
    node = mate.node_tree.nodes.get(node_name)
    if node is None:
        node = mate.node_tree.nodes.new(type='ShaderNodeRGB')
        node.name = node.label = node_name
    elif asis_if_exists:
        return node
    node.outputs[0].default_value = color

    return node


def create_float(context, mate, node_name, value, asis_if_exists=False):
    node = mate.node_tree.nodes.get(node_name)
    if node is None:
        node = mate.node_tree.nodes.new(type='ShaderNodeValue')
        node.name = node.label = node_name
    elif asis_if_exists:
        return node
    node.outputs[0].default_value = value

    return node


def setup_material(mate):
    if mate:
        if 'CM3D2 Texture Expand' not in mate:
            mate['CM3D2 Texture Expand'] = True
        mate['COM3D2 Shader Rev'] = COM3D2_SHADER_REV

        mate.use_nodes = True


def setup_image_name(img):
    """イメージの名前から拡張子を除外する"""
    # consider case with serial number. ex) sample.png.001
    img.name = re_png.sub(r'\1', img.name)


def get_tex_cm3d2path(filepath):
    return BASE_PATH_TEX + os.path.basename(filepath)


def to_cm3d2path(path):
    path = path.replace('\\', '/')
    path = re_prefix.sub('', path)
    if not re_path_prefix.search(path):
        path = get_tex_cm3d2path(path)
    return path


# col f タイプの設定値を値に合わせて着色
def set_texture_color(slot):
    if not slot or not slot.texture or slot.use:
        return

    slot_type = 'col' if slot.use_rgb_to_intensity else 'f'
    tex = slot.texture
    base_name = remove_serial_number(tex.name)
    tex.type = 'BLEND'

    if hasattr(tex, 'progression'):
        tex.progression = 'DIAGONAL'
    tex.use_color_ramp = True
    tex.use_preview_alpha = True
    elements = tex.color_ramp.elements

    element_count = 4
    if element_count < len(elements):
        for i in range(len(elements) - element_count):
            elements.remove(elements[-1])
    elif len(elements) < element_count:
        for i in range(element_count - len(elements)):
            elements.new(1.0)

    elements[0].position, elements[1].position, elements[2].position, elements[3].position = 0.2, 0.21, 0.25, 0.26

    if slot_type == 'col':
        elements[0].color = [0.2, 1, 0.2, 1]
        elements[-1].color = slot.color[:] + (slot.diffuse_color_factor, )
        if 0.3 < mathutils.Color(slot.color[:3]).v:
            elements[1].color, elements[2].color = [0, 0, 0, 1], [0, 0, 0, 1]
        else:
            elements[1].color, elements[2].color = [1, 1, 1, 1], [1, 1, 1, 1]

    elif slot_type == 'f':
        elements[0].color = [0.2, 0.2, 1, 1]
        multi = 1.0
        if base_name == '_OutlineWidth':
            multi = 200
        elif base_name == '_RimPower':
            multi = 1.0 / 30.0
        value = slot.diffuse_color_factor * multi
        elements[-1].color = [value, value, value, 1]
        if 0.3 < value:
            elements[1].color, elements[2].color = [0, 0, 0, 1], [0, 0, 0, 1]
        else:
            elements[1].color, elements[2].color = [1, 1, 1, 1], [1, 1, 1, 1]


# 必要なエリアタイプを設定を変更してでも取得
def get_request_area(context, request_type, except_types=None):
    if except_types is None:
        except_types = ['VIEW_3D', 'PROPERTIES', 'INFO', 'PREFERENCES']

    request_areas = [(a, a.width * a.height) for a in context.screen.areas if a.type == request_type]
    candidate_areas = [(a, a.width * a.height) for a in context.screen.areas if a.type not in except_types]

    return_areas = request_areas[:] if len(request_areas) else candidate_areas
    if not len(return_areas):
        return None

    return_areas.sort(key=lambda i: i[1])
    return_area = return_areas[-1][0]
    return_area.type = request_type
    return return_area


# 複数のデータを完全に削除
def remove_data(target_data):
    try:
        target_data = target_data[:]
    except:
        target_data = [target_data]

    for data in target_data:
        try:
            if isinstance(data, bpy.types.Object):
                if data.name in bpy.context.scene.collection.objects:
                    bpy.context.scene.collection.objects.unlink(data)
        except ReferenceError:
            pass

    # https://developer.blender.org/T49837
    # によると、xxx.remove(data, do_unlink=True)で十分
    #
    # for data in target_data:
    # 	users = getattr(data, 'users')
    # 	if users and 'user_clear' in dir(data):
    # 		data.user_clear()

    #for data in target_data:
    #    for data_str in dir(bpy.data):
    #        if not data_str.endswith('s'):
    #            continue
    #        try:
    #            data_collection = getattr(bpy.data.actions, data_str)
    #            if data.__class__.__name__ == data_collection[0].__class__.__name__:
    #                data_collection.remove(data, do_unlink=True)
    #                break
    #        except:
    #            pass
    
    for data in target_data:
        for data_str in dir(bpy.data):
            if not data_str.endswith('s'):
                continue
            try:
                if data.__class__.__name__ == eval('bpy.data.%s[0].__class__.__name__' % data_str):
                    exec('bpy.data.%s.remove(data, do_unlink=True)' % data_str)
                    break
            except:
                pass


# オブジェクトのマテリアルを削除/復元するクラス
class material_restore:
    def __init__(self, ob):
        self.object = ob

        self.slots = [slot.material if slot.material else None for slot in ob.material_slots]

        self.mesh_data = []
        for index, slot in enumerate(ob.material_slots):
            mesh_datum = []
            for face in ob.data.polygons:
                if face.material_index == index:
                    mesh_datum.append(face.index)
            self.mesh_data.append(mesh_datum)

        with bpy.context.temp_override(object=ob):
            for __ in ob.material_slots[:]:
                bpy.ops.object.material_slot_remove()

    def restore(self):
        with bpy.context.temp_override(object=self.object):
            for __ in self.object.material_slots[:]:
                bpy.ops.object.material_slot_remove()

            for index, mate in enumerate(self.slots):
                bpy.ops.object.material_slot_add()
                slot = self.object.material_slots[index]
                if slot:
                    slot.material = mate
                for face_index in self.mesh_data[index]:
                    self.object.data.polygons[face_index].material_index = index


# 現在のレイヤー内のオブジェクトをレンダリングしなくする/戻す
class hide_render_restore:
    def __init__(self, render_objects=[]):
        try:
            render_objects = render_objects[:]
        except:
            render_objects = [render_objects]

        if not len(render_objects):
            render_objects = bpy.context.selected_objects[:]

        self.render_objects = render_objects[:]
        self.render_object_names = [ob.name for ob in render_objects]

        self.rendered_objects = []
        for ob in render_objects:
            if ob.hide_render:
                self.rendered_objects.append(ob)
                ob.hide_render = False

        self.hide_rendered_objects = []
        clct_children = bpy.context.scene.collection.children
        for ob in bpy.data.objects:
            if ob.name not in self.render_object_names and not ob.hide_render:
                # ble-2.8ではlayerではなく、collectionからのリンクで判断
                for clct in bpy.context.window.view_layer.layer_collection.children:
                    if clct.exclude is False and ob.name in clct_children[clct.name].objects.keys():
                        self.hide_rendered_objects.append(ob)
                        ob.hide_render = True
                        break

    def restore(self):
        for ob in self.rendered_objects:
            ob.hide_render = True
        for ob in self.hide_rendered_objects:
            ob.hide_render = False


# 指定エリアに変数をセット
def set_area_space_attr(area, attr_name, value):
    if not area:
        return
    for space in area.spaces:
        if space.type == area.type:
            space.__setattr__(attr_name, value)
            break


# スムーズなグラフを返す1
def in_out_quad_blend(f):
    if f <= 0.5:
        return 2.0 * math.sqrt(f)
    f -= 0.5
    return 2.0 * f * (1.0 - f) + 0.5


# スムーズなグラフを返す2
def bezier_blend(f):
    return math.sqrt(f) * (3.0 - 2.0 * f)


# 三角関数でスムーズなグラフを返す
def trigonometric_smooth(x):
    return math.sin((x - 0.5) * math.pi) * 0.5 + 0.5


# エクスポート例外クラス
class CM3D2ExportError(Exception):
    def __init__(self, message, *args):
        super().__init__(message, *args)
        self.message = message

class CM3D2ImportError(Exception):
    def __init__(self, message, *args):
        super().__init__(message, *args)
        self.message = message


# ノード取得クラス
class NodeHandler:
    node_name: bpy.props.StringProperty(name='NodeName')

    def get_node(self, context):
        mate = context.material
        if mate and mate.use_nodes:
            return mate.node_tree.nodes.get(self.node_name)

            # if node is None:
            # # 見つからない場合は、シリアル番号付きのノードを探す
            # prefix = self.node_name + '.'
            # for n in nodes:
            # 	if n.name.startwith(prefix):
            # 		node = n
            # 		break

        return None

#@compat.BlRegister()
class CNV_UL_generic_selector(bpy.types.UIList):
    bl_options     = {'DEFAULT_CLOSED'}

    # Constants (flags)
    # Be careful not to shadow FILTER_ITEM!
    #bitflag_soft_filter = 1073741824 >> 0
    bitflag_soft_filter  = 1073741824 >> 3

    bitflag_forced_value = 1073741824 >> 10
    bitflag_forced_true  = 1073741824 >> 11
    bitflag_forced_false = 1073741824 >> 12

    
    cached_values = {}
    expanded_layout = False

    # Custom properties, saved with .blend file.
    use_filter_name_reverse: bpy.props.BoolProperty(
        name="Reverse Name",
        default=False,
        options=set(),
        description="Reverse name filtering",
    )
    #use_filter_deform: bpy.props.BoolProperty(
    #    name="Only Deform",
    #    default=True,
    #    options=set(),
    #    description="Only show deforming vertex groups",
    #)
    #use_filter_deform_reverse: bpy.props.BoolProperty(
    #    name="Other",
    #    default=False,
    #    options=set(),
    #    description="Only show non-deforming vertex groups",
    #)
    #use_filter_empty: bpy.props.BoolProperty(
    #    name="Filter Empty",
    #    default=False,
    #    options=set(),
    #    description="Whether to filter empty vertex groups",
    #)
    #use_filter_empty_reverse: bpy.props.BoolProperty(
    #    name="Reverse Empty",
    #    default=False,
    #    options=set(),
    #    description="Reverse empty filtering",
    #)
    
    # This allows us to have mutually exclusive options, which are also all disable-able!
    def _gen_order_update(name1, name2):
        def _u(self, ctxt):
            if (getattr(self, name1)):
                setattr(self, name2, False)
        return _u
    use_order_name: bpy.props.BoolProperty(
        name="Name", default=False, options=set(),
        description="Sort groups by their name (case-insensitive)",
        update=_gen_order_update('use_order_name', 'use_order_importance'),
    )
    use_filter_orderby_invert: bpy.props.BoolProperty(
        name="Order by Invert",
        default=False,
        options=set(),
        description="Invert the sort by order"
    )
    #use_order_importance: bpy.props.BoolProperty(
    #    name="Importance",
    #    default=False,
    #    options=set(),
    #    description="Sort groups by their average weight in the mesh",
    #    update=_gen_order_update("use_order_importance", "use_order_name"),
    #)
        
    # Usual draw item function.
    def draw_item(self, context, layout, data, item, icon_value, active_data, active_propname, index = 0, flt_flag = 0):
        # Just in case, we do not use it here!
        self.use_filter_invert = False

        # assert(isinstance(item, bpy.types.VertexGroup)
        #vgroup = getattr(data, 'matched_vgroups')[item.index]
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Here we use one feature of new filtering feature: it can pass data to draw_item, through flt_flag
            # parameter, which contains exactly what filter_items set in its filter list for this item!
            # In this case, we show empty groups grayed out.
            cached_value = self.cached_values.get(item.name, None)
            if (cached_value != None) and (cached_value != item.value):
                item.preferred = item.value

            force_values = flt_flag & self.bitflag_forced_value
            print("GET force_values =", force_values)
            if force_values:
                print("FORCE VALUES")
                if flt_flag & self.bitflag_forced_true:
                    item.value = True
                elif flt_flag & self.bitflag_forced_false:
                    item.value = False
                else:
                    item.value = item.preferred

            self.cached_values[item.name] = item.value

            if flt_flag & self.bitflag_soft_filter:
                row = layout.row()
                row.enabled = False
                #row.alignment = 'LEFT'
                row.prop(item, 'value', text=item.name, icon=item.icon)
            else:
                layout.prop(item, 'value', text=item.name, icon=item.icon)
            
            #layout.prop(item, 'value', text=item.name, icon=item.icon)
            icon = 'RADIOBUT_ON' if item.preferred else 'RADIOBUT_OFF'
            layout.prop(item, 'preferred', text="", icon=icon, emboss=False)

    def draw_filter(self, context, layout):
        # Nothing much to say here, it's usual UI code...
        row = layout.row()
        if not self.expanded_layout:
            layout.active = True
            layout.enabled = True
            row.active = True
            row.enabled = True
            self.expanded_layout = True

        subrow = row.row(align=True)
        subrow.prop(self, 'filter_name', text="")
        icon = 'ZOOM_OUT' if self.use_filter_name_reverse else 'ZOOM_IN'
        subrow.prop(self, 'use_filter_name_reverse', text="", icon=icon)

        #subrow = row.row(align=True)
        #subrow.prop(self, 'use_filter_deform', toggle=True)
        #icon = 'ZOOM_OUT' if self.use_filter_deform_reverse else 'ZOOM_IN'
        #subrow.prop(self, 'use_filter_deform_reverse', text="", icon=icon)

        #subrow = row.row(align=True)
        #subrow.prop(self, 'use_filter_empty', toggle=True)
        #icon = 'ZOOM_OUT' if self.use_filter_empty_reverse else 'ZOOM_IN'
        #subrow.prop(self, 'use_filter_empty_reverse', text="", icon=icon)

        row = layout.row(align=True)
        row.label(text="Order by:")
        row.prop(self, 'use_order_name', toggle=True)
        #row.prop(self, 'use_order_importance', toggle=True)
        icon = 'TRIA_UP' if self.use_filter_orderby_invert else 'TRIA_DOWN'
        row.prop(self, 'use_filter_orderby_invert', text="", icon=icon)

    def filter_items(self, context, data, propname):
        # This function gets the collection property (as the usual tuple (data, propname)), and must return two lists:
        # * The first one is for filtering, it must contain 32bit integers were self.bitflag_filter_item marks the
        #   matching item as filtered (i.e. to be shown), and 31 other bits are free for custom needs. Here we use the
        #   first one to mark VGROUP_EMPTY.
        # * The second one is for reordering, it must return a list containing the new indices of the items (which
        #   gives us a mapping org_idx -> new_idx).
        # Please note that the default UI_UL_list defines helper functions for common tasks (see its doc for more info).
        # If you do not make filtering and/or ordering, return empty list(s) (this will be more efficient than
        # returning full lists doing nothing!).
        items = getattr(data, propname)
        
        #if self.armature == None:
        #    target_ob, source_ob = common.get_target_and_source_ob(context)
        #    armature_ob = target_ob.find_armature() or source_ob.find_armature()
        #    self.armature = armature_ob and armature_ob.data or False
        #
        #if not self.local_bone_names:
        #    target_ob, source_ob = common.get_target_and_source_ob(context)
        #    bone_data_ob = (target_ob.get('LocalBoneData:0') and target_ob) or (source_ob.get('LocalBoneData:0') and source_ob) or None
        #    if bone_data_ob:
        #        local_bone_data = model_export.CNV_OT_export_cm3d2_model.local_bone_data_parser(model_export.CNV_OT_export_cm3d2_model.indexed_data_generator(bone_data_ob, prefix='LocalBoneData:'))
        #        self.local_bone_names = [ bone['name'] for bone in local_bone_data ]
        
        if not self.cached_values:
            self.cached_values = { item.name: item.value for item in items }
        #vgroups = [ getattr(data, 'matched_vgroups')[item.index][0]   for item in items ]
        helper_funcs = bpy.types.UI_UL_list

        # Default return values.
        flt_flags = []
        flt_neworder = []

        # Pre-compute of vgroups data, CPU-intensive. :/
        #vgroups_empty = self.filter_items_empty_vgroups(context, vgroups)

        # Filtering by name
        if self.filter_name:
            flt_flags = helper_funcs.filter_items_by_name(self.filter_name, self.bitflag_filter_item, items, 'name',
                                                          reverse=self.use_filter_name_reverse)
        if not flt_flags:
            flt_flags = [self.bitflag_filter_item] * len(items)
        
        #for idx, vg in enumerate(items):
        #    # Filter by deform.
        #    if self.use_filter_deform:
        #        flt_flags[idx] |= self.VGROUP_DEFORM
        #        if self.use_filter_deform:
        #            if self.armature and self.armature.get(vg.name):
        #                if not self.use_filter_deform_reverse:
        #                    flt_flags[idx] &= ~self.VGROUP_DEFORM
        #            elif bone_data_ob and (vg.name in self.local_bone_names):
        #                if not self.use_filter_deform_reverse:
        #                    flt_flags[idx] &= ~self.VGROUP_DEFORM
        #            elif self.use_filter_deform_reverse or (not self.armature and not self.local_bone_names):
        #                flt_flags[idx] &= ~self.VGROUP_DEFORM
        #    else:
        #        flt_flags[idx] &= ~self.VGROUP_DEFORM
        #
        #    # Filter by emptiness.
        #    #if vgroups_empty[vg.index][0]:
        #    #    flt_flags[idx] |= self.VGROUP_EMPTY
        #    #    if self.use_filter_empty and self.use_filter_empty_reverse:
        #    #        flt_flags[idx] &= ~self.bitflag_filter_item
        #    #elif self.use_filter_empty and not self.use_filter_empty_reverse:
        #    #    flt_flags[idx] &= ~self.bitflag_filter_item
        
        # Reorder by name or average weight.
        if self.use_order_name:
            flt_neworder = helper_funcs.sort_items_by_name(items, 'name')
        #elif self.use_order_importance:
        #    _sort = [(idx, vgroups_empty[vg.index][1]) for idx, vg in enumerate(vgroups)]
        #    flt_neworder = helper_funcs.sort_items_helper(_sort, lambda e: e[1], True)

        return flt_flags, flt_neworder



@compat.BlRegister()
class CNV_SelectorItem(bpy.types.PropertyGroup):

    name: bpy.props.StringProperty(name="Name", default="Unknown")
    value: bpy.props.BoolProperty(name="Value", default=True)
    index: bpy.props.IntProperty(name="Index", default=-1)
    preferred: bpy.props.BoolProperty(name="Prefered", default=True)
    icon: bpy.props.StringProperty(name="Icon", default='NONE')

    filter0: bpy.props.BoolProperty(name="Filter 0", default=False)
    filter1: bpy.props.BoolProperty(name="Filter 1", default=False)
    filter2: bpy.props.BoolProperty(name="Filter 2", default=False)
    filter3: bpy.props.BoolProperty(name="Filter 3", default=False)

    sort0: bpy.props.FloatProperty(name="Sort 0", default=0.0)
    sort1: bpy.props.FloatProperty(name="Sort 1", default=0.0)
    sort2: bpy.props.FloatProperty(name="Sort 2", default=0.0)
    sort3: bpy.props.FloatProperty(name="Sort 3", default=0.0)


@compat.BlRegister()
class CNV_FilePathItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()


# luvoid : for loop helper returns values with matching keys
def values_of_matched_keys(dict1, dict2):
    value_list = []
    items1 = dict1.items()
    items2 = dict2.items()
    if len(items1) <= len(items2): 
        items1.reverse()
        for k1, v1 in items1:
            for i in range(len(items2)-1, 0-1, -1):
                k2, v2 = items2[i]
                if k1 == k2:
                    value_list.append((v1,v2))
                    del items2[i]
    else:
        items2.reverse()
        for k2, v2 in items2:
            for i in range(len(items1)-1, 0-1, -1):
                k1, v1 = items1[i]
                if k1 == k2:
                    value_list.append((v1,v2))
                    del items1[i]
    
    value_list.reverse()
    return value_list


# luvoid : helper to easily get source and target objects
def get_target_and_source_ob(context: bpy.context, copyTarget=False, copySource=False):
    target_ob: bpy.types.Object = None
    source_ob: bpy.types.Object = None
    target_original_ob: bpy.types.Object = None
    source_original_ob: bpy.types.Object = None

    selected_objects = list(context.selected_objects)
    
    target_original_ob = context.active_object
    if copyTarget:
        target_ob = target_original_ob.copy()
        target_ob.data = target_ob.data.copy()
        compat.link(context.scene, target_ob)
        context.view_layer.update()
        #bpy.ops.object.select_all(action='DESELECT')
        #compat.set_select(target_original_ob, select=True)
        #bpy.ops.object.duplicate()
        #target_ob = context.active_object
    else:
        target_ob = target_original_ob

    for ob in selected_objects:
        if ob != target_ob:
            source_original_ob = ob
            break
    
    if copySource:
        source_ob = source_original_ob.copy()
        new_data = source_original_ob.data.copy()
        print(f"new_data = {new_data.shape_keys}")
        source_ob.data = new_data
        print(f"source_ob.data = {source_ob.data.shape_keys}")
        compat.link(context.scene, source_ob)
        context.view_layer.update()
        #bpy.ops.object.select_all(action='DESELECT')
        #compat.set_select(source_original_ob, select=True)
        #bpy.ops.object.duplicate()
        #print(f"duplicated_object = {context.active_object}")
        #source_ob = context.active_object
    else:
        source_ob = source_original_ob
    
    
    bpy.ops.object.select_all(action='DESELECT')
    for obj in selected_objects:
        compat.set_select(obj, select=True)
    
    compat.set_active(context, target_ob)
    compat.set_select(target_ob, select=True)
    compat.set_select(source_ob, select=True)
    if copyTarget:
        compat.set_select(target_original_ob, select=False)
    if copySource:
        compat.set_select(source_original_ob, select=False)
    
    to_return = [target_ob, source_ob]
    if copyTarget:
        to_return.append(target_original_ob)
    if copySource:
        to_return.append(source_original_ob)
    return tuple(to_return)


# luvoid
def is_descendant_of(bone, ancestor) -> bool:
    """Returns true if a bone is the descendant of the given ancestor"""
    while bone.parent:
        bone = bone.parent
        if bone.name == ancestor.name:
            return True
    return False


def get_outliner_selection(context: bpy.types.Context, object_type: str = '') -> tuple[list[bpy.types.Object], bpy.types.Object | None]:
    """
    Outliner上のhideオブジェクトも含めた選択オブジェクトの返却
    """
    selected_in_view = set(context.selected_objects)
    active_in_view = context.active_object
    scr = context.screen
    areas = [area for area in scr.areas if area.type == 'OUTLINER']
    regions = [region for region in areas[0].regions if region.type == 'WINDOW']
    with context.temp_override(area=areas[0], region=regions[0], screen=scr):
        selected_in_outliner = set(x for x in context.selected_ids if isinstance(x, bpy.types.Object))
        selected = list(selected_in_view | selected_in_outliner)
        active_in_outliner = context.active_object
        active = active_in_view or active_in_outliner
        if object_type:
            selected = [x for x in selected if x.type == object_type]
            if active and active.type != object_type:
                active = None
        return selected, active


def handler_append(handlers, func):
    """
    フック関数をハンドラに登録するヘルパー関数
    """
    handler_remove(handlers, func)
    handlers.append(func)


def handler_remove(handlers, func):
    """
    フック関数をハンドラから削除するヘルパー関数
    """
    func_name = func.__name__
    for h in list(handlers):
        if h.__name__ == func_name:
            handlers.remove(h)


def get_width(text: str) -> int:
    """全角=2、半角=1 として文字列の幅を計算する"""
    return sum(2 if unicodedata.east_asian_width(c) in ('F', 'W', 'A') else 1 for c in text)


def wrap_label(ui: bpy.types.UILayout, text: str, indent: str = '', width: int|None = None, **kwargs):
    """
    指定幅に合わせて改行してラベル出力する(UILayout.labelを複数回実施する)
    ※text指定値は翻訳済みのものを渡す ex. wrap_label(text=_("..."))
    """
    size = get_region_size(width=width)
    if 'icon' in kwargs or 'icon_value' in kwargs:
        size -= 4

    available_size = size - get_width(indent)
    if available_size <= 0:
        available_size = 1

    raw_lines = text.split('\n')
    final_lines = []

    for raw_line in raw_lines:
        if not raw_line:
            final_lines.append('')
            continue

        # tokensにワードを分割する。全角は1文字1ワードとする。
        tokens = []
        for width, group in itertools.groupby(raw_line, get_width):
            chunk = ''.join(group)
            if width == 1:
                words = chunk.split(' ')
                for i, w in enumerate(words):
                    if w:
                        tokens.append(w)
                    if i < len(words) - 1:
                        tokens.append(' ')
            else:
                tokens.extend(list(chunk))

        # tokens を指定幅ごとに行に分配する
        current_line = []
        current_width = 0
        for token in tokens:
            token_width = get_width(token)

            if not current_line and token == ' ':
                continue

            if current_width + token_width > available_size:
                if current_line:
                    final_lines.append(''.join(current_line))
                if token == ' ':
                    current_line = []
                    current_width = 0
                else:
                    current_line = [token]
                    current_width = token_width
            else:
                current_line.append(token)
                current_width += token_width
        if current_line:
            final_lines.append(''.join(current_line))

    for i, line in enumerate(final_lines):
        ui.label(text=indent + line.rstrip(), **kwargs)
        if i == 0:
            if 'icon' in kwargs or 'icon_value' in kwargs:
                kwargs['icon'] = 'BLANK1'


def get_region_size(width: int|None = None) -> int:
    """
    context.region に描画可能な文字列の幅を返却する
    """
    context = bpy.context
    margin = 0
    if width is not None:
        # ダイアログの場合、検知できないためダイアログに指定したwidthをそのまま使用する前提
        pass
    elif context.area.type == 'PREFERENCES':
        margin = 36
        width = getattr(context.region, 'width', 600)
    elif context.area.type == 'PROPERTIES':
        margin = 79
        width = getattr(context.region, 'width', 400)
    elif context.area.type == 'VIEW_3D':
        margin = 50
        width = getattr(context.region, 'width', 400)
    else:
        width = 600
    ui_scale = context.preferences.view.ui_scale
    content_px = max(100, width - int(margin * ui_scale))
    px_per_unit = 5.6 * ui_scale
    size = max(10, int(content_px / px_per_unit))
    #print(context.area.type, width, margin, content_px, size)
    return size
