import json
import logging
import math
import os
import polib
import re
import textwrap
import typer
from dotenv import load_dotenv
from google import genai
from rich.logging import RichHandler
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn


app = typer.Typer()
logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler(markup=True)])

GEMINI_FLAG = "mt:gemini"
CHUNK_SIZE = 200  # 300ぐらいからAPIリクエストサイズの上限に達する


@app.command()
def ai_translate(
        po_path: str = typer.Option(..., "--po", "-p", help="Path to the target PO file to update (e.g., ./locale/en_US.po)."),
        dry_run: bool = typer.Option(False, "--dry-run", help="Simulate the translation process, output requests, and estimate token costs."),
        max_api_calls: int = typer.Option(None, "--max-api-calls", help="The maximum number of API calls allowed per target language.", min=1)
    ):
    """
    Gemini(2.5-flash)を利用して指定POファイルの未翻訳部分を埋めて更新します。

      * `GEMINI_API_KEY` 環境変数に有効なAPIキー設定が必要です
      * 事前にコンテクストとして本addonコード全部を渡してGemini Cacheを作成し、Cache IDを作成して `.env` ファイル経由で取得できる必要があります
        - Cache ID取得には `ai_prepare.py` を使います
      * 翻訳には従量課金が発生し、もし1言語分まるまる翻訳すると約1.00USDほどかかります
        - 事前に `--dry-run` オプションにて消費トークン数概算見積とAPIコール数を確認するのがおすすめです
        - 翻訳対象ボリュームが多い場合はチャンクしながらの実行となりますが、初回は `--max-api-calls=1` で1チャンク分で試すとよいです
        - 全て埋まっているなどして翻訳対象が存在しない場合は課金は発生しません
      * POファイル中の下記のエントリが翻訳対象となります
        - `msgstr` が空のエントリ
        - fuzzyフラグが立っている、かつ `mt:gemini` コメントフラグが入っていないエントリです (再翻訳防止)
      * 翻訳したもので更新されたエントリには、fuzzyフラグ(要確認用)と `mt:gemini` コメントフラグが付きます
      * fuzzyフラグ付きのエントリでも翻訳に使われますが、Poeditなどのエディタで確認済みとしてfuzzyフラグを消去する運用が望ましいです
    """
    if not os.path.exists(po_path):
        logging.error(f"Target PO file not found at {po_path}")
        return

    load_dotenv(".env")
    # dry-run時はAPIキー・キャッシュIDがなくても動く
    if not dry_run:
        if not os.environ.get("GEMINI_API_KEY"):
            logging.error("GEMINI_API_KEY environment variable is not set.")
            raise typer.Exit(1)
        if not os.environ.get("GEMINI_CACHE_ID"):
            logging.error("GEMINI_CACHE_ID environment variable is not set. Make sure to run ai_prepare.py first to create a cache and set this variable.")
            raise typer.Exit(1)
    cache_id = os.environ.get("GEMINI_CACHE_ID", "*****")

    client = None if dry_run else genai.Client()

    # POファイル読み込み
    po = polib.pofile(po_path)
    target_lang_name, lang_code = get_target_language_info(po_path, po)
    if target_lang_name is None:
        logging.error(
            f"Unknown language detected at {po}. Check `Language` metadata or filename or `language_data` installed.")
        return
    logging.info(f"[bold cyan]Target Language:[/] {target_lang_name} ({lang_code})")
    logging.info(f"[bold cyan]Using Cache ID :[/] {cache_id}")
    if dry_run:
        logging.warning("[bold yellow]DRY-RUN MODE ACTIVE:[/] No API calls will be made, and no files will be altered.")

    # 翻訳が必要なエントリーのフィルタリング(翻訳元が日英で分ける)
    tasks_from_en = []
    tasks_from_ja = []
    po_cache = {}
    skipped_same_lang_count = 0
    for entry in po:
        ctxt = entry.msgctxt if entry.msgctxt else "*"
        key = (ctxt, entry.msgid)
        po_cache[key] = entry

        # Gemini翻訳フラグが入っているものは対象外
        if GEMINI_FLAG in entry.comment.split("\n"):
            continue

        # 翻訳文章が既にあってfuzzyでないものは対象外
        if entry.msgstr and "fuzzy" not in entry.flags:
            continue

        # ソースコードのメッセージ言語は日本語か英語の想定で翻訳元を判定
        src_lang = "Japanese" if re.search(r"[\u3040-\u30ff\u4e00-\u9faf]", entry.msgid) else "English"
        # 翻訳元と翻訳先が同じであればスキップ
        if target_lang_name.startswith(src_lang):
            skipped_same_lang_count += 1
            # ただし空なら同値で埋める
            if not entry.msgstr:
                entry.msgstr = entry.msgid
            continue

        task_item = {
            "msgctxt": ctxt,
            "msgid": entry.msgid,
            "msgstr": ""
        }
        if src_lang == "Japanese":
            tasks_from_ja.append(task_item)
        else:
            tasks_from_en.append(task_item)

    logging.info(f"Filtering Complete: Skipped {skipped_same_lang_count} identical direction entries.")
    if not tasks_from_en and not tasks_from_ja:
        if not dry_run:
            save_po_lf(po, po_path)
        logging.info("[bold green]Everything is up to date! No entries require API translation.")
        return
    else:
        logging.info(f" -> English to {target_lang_name} queue: {len(tasks_from_en)} items")
        logging.info(f" -> Japanese to {target_lang_name} queue: {len(tasks_from_ja)} items")

    # コスト見積もり用の集計カウンター
    total_api_calls = 0
    estimated_input_tokens = 0
    estimated_output_tokens = 0

    try:
        progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("{task.fields[value]}")
        )
        with progress:
            total_count = len(tasks_from_ja) + len(tasks_from_en)
            total_processed = 0
            total_chunks_overall = math.ceil(len(tasks_from_ja) / CHUNK_SIZE) + math.ceil(len(tasks_from_en) / CHUNK_SIZE)
            all_task = progress.add_task("Translating Messages...", total=total_count, value="", visible=not dry_run)
            chunk_task = progress.add_task("Processing Chunks...", total=total_chunks_overall, value="", visible=not dry_run)

            for source_lang_name, tasks in [("English", tasks_from_en), ("Japanese", tasks_from_ja)]:
                if len(tasks) == 0:
                    continue
                # チャンク分割して翻訳リクエストする
                for i in range(0, len(tasks), CHUNK_SIZE):
                    if max_api_calls and max_api_calls <= total_api_calls:
                        break
                    chunk = tasks[i:i + CHUNK_SIZE]
                    chunk_idx = (i // CHUNK_SIZE) + 1
                    total_chunks = (len(tasks) + CHUNK_SIZE - 1) // CHUNK_SIZE
                    total_api_calls += 1
                    total_processed += len(chunk)

                    dynamic_prompt = textwrap.dedent(f"""\
                        [Dynamic Translation Direction]
                        - Source Language: {source_lang_name}
                        - Target Language: {target_lang_name}

                        Please translate the 'msgid' fields in the following JSON array into {target_lang_name}.
                        Return the exact same JSON array structure, filling in the 'msgstr' fields with your translation.
                        {json.dumps(chunk, ensure_ascii=False, indent=2)}
                        """)

                    # トークン数見積用処理
                    chunk_input_tokens = estimate_tokens(dynamic_prompt)
                    estimated_input_tokens += chunk_input_tokens
                    chunk_output_tokens = int(chunk_input_tokens * 1.3)  # レスポンス増量が1.3倍と仮定
                    estimated_output_tokens += chunk_output_tokens

                    if dry_run:
                        logging.info(
                            f"\n--- [API Call #{total_api_calls}] [{source_lang_name} -> {target_lang_name}] Chunk {chunk_idx}/{total_chunks} ---")

                        # dry-run時はリクエストプロンプトをすべて標準出力する
                        logging.info("[bold magenta][PROMPT SENT TO GEMINI][/]")
                        logging.info(shorten_for_log(dynamic_prompt))
                        logging.info(
                            f"Estimated Tokens for this chunk -> Input: {chunk_input_tokens}, Expected Output: {chunk_output_tokens}")
                        logging.info("-" * 50)
                        continue

                    try:
                        # Gemini API呼び出し
                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=dynamic_prompt,
                            config=genai.types.GenerateContentConfig(
                                cached_content=cache_id,
                                response_mime_type="application/json",
                                temperature=0.1,
                            ),
                        )

                        try:
                            translated_results = json.loads(response.text.strip())
                        except json.JSONDecodeError:
                            cleaned_text = re.sub(r"^```json\s*|```$", "", response.text.strip(), flags=re.MULTILINE)
                            translated_results = json.loads(cleaned_text)

                        # 翻訳結果をPOエントリーに反映
                        for result in translated_results:
                            ctxt = result.get("msgctxt", "*")
                            msgid = result.get("msgid", "")
                            msgstr = result.get("msgstr", "")

                            key = (ctxt, msgid)
                            if key in po_cache and msgstr:
                                entry = po_cache[key]
                                entry.msgstr = msgstr
                                # 要確認フラグを追加
                                if "fuzzy" not in entry.flags:
                                    entry.flags.append("fuzzy")
                                # flagに入れたいが、Poeditで編集保存すると消されてしまうためコメントに追加
                                if GEMINI_FLAG not in entry.comment.split("\n"):
                                    if entry.comment:
                                        entry.comment += "\n"
                                    entry.comment += GEMINI_FLAG

                        progress.update(all_task, value=f"({total_processed}/{total_count})")
                        progress.advance(all_task, len(chunk))
                        progress.update(chunk_task, value=f"({total_api_calls}/{total_chunks_overall}) {source_lang_name} -> {target_lang_name} ({chunk_idx}/{total_chunks})")
                        progress.advance(chunk_task)

                    except Exception as chunk_error:
                        logging.warning(f"Failed to process chunk {chunk_idx}: {chunk_error}")
                        continue
            limited = "(Limited)" if max_api_calls and max_api_calls < total_chunks_overall else ""
            progress.update(all_task, value=f"({total_processed}/{total_count}) [Completed] {limited}")
            progress.update(chunk_task, value=f"({total_api_calls}/{total_chunks_overall}) [Completed] {limited}")

        # コスト集計結果のサマリー出力
        logging.info("[bold blue]" + "=" * 45 + "[/]")
        logging.info("[bold blue]           COST ESTIMATION REPORT            [/]")
        logging.info("[bold blue]" + "=" * 45 + "[/]")
        logging.info(f"Total Projected API Calls   : {total_api_calls} times")
        logging.info(f"Estimated Input Tokens      : {estimated_input_tokens} tokens")
        logging.info(f"Estimated Output Tokens     : {estimated_output_tokens} tokens")
        logging.info(f"Total Incremental Tokens    : {estimated_input_tokens + estimated_output_tokens} tokens")
        logging.info("[bold blue]" + "=" * 45 + "[/]")

        if not dry_run:
            # POファイル保存
            save_po_lf(po, po_path)
            logging.info(f"[bold green]Successfully updated translation file directly:[/] {po_path}")
        else:
            logging.info("[bold yellow][DRY-RUN][/] [bold green]No changes were written to the PO file.")

    except Exception as e:
        logging.error(f"An error occurred during execution: {e}")


def get_target_language_info(po_path, po_obj):
    """
    POファイルのメタデータまたはファイル名から翻訳対象の言語名(英名)を取得
    """
    from langcodes import Language
    lang_code = po_obj.metadata.get("Language", "")
    if not lang_code:
        base_name = os.path.basename(po_path)
        lang_code = os.path.splitext(base_name)[0]
        
    normalized_code = lang_code.replace("_", "-")
    try:
        lang_name = Language.get(normalized_code).display_name()
    except Exception:
        lang_name = None
    return lang_name, lang_code


def estimate_tokens(text):
    """
    文字数からトークン数を簡易見積もりして返却する
    日本語やJSON構造記号等はトークンを多く消費するため、全角/記号:1.2トークン、英数字:0.35トークン 程度で傾斜配分する
    """
    total_tokens = 0
    for char in text:
        if re.match(r"[a-zA-Z0-9 ]", char):
            total_tokens += 0.35
        else:
            total_tokens += 1.2
    return int(total_tokens)


def shorten_for_log(text: str, max_lines: int = 28, head_lines: int = 17) -> str:
    """
    長文を先頭/末尾だけ残して中間を省略表記して返却する
    """
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text

    tail_lines = max_lines - head_lines
    head = lines[:head_lines]
    tail = lines[-tail_lines:] if tail_lines > 0 else []
    omitted_count = len(lines) - len(head) - len(tail)
    marker = f"------- ( omitted {omitted_count} lines ) --------"
    return "\n".join(head + [marker] + tail)


def save_po_lf(po_obj: polib.POFile, path: str) -> None:
    """
    POをLF改行で保存する。
    """
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(str(po_obj))
