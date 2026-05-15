import os
import sys
import csv
import bpy

# get_true_locale() -> Returns the locale
# get_locale()      -> Returns the closest locale available for translation 

DICT = dict() # The translations dictionary
# {locale: {msg_key: msg_translation, ...}, ...}                                                                                                                                                      
# locale is either a lang iso code (fr), a lang+country code (pt_BR), a lang+variant code (sr@latin), or a full code (uz_UZ@cyrilic).                                                                 
# msg_key is a tupple of (context, org_message)

# max level of verbose messages to print. -1 = Nothing.
verbosity = 0

is_check_duplicates = False

handled_locales   = set()
translations_folder = os.path.dirname(__file__)
comments_dict = dict()

csv.register_dialect('cm3d2_converter',
    delimiter        = ','            ,
    doublequote      = False          ,
    escapechar       = '\\'           ,
    lineterminator   = '\n'           ,
    quotechar        = '"'            ,
    quoting          = csv.QUOTE_ALL  ,
    skipinitialspace = False          ,
    strict           = True         
)

fallback_lang_map = {
    'zh_CN': 'zh_HANS',
    'zh_TW': 'zh_HANT',
}


i18n_contexts = { identifer: getattr(bpy.app.translations.contexts, identifer) for identifer in bpy.app.translations.contexts_C_to_py.values() }
'''
i18n_contexts = {
    default_real        = None                ,
    default             = '*'                 ,
    operator_default    = 'Operator'          ,
    ui_events_keymaps   = 'UI_Events_KeyMaps' ,
    plural              = 'Plural'            ,
    id_action           = 'Action'            ,
    id_armature         = 'Armature'          ,
    id_brush            = 'Brush'             ,
    id_camera           = 'Camera'            ,
    id_cachefile        = 'CacheFile'         ,
    id_collection       = 'Collection'        ,
    id_curve            = 'Curve'             ,
    id_fs_linestyle     = 'FreestyleLineStyle',
    id_gpencil          = 'GPencil'           ,
    id_hair             = 'Hair'              ,
    id_id               = 'ID'                ,
    id_image            = 'Image'             ,
    id_shapekey         = 'Key'               ,
    id_light            = 'Light'             ,
    id_library          = 'Library'           ,
    id_lattice          = 'Lattice'           ,
    id_mask             = 'Mask'              ,
    id_material         = 'Material'          ,
    id_metaball         = 'Metaball'          ,
    id_mesh             = 'Mesh'              ,
    id_movieclip        = 'MovieClip'         ,
    id_nodetree         = 'NodeTree'          ,
    id_object           = 'Object'            ,
    id_paintcurve       = 'PaintCurve'        ,
    id_palette          = 'Palette'           ,
    id_particlesettings = 'ParticleSettings'  ,
    id_pointcloud       = 'PointCloud'        ,
    id_lightprobe       = 'LightProbe'        ,
    id_scene            = 'Scene'             ,
    id_screen           = 'Screen'            ,
    id_sequence         = 'Sequence'          ,
    id_simulation       = 'Simulation'        ,
    id_speaker          = 'Speaker'           ,
    id_sound            = 'Sound'             ,
    id_texture          = 'Texture'           ,
    id_text             = 'Text'              ,
    id_vfont            = 'VFont'             ,
    id_volume           = 'Volume'            ,
    id_world            = 'World'             ,
    id_workspace        = 'WorkSpace'         ,
    id_windowmanager    = 'WindowManager'
}
'''

def print_verbose(level:int, *args, tab:str="\t", sep:str=" ", end:str="\n", file=sys.stdout, flush:bool=False, **format_args) -> None:
    if level > verbosity:
        return
    message = tab * level + sep.join(str(arg) for arg in args)
    if format_args:
        message = message.format(**format_args)
    return print(message, end=end, file=file, flush=flush)


def check_duplicate(key: tuple, lang: str) -> bool:
    if not is_check_duplicates:
        return False
    if key in DICT[lang].keys():
        return True
    else:
        return False


def get_best_locale_match(locale: str) -> str:
    global handled_locales
    available = handled_locales
    # First check for exact locale tag match
    if locale in available:
        return locale
    
    # Otherwise match based on language, country, or variant.
    match = 'en_US' # default is English as per Blender Dev's recomendations
    affinity = 0
    for locale_tag in DICT.keys():
        language, country, variant, language_country, language_variant = bpy.app.translations.locale_explode(locale_tag)
        
        if   affinity < 4 and language_variant in available:
            affinity  = 4
            match     = locale_tag
        elif affinity < 3 and language_country in available:
            affinity  = 3
            match     = locale_tag
        elif affinity < 2 and language in available:
            affinity  = 2
            match     = locale_tag
        elif affinity < 1 and country in available:
            affinity  = 1
            match     = locale_tag
        # Not worth checking variant alone
        #elif affinity < 0 and variant          in available: 
        #    match    = locale_tag
        #    affinity = 0
    
    return match


def generate_translations(locale: str):
    if False:
        # Handle any special generations here
        # e.g. Using Spanish for Portuguese because they are similar
        #      even though they won't be detected by get_best_locale_match()
        pass
    else:
        # If not specially handled, fill it with best match
        match = get_best_locale_match(locale)
        DICT[locale] = DICT[match]


def get_locale() -> str:
    return get_best_locale_match(bpy.app.translations.locale)


def register(__name__=__name__):
    global DICT
    global comments_dict
    global handled_locales

    # Generate locales from csv files
    for lang in os.listdir(translations_folder):
        lang_folder = os.path.join(translations_folder, lang)
        if not os.path.isdir(lang_folder):
            continue
        if lang.startswith("_") or lang.startswith("."):
            continue

        print_verbose(0, "Loading translations for", lang)
        lang_dict = DICT.get(lang)
        if not lang_dict:
            lang_dict = dict()
            DICT[lang] = lang_dict
            comments_dict[lang] = dict()
        
        orig_count = len(lang_dict)
        for csv_file_name in os.listdir(lang_folder):
            _, ext = os.path.splitext(csv_file_name)
            if ext.lower() != ".csv":
                continue
            
            print_verbose(1, f"Reading {csv_file_name}")
            entry_count = 0
            dupe_count  = 0
            csv_file_path = os.path.join(lang_folder, csv_file_name)
            with open(csv_file_path, 'rt', encoding='utf-8', newline='') as csv_file:
                csv_reader = csv.reader(csv_file, dialect='cm3d2_converter')
                try:
                    for line, row in enumerate(csv_reader):
                        if line == 0: # ignore header
                            continue
                        if len(row) < 3:
                            continue
                        if row[0].startswith("#"):
                            # ignore comments
                            continue
                        if row[0] not in i18n_contexts.values():
                            print_verbose(2, f"Unknown translation context \"{row[0]}\" on line {line}")

                        key = (row[0], row[1])
                        if check_duplicate(key, lang):
                            print_verbose(2, f"Duplicate entry on line {line}")
                            entry_count -= 1
                            dupe_count  += 1

                        value = row[2]
                        lang_dict[key] = value
                        entry_count += 1

                        if len(row) > 3: # entry comment
                            comments_dict[lang][key] = row[3]

                        print_verbose(3, f"{line:{4}} {key}: {value}")
                except Exception as e:
                    print(f"Error parsing {csv_file_name} in {lang_folder}:")
                    print(e)

            print_verbose(1, f"-> Added {entry_count} translations from {csv_file_name}")
            if is_check_duplicates:
                print_verbose(1, f"-> Replaced {dupe_count} translations with {csv_file_name}")
        print_verbose(0, f"-> Added {len(lang_dict) - orig_count} translations for {lang}")


    # Any special translations that use another as a base should handle that here
    
    # End special translations

    # Blenderバージョンによりサポート言語タグが異なることがあり、その場合は代替言語タグに差し替える
    missing_lang = set(DICT.keys()) - set(bpy.app.translations.locales)
    for lang in missing_lang:
        fallback_lang = fallback_lang_map.get(lang)
        if fallback_lang:
            DICT[fallback_lang] = DICT[lang]

    handled_locales = { lang for lang in DICT.keys() }


    # Fill missing translations
    print_verbose(0, f"Generating missing translations...")
    gen_count = 0
    for lang in bpy.app.translations.locales:
        if lang not in DICT.keys():
            print_verbose(1, f"Generating translations for '{lang}'")
            generate_translations(lang)
            gen_count += 1
    # For when system.language == 'DEFAULT'
    true_locale = bpy.app.translations.locale
    if true_locale not in DICT.keys():
        print_verbose(1, f"Generating translations for '{true_locale}'")
        generate_translations(true_locale)
        gen_count += 1
    print_verbose(0, f"-> Generated {gen_count} missing translations")

    bpy.app.translations.register(__name__, DICT)

def unregister(__name__=__name__):
    bpy.app.translations.unregister(__name__)


if __name__ == "__main__":
    register()