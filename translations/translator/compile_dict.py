import json
import logging
import os
import textwrap
import polib
import typer
from rich.logging import RichHandler

app = typer.Typer()
logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler(markup=True)])


@app.command()
def compile_dict(
        locale_path: str = typer.Option("./locale", "--locale", "-l", help="Directory path containing target .po files."),
        output_path: str = typer.Option(..., "--output", "-o", help="Directory path where compiled Python modules will be saved."),
    ):
    """
    指定したlocaleディレクトリの全POファイルをひとまとめにコンパイルして、Blender翻訳用Pythonファイルとして最適化された形式で出力します。
    """
    if not os.path.isdir(locale_path):
        logging.error(f"Locale directory not found: {locale_path}")
        raise typer.Exit(1)

    logging.info(f"[bold cyan]Scanning PO files in:[/] {locale_path}")
    compiled_data = generate_translation_dict(locale_path)

    if not compiled_data:
        logging.error("No valid translation data found to compile.")
        raise typer.Exit(1)

    logging.info(f"[bold cyan]Writing Python module to:[/] {output_path}")
    write_python_module(compiled_data, output_path)
    logging.info("[bold green]Compilation completed successfully!")


def generate_translation_dict(locale_dir):
    """
    locale ディレクトリ内のすべての .po ファイルを走査し、
    Blender用の一括翻訳辞書データを構築する
    """
    compiled_data = {}

    # ディレクトリ内のファイルをスキャン
    for root, _, files in os.walk(locale_dir):
        for file in files:
            if not file.endswith(".po"):
                continue

            po_path = os.path.join(root, file)
            try:
                po = polib.pofile(po_path)
            except Exception as e:
                logging.error(f"Failed to parse PO file {file}: {e}")
                continue

            lang_code = po.metadata.get('Language', '')
            if not lang_code:
                lang_code = os.path.splitext(file)[0]

            logging.info(f"[bold cyan]Processing language:[/] [{lang_code}] ({po_path})")

            lang_dict = {}
            saved_count = 0
            skipped_count = 0

            for entry in po:
                msgctxt = entry.msgctxt if entry.msgctxt else "*"
                msgid = entry.msgid
                msgstr = entry.msgstr

                # 翻訳文が空のものはスキップ
                if not msgstr:
                    continue

                # 原文と翻訳文が同じものはスキップ
                if msgid == msgstr:
                    skipped_count += 1
                    continue

                lang_dict[(msgctxt, msgid)] = msgstr
                saved_count += 1

            if lang_dict:
                compiled_data[lang_code] = lang_dict
                logging.info(f"  [bold blue]Compiled[/] {saved_count} entries (Skipped {skipped_count} redundant fallback entries)")

    return compiled_data


def write_python_module(compiled_data, output_path):
    """
    辞書データをBlender addon用フォーマットのPythonモジュールファイルとして保存
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    def esc(text):
        return json.dumps(text, ensure_ascii=False)[1:-1]

    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(textwrap.dedent("""\
            # Generated automatically by custom PO-to-Py compiler. DO NOT EDIT DIRECTLY.
            
            # Blender translation dictionary data
            translation_dict = {
            """))
        for lang_code in sorted(compiled_data.keys()):
            f.write(f'    "{lang_code}": {{\n')
            lang_entries = compiled_data[lang_code]
            for msgctxt, msgid in sorted(lang_entries.keys(), key=lambda x: (x[0], x[1])):
                msgstr = lang_entries[(msgctxt, msgid)]
                f.write(f'        ("{esc(msgctxt)}", "{esc(msgid)}"): "{esc(msgstr)}",\n')
            f.write("    },\n")
        f.write("}\n")
