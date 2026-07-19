import logging
import os
import re
import textwrap
from datetime import datetime, timedelta, timezone
import typer
from dotenv import load_dotenv, set_key
from google import genai
from rich.logging import RichHandler

app = typer.Typer()
logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[RichHandler(markup=True)])

MIN_REMAINING_TTL = 600


@app.command()
def ai_prepare(
        addon_dir: str = typer.Option(..., "-d", "--dir", help="Path to the target addon root directory."),
        ttl: int = typer.Option(3600, "-t", "--ttl", help="Cache TTL in seconds (default: 3600)."),
        delete_cache: bool = typer.Option(False, "--delete-cache", help="Delete Cache ID immediately from the server."),
        dry_run: bool = typer.Option(False, "--dry-run", help="Simulate cache creation, preview the combined text, and estimate token sizes without calling the Gemini API.")
    ):
    """
    Geminiを利用して翻訳作業をするための準備として対象のソースコードをコンテクストキャッシュとしてアップロードします。

    * 既にキャッシュIDが存在する場合は、TTLが十分に残っていれば新規作成しません（料金がかかりません）
    * TTLが残り少ない場合は、TTLを最低必要時間分延長更新して終了します（延長時間分のわずかな料金のみで、トークン消費はありません）
    * キャッシュIDが存在しない場合は、対象のaddonディレクトリの第一階層にあるPythonコードを結合してコンテクストとしてアップロードします（トークンを多く消費します）
    * `--dry-run` オプションを指定すると、Gemini APIを呼ばずに、結合されたテキストのプレビューとトークン数の概算を表示します
    * `--delete-cache` オプションを指定すると、キャッシュIDを即座に削除します
    """
    load_dotenv(".env")
    # dry-run時はAPIキーがなくてもよい
    if not dry_run and not os.environ.get("GEMINI_API_KEY"):
        logging.error("GEMINI_API_KEY environment variable is not set.")
        raise typer.Exit(1)

    if dry_run:
        logging.warning("[bold yellow]DRY-RUN MODE ACTIVE:[/] No API calls will be made.")

    client = None if dry_run else genai.Client()

    # キャッシュの明示的削除モード
    if delete_cache:
        cache_id = os.environ.get("GEMINI_CACHE_ID")
        if cache_id:
            if dry_run:
                logging.warning(f"[bold yellow][DRY-RUN][/] Would delete remote cache: {cache_id}")
                return

            logging.info(f"Deleting remote cache: {cache_id} ...")
            try:
                client.caches.delete(name=cache_id)
                set_key(".env", "GEMINI_CACHE_ID", "")
                logging.info("[bold green]Successfully deleted.")
                return
            except Exception as e:
                logging.error(f"Failed to delete cache: {e}")
                raise typer.Exit(1)

    # キャッシュIDがある場合、まだ有効か確認してから上書きするかどうかを判断する
    existing_cache_id = os.environ.get("GEMINI_CACHE_ID")
    if existing_cache_id:
        if dry_run:
            logging.warning(f"[bold yellow][DRY-RUN][/] Existing cache ID found: {existing_cache_id}. Would check validity and decide on overwrite.")
        else:
            logging.info(f"Existing cache ID found: {existing_cache_id}. Checking validity...")
            try:
                cache_info = client.caches.get(name=existing_cache_id)
                if cache_info:
                    if cache_info.expire_time > datetime.now(timezone.utc) + timedelta(seconds=MIN_REMAINING_TTL):
                        logging.info(f"[bold yellow]Existing cache is still valid (expires at {cache_info.expire_time}). It will be overwritten with new content.")
                    else:
                        # TTLをMIN_REMAINING_TTLで更新
                        extended_cache = client.caches.update(
                            name=existing_cache_id,
                            config={"ttl": f"{MIN_REMAINING_TTL}s"}
                        )
                        logging.info(
                            f"[bold green]Extended existing cache TTL by {MIN_REMAINING_TTL}s.[/] "
                            f"New expire time: {extended_cache.expire_time}"
                        )
                        return
                else:
                    logging.info("Existing cache has expired or is invalid. It will be overwritten with new content.")
            except Exception as e:
                logging.warning(f"Could not retrieve existing cache info (it may have already expired): {e}. Proceeding to create new cache.")

    # キャッシュの新規作成モード
    logging.info(f"[bold cyan]Scanning addon root directory[/] (First level only): {addon_dir}")
    source_context = make_context_from_addon_dir(addon_dir)
    logging.info(f"  Context size: {len(source_context)} characters.")

    # システム指示の定義
    system_instruction = textwrap.dedent(f"""\
        You are an expert technical translator specializing in Blender addon development.
        Analyze the cached addon source code context to fully understand the addon's specific features, internal mechanics, and workflows.

        Your task is to translate the given JSON list of UI strings (msgid) into the specified target language (msgstr) by following the dynamic directions provided in the user request.

        Strict Translation Rules:
        1. When msgctxt is "Operator", it represents a button or menu action (Verb). Use concise, actionable terminology suitable for a UI button.
        2. Standard Blender terminology (Bone, Weight, Shape Key, Mesh, etc.) must be accurately translated into standard target language terms used in the official Blender software.
        3. For general contexts (msgctxt is "*"), maintain a user-friendly and clear tone suitable for a professional software UI.
        4. Keep the exact JSON structure in your response. Return ONLY the JSON array matching the input structure, filling in the "msgstr" fields. Do not include markdown code block wraps like ```json.
        """)
    ttl_string = f"{ttl}s"

    # トークン数の簡易見積もり
    instruction_tokens = estimate_tokens(system_instruction)
    context_tokens = estimate_tokens(source_context)
    total_cached_tokens = instruction_tokens + context_tokens

    logging.info("[bold blue]====== CACHE PREVIEW REPORT ======================")
    logging.info("[bold blue]------ System instruction (immutable rules) ------")
    logging.info(system_instruction.strip())
    logging.info("[bold blue]------ Source code content preview ---------------")
    logging.info(shorten_for_log(source_context.strip()))
    logging.info("[bold blue]------ Estimated token size ----------------------")
    logging.info(f"System Instruction Tokens : ~{instruction_tokens} tokens")
    logging.info(f"Source Context Tokens     : ~{context_tokens} tokens")
    logging.info(f"Total Projected Cache Size: ~{total_cached_tokens} tokens")
    logging.info("[bold blue]==================================================")

    if dry_run:
        logging.info("[bold yellow][DRY-RUN][/] [bold green]No request sent to Gemini. Cache creation skipped.")
        return

    # 以下、本実行処理
    logging.info(f"[bold cyan]Synchronizing[/] context and instructions to Gemini (TTL: {ttl} seconds)...")

    cache_config = {
        "ttl": ttl_string,
        "display_name": "addon_shared_source_context",
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": source_context}]
            }
        ]
    }

    try:
        cached_content = client.caches.create(
            model="gemini-2.5-flash",
            config=cache_config
        )
        cache_id = cached_content.name
        set_key(".env", "GEMINI_CACHE_ID", cache_id)
        logging.info(f"[bold purple]CACHE_ID: {cache_id}")
        logging.info("[bold green]Successfully cached addon source context.")
    except Exception as e:
        logging.error(f"Failed to create cache: {e}")
        raise typer.Exit(1)


def make_context_from_addon_dir(root_dir):
    """
    addonフォルダ第一階層にあるPythonコードのみを結合してテキスト化
    """
    context_text = "=== ADDON SOURCE CODE CONTEXT ===\n"
    try:
        with os.scandir(root_dir) as entries:
            for entry in entries:
                if entry.is_file() and entry.name.endswith(".py"):
                    with open(entry.path, "r", encoding="utf-8") as f:
                        context_text += f"\n--- File: {entry.name} ---\n"
                        context_text += f.read() + "\n"
    except Exception as e:
        logging.error(f"Failed to make source context from {root_dir}: {e}")
        raise typer.Exit(1)
    return context_text


def estimate_tokens(text):
    """
    文字数から大まかなトークン数を簡易見積もりするロジック。
    ソースコードは英数字・記号・インデントスペースが大半を占めるため、
    安全側に振って「全角/記号: 1.2トークン、英数字/空白: 0.35トークン」で計算します。
    """
    total_tokens = 0
    for char in text:
        if re.match(r'[a-zA-Z0-9 ]', char):
            total_tokens += 0.35
        else:
            total_tokens += 1.2
    return int(total_tokens)


def shorten_for_log(text: str, max_lines: int = 20, head_lines: int = 10) -> str:
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
