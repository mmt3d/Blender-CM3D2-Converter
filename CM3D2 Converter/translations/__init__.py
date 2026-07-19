import bpy
from .locales import translation_dict
from .pgettext_functions import _, iface_, tip_, data_, f_, f_iface_, f_tip_, f_data_

__all__ = [
    '_', 'iface_', 'tip_', 'data_', 'f_', 'f_iface_', 'f_tip_', 'f_data_'
]

LEGACY_FALLBACK_LANG_MAP = {
    'zh_CN': 'zh_HANS',
    'zh_TW': 'zh_HANT',
}


def register(__name__=__name__):
    # Blenderバージョンによりサポート言語タグが異なることがあり、その場合は代替言語タグに差し替える
    # 翻訳辞書がなければ英語表記とする
    for lang in bpy.app.translations.locales:
        if lang not in translation_dict:
            fallback_lang = LEGACY_FALLBACK_LANG_MAP.get(lang, 'en_US')
            translation_dict[lang] = translation_dict[fallback_lang]

    bpy.app.translations.register(__name__, translation_dict)

def unregister(__name__=__name__):
    bpy.app.translations.unregister(__name__)
