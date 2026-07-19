import logging
import os
import polib
import typer
from rich.logging import RichHandler

app = typer.Typer()
logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler(markup=True)])


@app.command()
def merge_po(
        source: str = typer.Option(..., "--source", "-s", help="Path to the newly extracted POT file (e.g., ./locale/messages.pot)"),
        target: str = typer.Option(..., "--target", "-t", help="Path to the existing target PO file to be updated (e.g., ./locale/en_US.po)")
    ):
    """
    POTファイルからPOファイルをマージ更新します。POファイルが存在しない場合はPOTをコピーして新規生成します。

    * POTに追加されたエントリはPOファイルにも追加されます
    * POTに存在しなくなったエントリはPOファイルからも削除されます
    * コード上の位置が変わった場合はPOファイルのメタ情報を更新します
    """
    # ファイルの存在チェック
    if not os.path.exists(source):
        logging.error(f"Source template file not found at {source}")
        raise typer.Exit(1)

    # ターゲット（既存のPO）が存在しない場合は、新規作成としてソースをそのままコピー保存する
    if not os.path.exists(target):
        logging.info(f"Target PO file not found. Creating a new one from template: {target}")
        try:
            # ディレクトリがなければ作成
            target_dir = os.path.dirname(target)
            if target_dir and not os.path.exists(target_dir):
                os.makedirs(target_dir)
                
            po_source = polib.pofile(source)

            metadata = dict(po_source.metadata or {})
            lang_code = os.path.splitext(os.path.basename(target))[0]
            metadata["Language"] = lang_code
            po_source.metadata = metadata
            save_po_lf(po_source, target)
            logging.info("[bold green]Successfully initialized new target PO file.")
        except Exception as e:
            logging.error(f"Failed to initialize target PO file: {e}")
            raise typer.Exit(1)
        return

    logging.info(f"[bold cyan]Merging[/] {source} into {target}...")

    try:
        # 両方のファイルを読み込む
        po_source = polib.pofile(source)
        po_target = polib.pofile(target)

        # 既存のターゲット内にある翻訳データをインデックス化 (キー: (msgctxt, msgid))
        target_cache = {}
        for entry in po_target:
            ctxt = entry.msgctxt if entry.msgctxt else "*"
            target_cache[(ctxt, entry.msgid)] = entry

        # 新しい空のPOオブジェクトを作成（ソースの順序やメタデータをベースにするため）
        new_po = polib.POFile()
        new_po.metadata = po_target.metadata  # 既存の言語設定やメタデータを引き継ぐ
        # addon バージョンはソースをコピー
        for key in ["Project-Id-Version", "POT-Creation-Date"]:
            new_po.metadata[key] = po_source.metadata[key]

        # ソース（最新のコード状態）をベースに再構築
        added_count = 0
        retained_count = 0
        
        for source_entry in po_source:
            ctxt = source_entry.msgctxt if source_entry.msgctxt else "*"
            key = (ctxt, source_entry.msgid)
            
            if key in target_cache:
                # すでに存在する文言：既存の翻訳結果（msgstr）、フラグ（fuzzyなど）、コメントを完全に引き継ぐ
                existing_entry = target_cache[key]
                # コード上の位置（occurrences）のみ最新の状態に更新
                existing_entry.occurrences = source_entry.occurrences
                new_po.append(existing_entry)
                retained_count += 1
            else:
                # コードに新しく追加された文言：新規エントリーとして追加
                new_po.append(source_entry)
                added_count += 1

        # 上書き保存
        save_po_lf(new_po, target)

        logging.info("[bold blue]Merge Complete")
        logging.info(f"  Retained / Updated keys : {retained_count}")
        logging.info(f"  Newly added keys        : {added_count}")
        logging.info(f"[bold green]Successfully saved directly to:[/] {target}")

    except Exception as e:
        logging.error(f"An error occurred during merging: {e}")


def save_po_lf(po_obj: polib.POFile, path: str) -> None:
    """
    POをLF改行で保存する。
    """
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(str(po_obj))
