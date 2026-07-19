import ast
import datetime
import gettext
import json
import logging
import os
import re
import textwrap
from typing import TypeGuard
import typer
from rich.logging import RichHandler
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn

app = typer.Typer()
logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler(markup=True)])

# Rule: Latest LTS
BLENDER_MO_PATH = r"C:\Program Files\Blender Foundation\Blender 5.0\5.0\datafiles\locale\ja\LC_MESSAGES\blender.mo"

IGNORE_CHARS_RE = re.compile(r"^[ \t\r\n!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~0-9]*$")
PYTHON_FORMAT_RE = re.compile(r"\{.*?\}|%[0-9.-]*[sdfrxX%]|%\(.*?\)[sdfrxX]")


@app.command()
def extract_pot(
        addon_dir: str = typer.Option(..., "--dir", "-d", help="Path to the target addon root directory."),
        output: str = typer.Option("./locale/messages.pot", "--output", "-o", help="Output POT file path."),
        blender_mo: str = typer.Option(BLENDER_MO_PATH, "--blender-mo", help="Path to blender.mo for extracting existing keys to exclude."),
    ):
    """
    addon本体コードから翻訳対象文字列を抽出しPOTファイルを生成します。

      * 指定されたフォルダの第一階層ファイルのみを対象とします
      * 原則`"`ダブルクォートで囲まれた文字列を対象とします
      * 記号数字のみで構成される文字列は除外します
      * Docstring（関数・クラスの解説文）、print関数、Raise文（例外エラーメッセージ）の文字列は除外します
      * `bl_label` や UIメソッド（operator, prop, label, menu）および各種Property定義から、特定の引数（text, name, description）を明示的なコンテキスト（Operator等）を考慮して抽出します
      * Blender本体の翻訳ファイル（blender.mo）に既に登録されている標準キーは重複排除のため除外します
    """
    if not os.path.isdir(addon_dir):
        logging.error(f"Directory not found: {addon_dir}")
        raise typer.Exit(1)

    blender_keys = get_keys_from_blender_mo(blender_mo)

    extractor = AddonPOTExtractor(addon_dir, blender_keys)
    extractor.run()
    extractor.write_pot(output)
    logging.info(f"POT file successfully generated at: {output}")


def get_keys_from_blender_mo(mo_path: str):
    """
    Blender本体の翻訳ファイルからキーを抽出する(キーのみ)
    最新のLTSバージョンの内包blender.moを指定すること
    """
    if not os.path.exists(mo_path):
        logging.error(f"blender.mo file not found: {mo_path}")
        raise typer.Exit(1)
    with open(BLENDER_MO_PATH, "rb") as f:
        keys = set(gettext.GNUTranslations(f)._catalog.keys())
        logging.info(f"Loaded blender.mo: {len(keys)} keys from {mo_path}")
    final_keys: set[tuple[str, str]] = set()
    for key in keys:
        if "\x04" in key:  # EOTで区切られている
            msgctxt, msgid = key.split("\x04")
            final_keys.add((msgctxt, msgid))
        else:
            final_keys.add(("*", key))
    return final_keys


class AddonPOTExtractor:
    def __init__(self, root_dir, blender_keys):
        self.root_dir = root_dir
        self.catalog = {}
        self.blender_keys = blender_keys
        try:
            bl_info = self.get_bl_info()
            self.project_name = f"{bl_info['name']} {bl_info['version']}"
        except:
            logging.error(f"Invalid addon directory (bl_info not found): {root_dir}")
            raise typer.Exit(1)

    def add_entry(self, ctxt, msgid, filepath, lineno):
        if not msgid or not isinstance(msgid, str):
            return
        
        if IGNORE_CHARS_RE.match(msgid):
            return
        
        key = (ctxt, msgid)
        if key in self.blender_keys:
            return

        rel_path = os.path.relpath(filepath, self.root_dir).replace("\\", "/")
        location = f"{rel_path}:{lineno}"
        
        # フォーマット構文フラグの管理
        flags = set()
        if PYTHON_FORMAT_RE.search(msgid):
            flags.add("python-format")
        
        if key not in self.catalog:
            self.catalog[key] = ([], set())
            
        if location not in self.catalog[key][0]:
            self.catalog[key][0].append(location)
            
        if flags:
            self.catalog[key][1].update(flags)

    def extract_from_file(self, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()

        try:
            root_node = ast.parse(source, filepath)
        except SyntaxError as e:
            logging.warning(f"Syntax Error in {filepath}: {e}")
            return

        ignored_nodes = set()
        processed_nodes = set()

        def is_double_quoted(source_code, node):
            try:
                segment = ast.get_source_segment(source_code, node)
                if segment:
                    return segment.strip().startswith('"')
            except Exception:
                pass
            return False

        def is_operator_class(class_node):
            for base in class_node.bases:
                if isinstance(base, ast.Attribute) and base.attr == "Operator":
                    return True
                if isinstance(base, ast.Name) and base.id == "Operator":
                    return True
            if "_OT_" in class_node.name:
                return True
            return False

        def is_extractable_str_node(_node: ast.AST) -> TypeGuard[ast.Constant]:
            return isinstance(_node, ast.Constant) and isinstance(_node.value, str)

        def should_extract(_node):
            return _node not in ignored_nodes and is_double_quoted(source, _node)

        def iter_keyword_str_nodes(call_node, allowed_args):
            for keyword in call_node.keywords:
                if keyword.arg in allowed_args and is_extractable_str_node(keyword.value):
                    yield keyword.value

        def is_docstring(_node: ast.AST) -> TypeGuard[ast.Expr]:
            return isinstance(_node, ast.Expr) and isinstance(_node.value, ast.Constant) and isinstance(_node.value.value, str)

        def is_not_ui_output(_node: ast.AST) -> TypeGuard[ast.Call]:
            return isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name) and _node.func.id in ["print"]

        def walk_extractable_nodes(_root_node: ast.AST):
            for _node in ast.walk(_root_node):
                if is_extractable_str_node(_node):
                    yield _node

        # [事前走査] 不要ノード特定
        for node in ast.walk(root_node):
            if is_docstring(node):
                ignored_nodes.add(node.value)
            elif is_not_ui_output(node):
                for arg in node.args:
                    if is_extractable_str_node(arg):
                        ignored_nodes.add(arg)
                    for sub_node in walk_extractable_nodes(arg):
                        ignored_nodes.add(sub_node)
            elif isinstance(node, ast.Raise) and node.exc:
                for sub_node in walk_extractable_nodes(node.exc):
                    ignored_nodes.add(sub_node)

        # [本走査1] 構文構造に合わせた厳密なコンテキスト仕分け（そのまま完全維持）
        for node in ast.walk(root_node):
            if isinstance(node, ast.ClassDef):
                is_op = is_operator_class(node)
                for body_node in node.body:
                    if isinstance(body_node, ast.Assign):
                        for target in body_node.targets:
                            if isinstance(target, ast.Name) and target.id == "bl_label":
                                if is_extractable_str_node(body_node.value) and should_extract(body_node.value):
                                    ctxt = "Operator" if is_op else "*"
                                    self.add_entry(ctxt, body_node.value.value, filepath, body_node.lineno)
                                    processed_nodes.add(body_node.value)

            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
                if func_name == "operator":
                    for value_node in iter_keyword_str_nodes(node, {"text"}):
                        if should_extract(value_node):
                            self.add_entry("Operator", value_node.value, filepath, node.lineno)
                            processed_nodes.add(value_node)
                    if node.args and is_extractable_str_node(node.args[0]):
                        processed_nodes.add(node.args[0])

                elif func_name.endswith("Property") or func_name in {"prop", "label", "menu"}:
                    for value_node in iter_keyword_str_nodes(node, {"name", "text", "description"}):
                        if should_extract(value_node):
                            self.add_entry("*", value_node.value, filepath, node.lineno)
                            processed_nodes.add(value_node)

        # [本走査2] pgettext系エイリアス関数の抽出
        alias_funcs = {"_", "iface_", "tip_", "data_", "f_", "f_iface_", "f_tip_", "f_data_"}
        for node in ast.walk(root_node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in alias_funcs:
                # 第1引数（翻訳対象文字列）がある場合のみ
                if node.args and is_extractable_str_node(node.args[0]):
                    msgid_node = node.args[0]
                    if should_extract(msgid_node):
                        ctxt = "*"
                        # _(text="text", msgctxt="Operator") のようなケース
                        for keyword in node.keywords:
                            if keyword.arg == "msgctxt" and is_extractable_str_node(keyword.value):
                                ctxt = keyword.value.value
                                break
                        # _("text", "Operator") のようなケース
                        if ctxt == "*" and len(node.args) >= 2 and is_extractable_str_node(node.args[1]):
                            ctxt = node.args[1].value
                        self.add_entry(ctxt, msgid_node.value, filepath, node.lineno)
                        processed_nodes.add(msgid_node)

        # [本走査3] フォールバック（そのまま完全維持）
        for node in walk_extractable_nodes(root_node):
            if node in ignored_nodes or node in processed_nodes:
                continue
            if is_double_quoted(source, node):
                if ("Operator", node.value) in self.catalog:
                    continue
                self.add_entry("*", node.value, filepath, node.lineno)

    def run(self):
        entries = sorted(
            [e for e in os.scandir(self.root_dir) if e.is_file() and e.name.endswith(".py")],
            key=lambda e: e.name
        )

        logging.info(f"[bold cyan]Target addon:[/] {self.project_name}")
        logging.info(f"  Found {len(entries)} Python files")

        progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("{task.fields[value]}")
        )
        with progress:
            task = progress.add_task("Extracting...", total=len(entries), value="")
            total = len(entries)
            for i, entry in enumerate(entries):
                progress.update(task, value=f"({i+1}/{total}) {entry.name}")
                self.extract_from_file(entry.path)
                progress.advance(task)
            progress.update(task, value=f"({total}/{total}) [Completed]")

    def get_bl_info(self) -> dict:
        """
        Blender addon の __init__.py から bl_info 辞書を抽出する
        """
        init_py_path = os.path.join(self.root_dir, "__init__.py")
        with open(init_py_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, init_py_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "bl_info":
                        # 辞書型（ast.Dict）であれば、安全にPythonのdictに変換する
                        if isinstance(node.value, ast.Dict):
                            # ast.literal_eval を使うことで、安全に文字列やタプルを評価してdict化できます
                            return ast.literal_eval(node.value)
        raise Exception("Could not extract bl_info from __init__.py")

    def write_pot(self, output_path):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def escape(text):
            return json.dumps(text, ensure_ascii=False)[1:-1]

        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(textwrap.dedent(f'''\
                msgid ""
                msgstr ""
                "Project-Id-Version: {self.project_name}\\n"
                "POT-Creation-Date: {now}\\n"
                "MIME-Version: 1.0\\n"
                "Content-Type: text/plain; charset=UTF-8\\n"
                "Content-Transfer-Encoding: 8bit\\n"
                
                '''))

            for (ctxt, msgid), (locations, flags) in self.catalog.items():
                for loc in locations:
                    f.write(f"#: {loc}\n")
                if flags:
                    flag_str = ", ".join(sorted(flags))
                    f.write(f"#, {flag_str}\n")
                f.write(f'msgctxt "{escape(ctxt)}"\n')
                f.write(f'msgid "{escape(msgid)}"\n')
                f.write('msgstr ""\n\n')
