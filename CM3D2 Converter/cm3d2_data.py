"""CM3D2/COM3D2用のデータ構造を扱うデータクラス"""
import copy
import glob
import os
import pickle
import re
import struct
import bpy
from . import common
from .translations import *

SHADER_NAMES_CM3D2 = [
    'CM3D2/Toony_Lighted',
    'CM3D2/Toony_Lighted_Hair',
    'CM3D2/Toony_Lighted_Trans',
    'CM3D2/Toony_Lighted_Trans_NoZ',
    'CM3D2/Toony_Lighted_Outline',
    'CM3D2/Toony_Lighted_Outline_Trans',
    'CM3D2/Toony_Lighted_Hair_Outline',
    'CM3D2/Lighted_Trans',
    'CM3D2/Lighted',
    'Unlit/Texture',
    'Unlit/Transparent',
    'CM3D2/Mosaic',
    'CM3D2/Man',
    'Diffuse',
    'Transparent/Diffuse',
    'CM3D2_Debug/Debug_CM3D2_Normal2Color',
]
SHADER_NAMES_COM3D2 = [
    'CM3D2/Toony_Lighted',
    'CM3D2/Toony_Lighted_Hair',
    'CM3D2/Toony_Lighted_Trans',
    'CM3D2/Toony_Lighted_Trans_NoZ',
    'CM3D2/Toony_Lighted_Trans_NoZTest',
    'CM3D2/Toony_Lighted_Outline',
    'CM3D2/Toony_Lighted_Outline_Tex',
    'CM3D2/Toony_Lighted_Hair_Outline',
    # 'CM3D2/Toony_Lighted_Hair_Outline_Tex',
    'CM3D2/Toony_Lighted_Outline_Trans',
    'CM3D2/Toony_Lighted_Cutout_AtC',
    'CM3D2/Lighted_Cutout_AtC',
    'CM3D2/Lighted_Trans',
    'CM3D2/Lighted',
    'Unlit/Texture',
    'Unlit/Transparent',
    'CM3D2/Mosaic',
    'CM3D2/Man',
    'Diffuse',
    'Transparent/Diffuse',
    'CM3D2_Debug/Debug_CM3D2_Normal2Color',
]
TOON_TEXES = [
    'NoTex', 'ToonBlueA1', 'ToonBlueA2', 'ToonBrownA1', 'ToonGrayA1',
    'ToonGreenA1', 'ToonGreenA2', 'ToonGreenA3',
    'ToonOrangeA1',
    'ToonPinkA1', 'ToonPinkA2', 'ToonPurpleA1',
    'ToonRedA1', 'ToonRedA2',
    'ToonRedmmm1', 'ToonRedmm1', 'ToonRedm1',
    'ToonYellowA1', 'ToonYellowA2', 'ToonYellowA3', 'ToonYellowA4',
    'ToonFace',  # 'ToonFace002',
    'ToonSkin',  # 'ToonSkin002',
    'ToonBlackA1',
    'ToonFace_shadow',
    'ToonDress_shadow',
    'ToonSkin_Shadow',
    'ToonBlackMM1', 'ToonBlackM1', 'ToonGrayMM1', 'ToonGrayM1',
    'ToonPurpleMM1', 'ToonPurpleM1',
    'ToonSilverA1',
    'ToonDressMM_Shadow', 'ToonDressM_Shadow',
]
PROPS = {
    '_MainTex': {
        'type': 'tex',
        'desc': "面の色を決定するテクスチャを指定。普段テスクチャと呼んでいるものは基本コレです。テクスチャパスは適当でも動きます。しかし、テクスチャ名はきちんと決めましょう。",
    },
    '_ToonRamp': {
        'type': 'tex',
        'desc': "暗い部分に乗算するグラデーション画像を指定します。",
    },
    '_ShadowTex': {
        'type': 'tex',
        'desc': "陰部分の面の色を決定するテクスチャを指定。「_ShadowRateToon」で範囲を指定します。",
    },
    '_ShadowRateToon': {
        'type': 'tex',
        'desc': "「_ShadowTex」を有効にする部分を指定します。黒色で有効、白色で無効。",
    },
    '_OutlineTex': {
        'type': 'tex',
        'desc': "アウトラインを表現するためのテクスチャを指定。",
    },
    '_OutlineToonRamp': {
        'type': 'tex',
        'desc': "_OutlineTexの暗い部分に乗算するグラデーション画像を指定します。",
    },
    '_HiTex': {
        'type': 'tex',
        'desc': "ハイライトのテクスチャを指定。",
    },
    '_RenderTex': {
        'type': 'tex',
        'desc': "モザイクシェーダーにある設定値。特に設定の必要なし。",
    },
    '_Color': {
        'type': 'col',
        'desc': "面の色を指定。白色で無効。基本的に白色で良いでしょう。",
    },
    '_ShadowColor': {
        'type': 'col',
        'desc': "影の色を指定。白色で無効。別の物体に遮られてできた「影」の色です。",
    },
    '_RimColor': {
        'type': 'col',
        'desc': "リムライトの色を指定。リムライトとは縁にできる光の反射のことです。",
    },
    '_OutlineColor': {
        'type': 'col',
        'desc': "輪郭線の色を指定。黒にするか、テクスチャの明度を落としたものを指定するとより良いでしょう。",
    },
    '_Shininess': {
        'type': 'f',
        'desc': "スペキュラーの強さを指定。0.0～1.0で指定。スペキュラーとは面の角度と光源の角度によってできるハイライトのことです。金属、皮、ガラスなどに使うと良いでしょう。",
        'presets': [0, 0.1, 0.5, 1, 5],
        # 'default': 0, 'step': 1, 'precision': 2,
        # 'min': -100, 'soft_min': -100,
        # 'max': 100, 'soft_max': 100,
    },
    '_OutlineWidth': {
        'type': 'f',
        'desc': "輪郭線の太さを指定。0.002は太め、0.001は細め。",
        'presets': [0.0001, 0.001, 0.0015, 0.002],
        'dispExact': True,
        # 'default': 0, 'step': 0.001, 'precision': 4,
        # 'min': 0, 'soft_min': 1,
        # 'max': 0, 'soft_max': 1,
    },
    '_RimPower': {
        'type': 'f',
        'desc': "リムライトの強さを指定。この値は10以上なことも多いです。0に近い値だと正常に表示されません。",
        'presets': [0, 25, 50, 100],  # 1, 10, 20, 30
        # 'default': 0, 'step': 1, 'precision': 2,
        # 'min': -100, 'soft_min': -100,
        # 'max': 100, 'soft_max': 100,
    },
    '_RimShift': {
        'type': 'f',
        'desc': "リムライトの幅を指定。0.0～1.0で指定。0.5でもかなり強い。",
        'presets': [0, 0.25, 0.5, 0.75, 1],  # 0.0, 0.25, 0.5, 0.75, 1.0
        # 'default': 0, 'step': 1, 'precision': 2,
        # 'min': -100, 'soft_min': -100,
        # 'max': 100, 'soft_max': 100,
    },
    '_FloatValue1': {
        'type': 'f',
        'desc': "モザイクの粗さ",
        'presets': [0, 100, 200],
        # 'default': 0, 'step': 1, 'precision': 2,
        # 'min': -100, 'soft_min': -100,
        # 'max': 100, 'soft_max': 100,
    },
    '_Cutoff': {
        'type': 'f',
        'desc': "アルファのカットオフ値。アルファ値がこの値より大きい部分だけがレンダリングされる",
        'presets': [0, 0.1, 0.5, 1, 5],
        # 'default': 0, 'step': 1, 'precision': 2,
        # 'min': -100, 'soft_min': -100,
        # 'max': 100, 'soft_max': 100,
    },
    # '_Cutout': "アルファのカットオフ値。アルファ値がこの値より大きい部分だけがレンダリングされる",
    '_ZTest': {
        'type': 'f',
        'desc': "深度テストの実行方法を指定する。",
        'disableSlider': True,
        'preset_enums': [
            (0, 'Disabled:0', "深度テストを無効にし、全てのオブジェクトを描画する"),
            (1, 'Never:1', "描画しない"),
            (2, 'Less:2', "奥にある場合に描画する"),
            (3, 'Equal:3', "既存のオブジェクトと距離が同じ場合に描画する"),
            (4, 'LessEqual:4', "等しいか、手前にある場合に描画する（デフォルト）"),
            (5, 'Greater:5', "手前にある場合に描画する"),
            (6, 'NotEqual:6', "距離が等しくない場合に描画する"),
            (7, 'GreaterEqual:7', "等しいか、奥にある場合に描画する"),
            (8, 'Always:8', "奥行きを無視して、常に描画する")
        ],
    },
    '_FloatValue2': {
        'type': 'f',
        'presets': [-15, 0, 1, 15],
        # 'default': 0, 'step': 1, 'precision': 2,
        # 'min': -100, 'soft_min': -100,
        # 'max': 100, 'soft_max': 100,
    },
    '_FloatValue3': {
        'type': 'f',
        'presets': [0, 0.1, 0.5, 1],
        # 'default': 0, 'step': 1, 'precision': 2,
        # 'min': -100, 'soft_min': -100,
        # 'max': 100, 'soft_max': 100,
    },
    '_ZTest2': {
        'type': 'f',
        'disableSlider': True,
        'preset_enums': [(0, '0'), (1, '1')],
        # 'default': 0, 'step': 1, 'precision': 2,
        # 'min': -100, 'soft_min': -100,
        # 'max': 100, 'soft_max': 100,
    },
    '_ZTest2Alpha': {
        'type': 'f',
        'presets': [0, 0.8, 1],
        # 'default': 0, 'step': 1, 'precision': 2,
        # 'min': -100, 'soft_min': -100,
        # 'max': 100, 'soft_max': 100,
    },
    '_HiPow': {
        'type': 'f',
        'desc': "ハイライトの強さを指定。",
        'presets': [0, 25, 50],
    },
    '_HiRate': {
        'type': 'f',
        'desc': "ハイライトの係数を指定。",
        'presets': [0, 0.25, 0.5, 0.75, 1],
    },
}


class DataHandler:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = DataHandler()

        return cls._instance

    def __init__(self):
        diffuse = {
            'type_name': "リアル",
            'icon': 'BRUSH_CLAY_STRIPS',
            'shader2': 'Legacy Shaders__Diffuse',
            'tex_list': ['_MainTex'],
            'col_list': ['_Color'],
            'f_list': [],
        }
        trans_diffuse = {
            'type_name': "リアル 透過",
            'icon': 'SHADING_RENDERED',
            'shader2': 'Legacy Shaders__Transparent__Diffuse',
            'tex_list': ['_MainTex'],
            'col_list': ['_Color'],
            'f_list': [],
        }

        self.shader_dict = {
            'CM3D2/Toony_Lighted': {
                'type_name': "トゥーン",
                'icon': 'SHADING_SOLID',
                'shader2': 'CM3D2__Toony_Lighted',
                'tex_list': ['_MainTex', '_ToonRamp', '_ShadowTex', '_ShadowRateToon'],
                'col_list': ['_Color', '_ShadowColor', '_RimColor'],
                'f_list': ['_Shininess', '_RimPower', '_RimShift']
            },
            'CM3D2/Toony_Lighted_Hair': {
                'type_name': "トゥーン 髪",
                'icon': 'PARTICLEMODE',
                'shader2': 'CM3D2__Toony_Lighted_Hair',
                'tex_list': ['_MainTex', '_ToonRamp', '_ShadowTex', '_ShadowRateToon', '_HiTex'],
                'col_list': ['_Color', '_ShadowColor', '_RimColor'],
                'f_list': ['_Shininess', '_RimPower', '_RimShift', '_HiRate', '_HiPow']
            },
            'CM3D2/Toony_Lighted_Trans': {
                'type_name': "トゥーン 透過",
                'icon': 'SHADING_WIRE',
                'shader2': 'CM3D2__Toony_Lighted_Trans',
                'tex_list': ['_MainTex', '_ToonRamp', '_ShadowTex', '_ShadowRateToon'],
                'col_list': ['_Color', '_ShadowColor', '_RimColor'],
                'f_list': ['_Shininess', '_Cutoff', '_RimPower', '_RimShift'],
            },
            'CM3D2/Toony_Lighted_Trans_NoZ': {
                'type_name': "トゥーン 透過 NoZ",
                'icon': 'DRIVER',
                'shader2': 'CM3D2__Toony_Lighted_Trans_NoZ',
                'tex_list': ['_MainTex', '_ToonRamp', '_ShadowTex', '_ShadowRateToon'],
                'col_list': ['_Color', '_ShadowColor', '_RimColor'],
                'f_list': ['_Shininess', '_RimPower', '_RimShift'],
            },
            'CM3D2/Toony_Lighted_Trans_NoZTest': {
                'type_name': "トゥーン 透過 NoZTest",
                'icon': 'ANIM_DATA',
                'shader2': 'CM3D2__Toony_Lighted_Trans_NoZTest',
                'tex_list': ['_MainTex', '_ToonRamp', '_ShadowTex', '_ShadowRateToon'],
                'col_list': ['_Color', '_ShadowColor', '_RimColor'],
                'f_list': ['_Shininess', '_RimPower', '_RimShift', '_ZTest', '_ZTest2', '_ZTest2Alpha'],
            },
            'CM3D2/Toony_Lighted_Outline': {
                'type_name': "トゥーン 輪郭線",
                'icon': 'ANTIALIASED',
                'shader2': 'CM3D2__Toony_Lighted_Outline',
                'tex_list': ['_MainTex', '_ToonRamp', '_ShadowTex', '_ShadowRateToon'],
                'col_list': ['_Color', '_ShadowColor', '_RimColor', '_OutlineColor'],
                'f_list': ['_Shininess', '_OutlineWidth', '_RimPower', '_RimShift'],
            },
            'CM3D2/Toony_Lighted_Outline_Tex': {
                'type_name': "トゥーン 輪郭線 Tex",
                'icon': 'MATSPHERE',
                'shader2': 'CM3D2__Toony_Lighted_Outline_Tex',
                'tex_list': ['_MainTex', '_ToonRamp', '_ShadowTex', '_ShadowRateToon', '_OutlineTex', '_OutlineToonRamp'],
                'col_list': ['_Color', '_ShadowColor', '_RimColor', '_OutlineColor'],
                'f_list': ['_Shininess', '_OutlineWidth', '_RimPower', '_RimShift'],
            },
            'CM3D2/Toony_Lighted_Hair_Outline': {
                'type_name': "トゥーン 輪郭線 髪",
                'icon': 'PARTICLEMODE',
                'shader2': 'CM3D2__Toony_Lighted_Hair_Outline',
                'tex_list': ['_MainTex', '_ToonRamp', '_ShadowTex', '_ShadowRateToon', '_HiTex'],
                'col_list': ['_Color', '_ShadowColor', '_RimColor', '_OutlineColor'],
                'f_list': ['_Shininess', '_OutlineWidth', '_RimPower', '_RimShift', '_HiRate', '_HiPow'],
            },
            # 'CM3D2/Toony_Lighted_Hair_Outline_Tex': {
            # 	'type_name': "トゥーン 輪郭線 Tex 髪",
            # 	'icon': 'PARTICLEMODE',
            # 	'shader2': 'CM3D2__Toony_Lighted_Hair_Outline_Tex',
            # 	'tex_list': ['_MainTex', '_ToonRamp', '_ShadowTex', '_ShadowRateToon', '_HiTex'],
            # 	'col_list': ['_Color', '_ShadowColor', '_RimColor', '_OutlineColor'],
            # 	'f_list': ['_Shininess', '_OutlineWidth', '_RimPower', '_RimShift', '_HiRate', '_HiPow'],
            # },
            'CM3D2/Toony_Lighted_Outline_Trans': {
                'type_name': "トゥーン 輪郭線 透過",
                'icon': 'PROP_OFF',
                'shader2': 'CM3D2__Toony_Lighted_Outline_Trans',
                'tex_list': ['_MainTex', '_ToonRamp', '_ShadowTex', '_ShadowRateToon'],
                'col_list': ['_Color', '_ShadowColor', '_RimColor', '_OutlineColor'],
                'f_list': ['_Shininess', '_OutlineWidth', '_RimPower', '_RimShift'],
            },
            'CM3D2/Toony_Lighted_Cutout_AtC': {
                'type_name': "トゥーン Cutout",
                'icon': 'IPO_BACK',
                'shader2': 'CM3D2__Toony_Lighted_Cutout_AtC',
                'tex_list': ['_MainTex', '_ToonRamp', '_ShadowTex', '_ShadowRateToon'],
                'col_list': ['_Color', '_ShadowColor', '_RimColor'],
                'f_list': ['_Shininess', '_RimPower', '_RimShift', '_Cutoff'],
            },
            'CM3D2/Lighted_Trans': {
                'type_name': "トゥーン無し 透過",
                'icon': 'VIS_SEL_01',
                'shader2': 'CM3D2__Lighted_Trans',
                'tex_list': ['_MainTex'],
                'col_list': ['_Color', '_ShadowColor'],
                'f_list': ['_Shininess'],
            },
            'CM3D2/Lighted': {
                'type_name': "トゥーン無し",
                'icon': 'VIS_SEL_11',
                'shader2': 'CM3D2__Lighted',
                'tex_list': ['_MainTex'],
                'col_list': ['_Color', '_ShadowColor'],
                'f_list': ['_Shininess'],
            },
            'CM3D2/Lighted_Cutout_AtC': {
                'type_name': "トゥーン無し Cutout",
                'icon': 'IPO_BACK',
                'shader2': 'CM3D2__Lighted_Cutout_AtC',
                'tex_list': ['_MainTex'],
                'col_list': ['_Color', '_ShadowColor'],
                'f_list': ['_Shininess', '_Cutoff'],
            },
            'Unlit/Texture': {
                'type_name': "発光",
                'icon': 'PARTICLES',
                'shader2': 'Unlit__Texture',
                'tex_list': ['_MainTex'],
                'col_list': [],  # ['_Color'],
                'f_list': [],
            },
            'Unlit/Transparent': {
                'type_name': "発光 透過",
                'icon': 'MOD_PARTICLES',
                'shader2': 'Unlit__Texture',
                'tex_list': ['_MainTex'],
                'col_list': [],  # ['_Color'],
                'f_list': [],
            },
            'CM3D2/Mosaic': {
                'type_name': "モザイク",
                'icon': 'ALIASED',
                'shader2': 'CM3D2__Mosaic',
                'tex_list': ['_RenderTex'],
                'col_list': [],
                'f_list': ['_FloatValue1'],
            },
            'CM3D2/Man': {
                'type_name': "ご主人様",
                'icon': 'ARMATURE_DATA',
                'shader2': 'CM3D2__Man',
                'tex_list': [],
                'col_list': ['_Color'],
                'f_list': ['_FloatValue2', '_FloatValue3'],
            },
            'Diffuse': diffuse,
            'Legacy Shaders/Diffuse': diffuse,
            'Transparent/Diffuse': trans_diffuse,
            'Legacy Shaders/Transparent/Diffuse': trans_diffuse,
            'CM3D2_Debug/Debug_CM3D2_Normal2Color': {
                'type_name': "法線",
                'icon': 'NORMALS_VERTEX',
                'shader2': 'CM3D2_Debug__Debug_CM3D2_Normal2Color',
                'tex_list': [],
                'col_list': ['_Color'],  # , '_RimColor', '_OutlineColor', '_SpecColor'],
                'f_list': []  # ['_Shininess', '_OutlineWidth', '_RimPower', '_RimShift'],
            },
        }

    @classmethod
    def create_shader_items(cls) -> list:
        _inst = cls.instance()
        items = []
        idx = 0
        for name in SHADER_NAMES_CM3D2:
            item = _inst.shader_dict.get(name)
            if item:
                items.append((name, item['type_name'], '', item['icon'], idx))
                idx += 1
        return items

    @classmethod
    def create_comshader_items(cls) -> list:
        _inst = cls.instance()
        items = []
        idx = 0
        for name in SHADER_NAMES_COM3D2:
            item = _inst.shader_dict.get(name)
            if item:
                items.append((name, item['type_name'], '', item['icon'], idx))
                idx += 1
        return items

    @classmethod
    def create_shader_all_items(cls) -> list:
        _inst = cls.instance()
        items = []
        idx = 0
        support_both = set(SHADER_NAMES_CM3D2) & set(SHADER_NAMES_COM3D2)

        for name in SHADER_NAMES_COM3D2:
            item = _inst.shader_dict.get(name)
            if item:
                support_desc = '' if name in support_both else " (COM3D2 only)"
                items.append((name, f"{item['type_name']}{support_desc}", '', item['icon'], idx))
                idx += 1
        return items

    @classmethod
    def get_shader_prop(cls, name):
        _inst = cls.instance()
        shader_prop = _inst.shader_dict.get(name)
        if shader_prop:
            return shader_prop

        return {'type_name': "不明", 'icon': 'NONE'}

Handler = DataHandler.instance()


class Material():
    """マテリアルデータクラス"""
    def __init__(self):
        self.version = 1000
        self.name1 = None
        self.name2 = None
        self.shader1 = None
        self.shader2 = None

        self.tex_list = []  # prop_name, (tex_name, tex_path, trans[2], scale[2])
        self.col_list = []  # prop_name, col[4]
        self.f_list = []  # prop_name, f
        self.range_list = [] # prop_name, col[4]

        self.custom_list = dict()

    def sort(self):
        self.tex_list = sorted(self.tex_list, key=lambda item: item[0])
        self.col_list = sorted(self.col_list, key=lambda item: item[0])
        self.f_list = sorted(self.f_list, key=lambda item: item[0])

    @property
    def name(self):
        return self.name2 or self.name1

    @name.setter
    def name(self, new_name: str):
        self.name1 = new_name
        self.name2 = new_name
    
    def read(self, reader, read_header=True):
        if read_header:
            header = common.read_str(reader)
            if header != 'CM3D2_MATERIAL':
                raise common.CM3D2ImportError(f_tip_("mateファイルではありません。ヘッダ:{}", header))
            self.version = struct.unpack('<i', reader.read(4))[0]
            self.name1 = common.read_str(reader)
        self.name2 = common.read_str(reader)

        self.shader1 = common.read_str(reader)
        self.shader2 = common.read_str(reader)
        
        peeked = reader.peek()[0]
        print(f"type({peeked}) = {type(peeked)}")
        if self.version >= 2102 and (peeked in (0, 1)): # CR Edit Mode
            cr_unknown_float_count = struct.unpack('<B', reader.read(1))[0]
            for i in range(cr_unknown_float_count):
                # CR TODO
                self.custom_list[f'cr_unknown_float:{i:03d}'] = struct.unpack('<f', reader.read(4))

        for i in range(99999):
            prop_type = common.read_str(reader)
            if prop_type == 'tex':
                prop_name = common.read_str(reader)
                sub_type = common.read_str(reader)
                if sub_type == 'tex2d':
                    tex_name = common.read_str(reader)
                    tex_path = common.read_str(reader)
                    offset = struct.unpack('<2f', reader.read(4 * 2))
                    scale = struct.unpack('<2f', reader.read(4 * 2))
                    tex_item = [prop_name, tex_name, tex_path, offset, scale]
                else:
                    tex_item = [prop_name]
                self.tex_list.append(tex_item)

            elif prop_type == 'col':
                prop_name = common.read_str(reader)
                col = struct.unpack('<4f', reader.read(4 * 4))
                self.col_list.append([prop_name, col])

            elif prop_type == 'f' or prop_type == 'range': # 'range' from CR Edit
                prop_name = common.read_str(reader)
                f = struct.unpack('<f', reader.read(4))[0]
                self.f_list.append([prop_name, f])
            
            # CR TODO
            elif prop_type == 'keyword':
                prop_name = common.read_str(reader)
                keyword_f = struct.unpack('<f', reader.read(4))[0]
                print(keyword_f, type(keyword_f))
                self.custom_list.setdefault('keyword', dict())[prop_name] = keyword_f #.append([prop_name, keyword_f])
                
            # CR TODO
            elif prop_type == '_ALPHAPREMULTIPLY_ON':
                alpha_bool = struct.unpack('<?', reader.read(1))[0]
                self.custom_list['_ALPHAPREMULTIPLY_ON'] = alpha_bool

            elif prop_type == 'end':
                break
            else:
                raise common.CM3D2ImportError(f_tip_("Materialプロパティに未知の設定値タイプ({prop})が見つかりました。", prop=prop_type))

    def write(self, writer, write_header=True):
        if write_header:
            common.write_str(writer, 'CM3D2_MATERIAL')
            writer.write(struct.pack('<i', self.version))
            common.write_str(writer, self.name1)

        common.write_str(writer, self.name2)
        common.write_str(writer, self.shader1)
        common.write_str(writer, self.shader2)

        for tex_item in self.tex_list:
            common.write_str(writer, 'tex')
            common.write_str(writer, tex_item[0])  # prop_name

            if len(tex_item) < 2:
                common.write_str(writer, 'null')
            else:
                common.write_str(writer, 'tex2d')
                common.write_str(writer, tex_item[1])  # tex_name
                common.write_str(writer, tex_item[2])  # tex_path
                trans = tex_item[3]
                writer.write(struct.pack('<2f', trans[0], trans[1]))
                scale = tex_item[4]
                writer.write(struct.pack('<2f', scale[0], scale[1]))

        for col_item in self.col_list:
            common.write_str(writer, 'col')
            common.write_str(writer, col_item[0])  # prop_name

            col = col_item[1]
            writer.write(struct.pack('<4f', col[0], col[1], col[2], col[3]))

        for f_item in self.f_list:
            common.write_str(writer, 'f')
            common.write_str(writer, f_item[0])  # prop_name

            writer.write(struct.pack('<f', f_item[1]))

        common.write_str(writer, 'end')

    def to_text(self):
        output_text = str(self.version) + '\n'
        output_text += self.name1 + '\n'
        output_text += self.name2 + '\n'
        output_text += self.shader1 + '\n'
        output_text += self.shader2 + '\n'
        output_text += '\n'

        for tex_item in self.tex_list:
            output_text += 'tex\n'
            output_text += '\t' + tex_item[0] + '\n'  # prop_name

            if len(tex_item) < 2:
                output_text += '\tnull\n'
            else:
                output_text += '\ttex2d\n'
                output_text += '\t' + tex_item[1] + '\n'  # tex_name
                output_text += '\t' + tex_item[2] + '\n'  # tex_path
                trans = tex_item[3]
                scale = tex_item[4]
                output_text += '\t' + ' '.join([str(trans[0]), str(trans[1]), str(scale[0]), str(scale[1])]) + '\n'

        for col_item in self.col_list:
            output_text += 'col\n'
            output_text += '\t' + col_item[0] + '\n'  # prop_name
            col = col_item[1]
            output_text += '\t' + ' '.join([str(col[0]), str(col[1]), str(col[2]), str(col[3])]) + '\n'  # prop_name

        for f_item in self.f_list:
            output_text += 'f\n'
            output_text += '\t' + f_item[0] + '\n'  # prop_name
            f = f_item[1]
            output_text += '\t' + str(f) + '\n'

        return output_text

    def to_json(self):
        import json
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)

    def from_dict(self, data):
        self.name1 = data['name1']
        self.name2 = data['name2']
        self.version = data['version']
        self.shader1 = data['shader1']
        self.shader2 = data['shader2']

        self.tex_list = data['tex_list']  # prop_name, (tex_name, tex_path, trans[2], scale[2])
        self.col_list = data['col_list']  # prop_name, col[4]
        self.f_list = data['f_list']  # prop_name, f


class MaterialHandler:

    @classmethod
    def parse_tex_node(cls, node, remove_serial=True):
        node_name = common.remove_serial_number(node.name, remove_serial)
        tex_item = [node_name]

        try:
            img = node.image
        except:
            raise common.CM3D2ImportError('Materialプロパティのtexタイプの設定値取得に失敗しました。')

        if img:
            tex_name = common.remove_serial_number(img.name, remove_serial)
            tex_name = common.re_png.sub(r'\1', tex_name)  # 拡張子を除外
            tex_item.append(tex_name)

            if 'cm3d2_path' in img:
                path = img['cm3d2_path']
            else:
                path = bpy.path.abspath(img.filepath)
            path = common.to_cm3d2path(path)

            tex_item.append(path)
            tex_map = node.texture_mapping
            tex_trans = tex_map.translation[:2]
            tex_scale = tex_map.scale[:2]
            tex_item.append(tex_trans)
            tex_item.append(tex_scale)
        return tex_item

    @classmethod
    def parse_col_node(cls, node, remove_serial=True):
        node_name = common.remove_serial_number(node.name, remove_serial)
        col = node.outputs[0].default_value
        return [node_name, col[:4]]

    @classmethod
    def parse_f_node(cls, node, remove_serial=True):
        node_name = common.remove_serial_number(node.name, remove_serial)
        f = node.outputs[0].default_value
        return [node_name, f]

    @classmethod
    def read(cls, reader, read_header=True, version=None):
        if not read_header and version == None:
            raise ValueError(f_tip_("The argument 'version' is required when 'read_header' is False for MaterialHandler.read()"))
        mat_data = Material()
        if version:
            mat_data.version = version
        mat_data.read(reader, read_header)

        return mat_data

    @classmethod
    def get_shader_prop_dynamic(cls, mate, ):
        lists = { 'VALUE':'f_list', 'RGB':'col_list', 'TEX_IMAGE':'tex_list' }
        shader_prop = copy.deepcopy( DataHandler.get_shader_prop(mate.get('shader1')) )
        for node in mate.node_tree.nodes:
            if node.name[0] != '_':
                continue
            list_name = lists.get(node.type)
            if not list_name:
                continue
            prop_list = shader_prop.get(list_name)
            if not prop_list:
                prop_list = list()
                shader_prop[list_name] = prop_list
            if node.name in prop_list:
                continue
            prop_list.append(node.name)
        return shader_prop

    @classmethod
    def parse_mate(cls, mate, remove_serial=True):
        mat_data = Material()

        mate_name = common.remove_serial_number(mate.name, remove_serial)
        mat_data.name1 = mate_name.lower()
        mat_data.name2 = mate_name
        mat_data.shader1 = mate['shader1']
        mat_data.shader2 = mate['shader2']

        nodes = mate.node_tree.nodes
        shader_prop = cls.get_shader_prop_dynamic(mate) #DataHandler.get_shader_prop(mat_data.shader1)
        if shader_prop:
            for node_name in shader_prop['tex_list']:
                node = nodes.get(node_name)
                if node and node.type == 'TEX_IMAGE':
                    tex_item = cls.parse_tex_node(node, remove_serial)
                    mat_data.tex_list.append(tex_item)

            for node_name in shader_prop['col_list']:
                node = nodes.get(node_name)
                if node and node.type == 'RGB':
                    col_item = cls.parse_col_node(node, remove_serial)
                    mat_data.col_list.append(col_item)

            for node_name in shader_prop['f_list']:
                node = nodes.get(node_name)
                if node and node.type == 'VALUE':
                    f_item = cls.parse_f_node(node, remove_serial)
                    mat_data.f_list.append(f_item)

        #for node in nodes:
        #    if not node.name.startswith('_'):
        #        continue
        #
        #    node_type = node.type
        #    if node_type == 'TEX_IMAGE':
        #        tex_item = cls.parse_tex_node(node, remove_serial)
        #        mat_data.tex_list.append(tex_item)
        #    elif node_type == 'RGB':
        #        col_item = cls.parse_col_node(node, remove_serial)
        #        mat_data.col_list.append(col_item)
        #
        #    elif node_type == 'VALUE':
        #        f_item = cls.parse_f_node(node, remove_serial)
        #        mat_data.f_list.append(f_item)
        
        return mat_data

    @classmethod
    def parse_text(cls, text):
        mat_data = Material()
        lines = text.split('\n')

        mat_data.version = int(lines[0])
        mat_data.name1 = lines[1]
        mat_data.name2 = lines[2]
        mat_data.shader1 = lines[3]
        mat_data.shader2 = lines[4]

        line_seek = 5
        while line_seek < len(lines):
            node_type = common.line_trim(lines[line_seek])
            if not node_type:
                line_seek += 1
                continue
            if node_type == 'tex':
                prop_name = common.line_trim(lines[line_seek + 1])
                sub_type = common.line_trim(lines[line_seek + 2])
                if sub_type == 'tex2d':
                    line_seek += 3
                    tex_name = common.line_trim(lines[line_seek])
                    tex_path = common.line_trim(lines[line_seek + 1])
                    tex_map = common.line_trim(lines[line_seek + 2]).split(' ')
                    for map_datum in range(len(tex_map)):
                        tex_map[map_datum] = float(tex_map[map_datum])
                    mat_data.tex_list.append([prop_name, tex_name, tex_path, tex_map[:2], tex_map[2:]])
                else:
                    mat_data.tex_list.append([prop_name])

                line_seek += 3

            elif node_type == 'col':
                prop_name = common.line_trim(lines[line_seek + 1])
                tex_map = common.line_trim(lines[line_seek + 2]).split(' ')
                for map_datum in range(len(tex_map)):
                    tex_map[map_datum] = float(tex_map[map_datum])

                mat_data.col_list.append([prop_name, tex_map[:]])
                line_seek += 3

            elif node_type == 'f':
                prop_name = common.line_trim(lines[line_seek + 1])
                val = float(common.line_trim(lines[line_seek + 2]))

                mat_data.f_list.append([prop_name, val])
                line_seek += 3
            else:
                raise Exception('未知の設定値タイプが見つかりました。')

        return mat_data

    @classmethod
    def parse_json(cls, text):
        import json
        mat_data = Material()
        mat_data.from_dict(json.loads(text))

        return mat_data

    @classmethod
    def apply_to(cls, override, mate, mat_data, replace_tex=True):
        mate['shader1'] = mat_data.shader1
        mate['shader2'] = mat_data.shader2

        if mate.use_nodes is False:
            mate.use_nodes = True

        nodes = mate.node_tree.nodes
        nodes.clear()
        # OUTPUT_MATERIAL, BSDF_PRINCIPLEDは消さない
        #if len(nodes) > 2:
        #    clear_nodes(nodes)

        for tex_item in mat_data.tex_list:
            prop_name = tex_item[0]

            if len(tex_item) < 2:
                common.create_tex(override, mate, prop_name)
            else:
                tex_name = tex_item[1]
                tex_path = tex_item[2]
                tex_map = tex_item[3] + tex_item[4]
                common.create_tex(override, mate, prop_name, tex_name, tex_path, tex_path, tex_map, replace_tex)

        for col_item in mat_data.col_list:
            prop_name = col_item[0]
            col = col_item[1]
            common.create_col(override, mate, prop_name, col)

        for item in mat_data.f_list:
            prop_name = item[0]
            f = item[1]
            common.create_float(override, mate, prop_name, f)

        for key, value in mat_data.custom_list.items():
            mate[key] = value
            if type(value) == bool:
                rna_ui = mate.get('_RNA_UI', dict())
                rna_ui[key] = {
                    'default'  : value,
                    'min'      : 0    ,
                    'max'      : 1    ,
                    'soft_min' : 0    ,
                    'soft_max' : 1    ,
                }
                mate['_RNA_UI'] = rna_ui



        align_nodes(mate)

    @staticmethod
    def search_or_create_slot(override, mate, olds_slots, slot_index, prop_name, tex_type):
        tex = None
        slot_item = mate.texture_slots[slot_index]
        slot_name = slot_item.name if slot_item else ''

        slot_name = common.remove_serial_number(slot_name)
        # 指定スロットが同名であればそのスロットをそのまま利用する
        if prop_name == slot_name:
            slot = slot_item
        else:
            # スロット名が異なり、既にスロットがある場合はキャッシュに格納
            if slot_item:
                olds_slots[slot_name] = slot_item
            slot = mate.texture_slots.create(slot_index)

            if prop_name in olds_slots:
                tex = olds_slots.pop(prop_name).texture
            else:
                for item_index in range(slot_index + 1, len(mate.texture_slots)):
                    slot_item = mate.texture_slots[item_index]
                    if slot_item is None:
                        break
                    if prop_name == common.remove_serial_number(slot_item.name):
                        tex = slot_item.texture
                        break
            if tex is None:
                tex = override['blend_data'].textures.new(prop_name, tex_type)
            slot.texture = tex
        return slot


def clear_nodes(nodes):
    for node in nodes:
        if node.type not in ['VALUE', 'RGB', 'TEX_IMAGE']:
            nodes.remove(node)


def align_nodes(mate):
    nodes = mate.node_tree.nodes
    # Principled BSDFがある前提での整列
    bsdf = nodes.get('Principled BSDF')
    base_location = (10, 300)
    if bsdf:
        main_tex = nodes.get('_MainTex')
        if main_tex:
            mate.node_tree.links.new(bsdf.inputs['Base Color'], main_tex.outputs['Color'])
            mate.node_tree.links.new(bsdf.inputs['Alpha'], main_tex.outputs['Alpha'])
        shininess = nodes.get('_Shininess')
        if shininess:
            mate.node_tree.links.new(bsdf.inputs['Specular'], shininess.outputs[0])
        base_location = bsdf.location

    shader_name = mate.get('shader1')
    if shader_name:
        location_x = base_location[0] - 400
        location_y = base_location[1] + 60
        shader_prop = MaterialHandler.get_shader_prop_dynamic(mate) #DataHandler.get_shader_prop(shader_name)
        node_list = shader_prop.get('tex_list')
        if node_list:
            for node_name in node_list:
                node = nodes.get(node_name)
                if node:
                    node.location = (location_x, location_y)
                    node.hide = True
                    location_y -= 40

        col_list = shader_prop.get('col_list')
        if col_list:
            for node_name in col_list:
                node = nodes.get(node_name)
                if node:
                    node.location = (location_x, location_y)
                    node.hide = True
                    location_y -= 40

        f_list = shader_prop.get('f_list')
        if f_list:
            for node_name in f_list:
                node = nodes.get(node_name)
                if node:
                    node.location = (location_x, location_y)
                    node.hide = True
                    location_y -= 40


class ArcHandler:
    ARC_MAGIC = b'\x77\x61\x72\x63\xFF\xAA\x45\xF1\xE8\x03\x00\x00\x04\x00\x00\x00\x02\x00\x00\x00'

    @classmethod
    def decompress_data(cls, data: bytes, raw_size: int) -> bytes:
        import zlib
        try:
            return zlib.decompress(data)
        except zlib.error:
            return zlib.decompress(data, -zlib.MAX_WBITS)

    @classmethod
    def parse_arc_file(cls, arc_path: str) -> list:
        files_found = []
        with open(arc_path, 'rb') as f:
            magic = f.read(20)
            if magic != cls.ARC_MAGIC:
                # print(f"エラー: 有効なARCファイルではありません。({arc_path}) magic={magic}")
                return []

            footer_offset = struct.unpack('<q', f.read(8))[0]
            base_offset = f.tell()
            f.seek(base_offset + footer_offset)

            utf16_hash_data = None
            name_data = None

            while utf16_hash_data is None or name_data is None:
                block_type = struct.unpack('<i', f.read(4))[0]
                block_size = struct.unpack('<q', f.read(8))[0]

                if block_type == 0:
                    utf16_hash_data = f.read(block_size)
                elif block_type == 1:
                    f.seek(block_size, os.SEEK_CUR)
                elif block_type == 3:
                    is_compressed = struct.unpack('<I', f.read(4))[0] == 1
                    f.read(4)
                    raw_size = struct.unpack('<I', f.read(4))[0]
                    compressed_size = struct.unpack('<I', f.read(4))[0]

                    raw_block_bytes = f.read(compressed_size)
                    if is_compressed:
                        name_data = cls.decompress_data(raw_block_bytes, raw_size)
                    else:
                        name_data = raw_block_bytes
                else:
                    break

            name_lut = {}
            ordered_names = []
            if name_data:
                n_offset = 0
                while n_offset < len(name_data):
                    if n_offset + 12 > len(name_data):
                        break
                    h_val = struct.unpack('<Q', name_data[n_offset:n_offset + 8])[0]
                    str_len = struct.unpack('<i', name_data[n_offset + 8:n_offset + 12])[0]
                    n_offset += 12

                    if str_len < 0 or n_offset + (str_len * 2) > len(name_data):
                        break

                    name_bytes = name_data[n_offset: n_offset + (str_len * 2)]
                    n_offset += str_len * 2
                    # errors='ignore' にして、壊れたサロゲートペアだけを排除しつつ復元
                    cleaned_name = name_bytes.decode('utf-16-le', errors='ignore').strip('\0')

                    name_lut[h_val] = cleaned_name
                    ordered_names.append(cleaned_name)

            def parse_hash_table(stream_bytes, offset_ref):
                if offset_ref[0] >= len(stream_bytes): return
                offset_ref[0] += 8
                struct.unpack('<Q', stream_bytes[offset_ref[0]:offset_ref[0] + 8])[0]
                dir_count, file_count, depth, __ = struct.unpack('<IIII',
                                                                stream_bytes[offset_ref[0] + 8:offset_ref[0] + 24])
                offset_ref[0] += 24

                dirs_info = []
                for __ in range(dir_count):
                    d_hash, d_offset = struct.unpack('<QQ', stream_bytes[offset_ref[0]:offset_ref[0] + 16])
                    dirs_info.append((d_hash, d_offset))
                    offset_ref[0] += 16

                for __ in range(file_count):
                    f_hash, f_offset = struct.unpack('<QQ', stream_bytes[offset_ref[0]:offset_ref[0] + 16])
                    f_name = name_lut.get(f_hash, None)
                    files_found.append({
                        'name': f_name,
                        'offset': f_offset + base_offset
                    })
                    offset_ref[0] += 16

                offset_ref[0] += 8 * depth
                for __ in dirs_info:
                    parse_hash_table(stream_bytes, offset_ref)

            if utf16_hash_data:
                parse_hash_table(utf16_hash_data, [0])

        return files_found

    @classmethod
    def extract(cls, arc_file_pattern: str, output_dir: str, target_files: list[str] | str, force: bool = False):
        arc_path = common.default_cm3d2_dir('', '', '.arc')
        file_pattern = re.compile(rf'.*\\{arc_file_pattern}')
        target_pattern = re.compile(target_files) if isinstance(target_files, str) else None
        arc_paths = [x for x in glob.glob(arc_path) if file_pattern.match(x)]
        for arc_path in arc_paths:

            # print(f"ARCファイルのパース中: {arc_path}")
            file_entries = cls.parse_arc_file(arc_path)
            if not file_entries:
                continue

            # print(f"合計 {len(file_entries)} 個のファイルが見つかりました。")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            for entry in file_entries:
                filename = entry['name']
                if target_pattern:
                    if not target_pattern.match(filename):
                        continue
                elif filename not in target_files:
                    continue

                out_path = os.path.join(output_dir, filename)
                ext = os.path.splitext(out_path)[1]
                if ext in ['.nei', '.ks']:
                    out_path += '.pkl'
                elif ext == '.tex':
                    out_path = os.path.splitext(out_path)[0] + '.png'
                if not force and os.path.exists(out_path):
                    #                print(f"スキップ: {filename}")
                    continue
                print(f"抽出中: {filename}")

                with open(arc_path, 'rb') as f:
                    f.seek(entry['offset'])
                    is_compressed = struct.unpack('<I', f.read(4))[0] == 1
                    f.read(4)
                    raw_size = struct.unpack('<I', f.read(4))[0]
                    compressed_size = struct.unpack('<I', f.read(4))[0]

                    file_bytes = f.read(compressed_size)
                    if is_compressed:
                        file_bytes = cls.decompress_data(file_bytes, raw_size)

                if filename.endswith('.nei'):
                    decrypted_nei = NeiHandler.decrypt_nei(file_bytes)
                    data = NeiHandler.nei_to_list(decrypted_nei)
                    with open(out_path, mode='wb') as f:
                        pickle.dump(data, f)
                elif filename.endswith('.ks'):
                    ks = file_bytes.decode('cp932', errors='replace')
                    data = KsHandler.ks_to_dict_list(ks)
                    with open(out_path, mode='wb') as f:
                        pickle.dump(data, f)
                elif filename.endswith('.tex'):
                    out_path2 = os.path.splitext(out_path)[0] + '.tex'
                    with open(out_path2, mode='wb') as f:
                        f.write(file_bytes)
                    tex_data = common.load_cm3d2tex(out_path2)
                    with open(out_path, 'wb') as f:
                        f.write(tex_data[-1])
                else:
                    with open(out_path, mode='wb') as f:
                        f.write(file_bytes)

        #            print('done: ', filename)

        print('extracted: ', arc_file_pattern)


class KsHandler:
    def ks_to_dict_list(script: str) -> dict:
        arg_pattern = re.compile(r'(?:[^\s"]+|"[^"]*")+')
        parsed_data = {}
        current_section = None

        for line_num, line in enumerate(script.split('\n')):
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            if line.startswith('*'):
                section_name = line.strip()
                current_section = section_name
                parsed_data[current_section] = {}
            elif line.startswith('@'):
                cmd_core = line.strip()
                if not cmd_core:
                    continue
                tokens = arg_pattern.findall(cmd_core)
                if not tokens:
                    continue
                cmd_name = tokens[0]
                cmd_args = {}
                for token in tokens[1:]:
                    if '=' in token and token[0] != '"':
                        key, value = token.split('=')
                        cmd_args[key] = value
                    else:
                        cmd_args[token] = None
                if current_section not in parsed_data:
                    parsed_data[current_section] = {}
                if cmd_name not in parsed_data[current_section]:
                    parsed_data[current_section][cmd_name] = []
                parsed_data[current_section][cmd_name].append(cmd_args)

        return parsed_data


class NeiHandler:
    NEI_KEY = bytes([
        0xAA, 0xC9, 0xD2, 0x35, 0x22, 0x87, 0x20, 0xF2,
        0x40, 0xC5, 0x61, 0x7C, 0x01, 0xDF, 0x66, 0x54
    ])
    NEI_MAGIC = b'\x77\x73\x76\xFF'

    @classmethod
    def decrypt_nei(cls, encrypted_bytes: bytes) -> bytes:
        if len(encrypted_bytes) < 5: return b""
        extra_data_size = encrypted_bytes[-5] ^ encrypted_bytes[-4]
        iv_seed = encrypted_bytes[-4:]
        iv = cls._generate_iv(iv_seed)

        # ここで Pure Python の AES デコーダを使用
        cipher = AES128CBC(cls.NEI_KEY, iv)
        decrypted_padded = cipher.decrypt(encrypted_bytes[:-5])

        actual_size = len(encrypted_bytes) - extra_data_size - 5
        return decrypted_padded[:actual_size]

    @classmethod
    def nei_to_list(cls, nei_data: bytes) -> list:
        if len(nei_data) < 12 or nei_data[0:4] != cls.NEI_MAGIC:
            return []
        cols, rows = struct.unpack('<II', nei_data[4:12])
        offset = 12
        str_lengths = []
        for __ in range(cols * rows):
            offset += 4
            str_len = struct.unpack('<I', nei_data[offset:offset + 4])[0]
            str_lengths.append(str_len)
            offset += 4

        matrix = []
        length_idx = 0
        for r in range(rows):
            current_row = []
            for c in range(cols):
                length = str_lengths[length_idx]
                length_idx += 1
                cell_bytes = nei_data[offset: offset + length]
                offset += length
                try:
                    cell_val = cell_bytes.decode('cp932').strip('\0')
                except UnicodeDecodeError:
                    cell_val = cell_bytes.decode('cp932', errors='replace').strip('\0')
                current_row.append(cell_val)
            matrix.append(current_row)
        return matrix

    @classmethod
    def _generate_iv(cls, iv_seed: bytes) -> bytes:
        seed_last = struct.unpack('<I', iv_seed)[0] ^ 0xBFBFBFBF
        seed = [0x075BCD15, 0x159A55E5, 0x1F123BB5, cls._to_u32(seed_last)]
        for __ in range(4):
            n = cls._to_u32(seed[0] ^ cls._to_u32(seed[0] << 11))
            seed[0] = seed[1]
            seed[1] = seed[2]
            seed[2] = seed[3]
            part1 = cls._to_u32(seed[3] >> 11)
            part2 = cls._to_u32(cls._to_u32(n ^ part1) >> 8)
            seed[3] = cls._to_u32(n ^ seed[3] ^ part2)
        return struct.pack('<IIII', seed[0], seed[1], seed[2], seed[3])

    @staticmethod
    def _to_u32(val: int) -> int:
        return val & 0xFFFFFFFF


class AES128CBC:
    SBOX = (
        0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
        0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
        0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
        0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
        0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
        0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
        0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
        0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
        0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
        0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
        0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
        0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
        0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
        0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
        0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
        0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16
    )
    INV_SBOX = (
        0x52, 0x09, 0x6A, 0xD5, 0x30, 0x36, 0xA5, 0x38, 0xBF, 0x40, 0xA3, 0x9E, 0x81, 0xF3, 0xD7, 0xFB,
        0x7C, 0xE3, 0x39, 0x82, 0x9B, 0x2F, 0xFF, 0x87, 0x34, 0x8E, 0x43, 0x44, 0xC4, 0xDE, 0xE9, 0xCB,
        0x54, 0x7B, 0x94, 0x32, 0xA6, 0xC2, 0x23, 0x3D, 0xEE, 0x4C, 0x95, 0x0B, 0x42, 0xFA, 0xC3, 0x4E,
        0x08, 0x2E, 0xA1, 0x66, 0x28, 0xD9, 0x24, 0xB2, 0x76, 0x5B, 0xA2, 0x49, 0x6D, 0x8B, 0xD1, 0x25,
        0x72, 0xF8, 0xF6, 0x64, 0x86, 0x68, 0x98, 0x16, 0xD4, 0xA4, 0x5C, 0xCC, 0x5D, 0x65, 0xB6, 0x92,
        0x6C, 0x70, 0x48, 0x50, 0xFD, 0xED, 0xB9, 0xDA, 0x5E, 0x15, 0x46, 0x57, 0xA7, 0x8D, 0x9D, 0x84,
        0x90, 0xD8, 0xAB, 0x00, 0x8C, 0xBC, 0xD3, 0x0A, 0xF7, 0xE4, 0x58, 0x05, 0xB8, 0xB3, 0x45, 0x06,
        0xD0, 0x2C, 0x1E, 0x8F, 0xCA, 0x3F, 0x0F, 0x02, 0xC1, 0xAF, 0xBD, 0x03, 0x01, 0x13, 0x8A, 0x6B,
        0x3A, 0x91, 0x11, 0x41, 0x4F, 0x67, 0xDC, 0xEA, 0x97, 0xF2, 0xCF, 0xCE, 0xF0, 0xB4, 0xE6, 0x73,
        0x96, 0xAC, 0x74, 0x22, 0xE7, 0xAD, 0x35, 0x85, 0xE2, 0xF9, 0x37, 0xE8, 0x1C, 0x75, 0xDF, 0x6E,
        0x47, 0xF1, 0x1A, 0x71, 0x1D, 0x29, 0xC5, 0x89, 0x6F, 0xB7, 0x62, 0x0E, 0xAA, 0x18, 0xBE, 0x1B,
        0xFC, 0x56, 0x3E, 0x4B, 0xC6, 0xD2, 0x79, 0x20, 0x9A, 0xDB, 0xC0, 0xFE, 0x78, 0xCD, 0x5A, 0xF4,
        0x1F, 0xDD, 0xA8, 0x33, 0x88, 0x07, 0xC7, 0x31, 0xB1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xEC, 0x5F,
        0x60, 0x51, 0x7F, 0xA9, 0x19, 0xB5, 0x4A, 0x0D, 0x2D, 0xE5, 0x7A, 0x9F, 0x93, 0xC9, 0x9C, 0xEF,
        0xA0, 0xE0, 0x3B, 0x4D, 0xAE, 0x2A, 0xF5, 0xB0, 0xC8, 0xEB, 0xBB, 0x3C, 0x83, 0x53, 0x99, 0x61,
        0x17, 0x2B, 0x04, 0x7E, 0xBA, 0x77, 0xD6, 0x26, 0xE1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0C, 0x7D
    )
    RCON = (0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)

    def __init__(self, key: bytes, iv: bytes):
        self.key = list(key)
        self.iv = list(iv)
        self.round_keys = self._expand_key(self.key)

    def _expand_key(self, key):
        rk = list(key)
        for i in range(4, 4 * 11):
            temp = rk[(i - 1) * 4: i * 4]
            if i % 4 == 0:
                temp = [self.SBOX[temp[1]], self.SBOX[temp[2]], self.SBOX[temp[3]], self.SBOX[temp[0]]]
                temp[0] ^= self.RCON[i // 4]
            for j in range(4):
                rk.append(rk[(i - 4) * 4 + j] ^ temp[j])
        return rk

    def _inv_mix_columns(self, state):
        for i in range(4):
            c = state[i * 4: i * 4 + 4]
            state[i * 4 + 0] = self._gmul(0x0e, c[0]) ^ self._gmul(0x0b, c[1]) ^ self._gmul(0x0d, c[2]) ^ self._gmul(0x09, c[3])
            state[i * 4 + 1] = self._gmul(0x09, c[0]) ^ self._gmul(0x0e, c[1]) ^ self._gmul(0x0b, c[2]) ^ self._gmul(0x0d, c[3])
            state[i * 4 + 2] = self._gmul(0x0d, c[0]) ^ self._gmul(0x09, c[1]) ^ self._gmul(0x0e, c[2]) ^ self._gmul(0x0b, c[3])
            state[i * 4 + 3] = self._gmul(0x0b, c[0]) ^ self._gmul(0x0d, c[1]) ^ self._gmul(0x09, c[2]) ^ self._gmul(0x0e, c[3])

    @staticmethod
    def _gmul(a, b):
        p = 0
        for __ in range(8):
            if b & 1: p ^= a
            hi_bit_set = a & 0x80
            a = (a << 1) & 0xFF
            if hi_bit_set: a ^= 0x1B
            b >>= 1
        return p

    def _decrypt_block(self, block):
        state = list(block)

        # AddRoundKey (Round 10)
        for i in range(16): state[i] ^= self.round_keys[160 + i]

        for round_idx in range(9, 0, -1):
            # InvShiftRows
            state[1], state[5], state[9], state[13] = state[13], state[1], state[5], state[9]
            state[2], state[6], state[10], state[14] = state[10], state[14], state[2], state[6]
            state[3], state[7], state[11], state[15] = state[7], state[11], state[15], state[3]
            # InvSubBytes
            for i in range(16): state[i] = self.INV_SBOX[state[i]]
            # AddRoundKey
            for i in range(16): state[i] ^= self.round_keys[round_idx * 16 + i]
            # InvMixColumns
            self._inv_mix_columns(state)

        # Round 0
        state[1], state[5], state[9], state[13] = state[13], state[1], state[5], state[9]
        state[2], state[6], state[10], state[14] = state[10], state[14], state[2], state[6]
        state[3], state[7], state[11], state[15] = state[7], state[11], state[15], state[3]
        for i in range(16): state[i] = self.INV_SBOX[state[i]]
        for i in range(16): state[i] ^= self.round_keys[i]

        return state

    def decrypt(self, data: bytes) -> bytes:
        decrypted = bytearray()
        prev_block = self.iv

        for i in range(0, len(data), 16):
            block = data[i:i + 16]
            if len(block) < 16: break
            dec_block = self._decrypt_block(block)
            for j in range(16):
                decrypted.append(dec_block[j] ^ prev_block[j])
            prev_block = list(block)

        return bytes(decrypted)
