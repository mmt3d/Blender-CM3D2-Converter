import os
import re
import subprocess
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from pathlib import Path
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.spinner import Spinner


# 環境変数
load_dotenv(".env")
BLENDER_PATH_FMT = os.environ.get("BLENDER_PATH_FMT", "")
BLENDER_VERSIONS = os.environ.get("BLENDER_VERSIONS", "").split(" ")
BLENDER_PATHS = [BLENDER_PATH_FMT.format(x) for x in BLENDER_VERSIONS]
MAX_WORKER_NUM = int(os.environ.get("MAX_WORKER_NUM", 5))

SIGNAL_RE = re.compile(r"__TEST_([\w]+)__:([\w._]+)$")
console = Console()


def run_runner(blender_path: str, runner_script: Path, versions: list, test_files: list,
               status_matrix: dict, live):
    """
    Blenderを起動してテストランナースクリプトを実行する
    """
    path = Path(blender_path)
    v_name = path.parent.name
    log_dir = runner_script.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    raw_log_path_fmt = log_dir / f"_raw_{v_name}_{{tf_name}}.log"

    # Blender起動
    cmd = [str(path), "-b", "-P", str(runner_script), "--", "--raw-log-path-fmt", raw_log_path_fmt, "-m", "not profile"]
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore'
    )

    for tf in test_files:
        status_matrix[(v_name, tf)] =  Spinner("point", text="[bold yellow]Booting[/]")
    live.update(generate_table(versions, test_files, status_matrix))

    # pipeが止まるまで進捗報告を受信して経過表を更新する
    is_running = False
    other_log = ""
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            clean_line = line.strip()
            m = SIGNAL_RE.match(clean_line)
            if m:
                event, current_tf = m.groups()
                if (v_name, current_tf) in status_matrix:
                    if not is_running:
                        for tf in test_files:
                            status_matrix[(v_name, tf)] = ""
                        is_running = True
                    if event == "START":
                        status_matrix[(v_name, current_tf)] = Spinner("dots", text="[bold cyan]Running[/]")
                    elif event == "PASS":
                        status_matrix[(v_name, current_tf)] = "[bold green]✔ Pass[/]"
                    elif event == "FAIL":
                        status_matrix[(v_name, current_tf)] = "[bold red]✘ Fail[/]"
                    elif event == "FATAL":
                        status_matrix[(v_name, current_tf)] = "[bold red]☠ Critical[/]"
                    live.update(generate_table(versions, test_files, status_matrix))
            else:
                other_log += line

    # 生ログを読み込みメタ情報を追記してログを保存
    return_code = process.poll()
    failed_logs = []
    for tf in test_files:
        current_status = status_matrix[(v_name, tf)]
        raw_log_path = log_dir / f"_raw_{v_name}_{tf}.log"
        if raw_log_path.exists():
            with open(raw_log_path, "r", encoding="utf-8") as f:
                content = f.read()
            status = "PASS" if "Pass" in str(current_status) else "FAIL"
            log_path = save_log(v_name, tf, content, log_dir, return_code, status)
            if status == "FAIL":
                failed_logs.append((v_name, tf, log_path))
            raw_log_path.unlink()
        else:
            # 生ログがない場合、致命的な強制終了が発生していると解釈、ログは作らない
            status_matrix[(v_name, tf)] = "[bold red]☠ Critical[/]"
            log_path = save_log(v_name, tf, other_log, log_dir, return_code, "CRITICAL")
            failed_logs.append((v_name, tf, log_path))

    live.update(generate_table(versions, test_files, status_matrix))
    return failed_logs


def save_log(v_name: str, tf_name: str, log: str, log_dir: Path, return_code: int|None, status: str):
    """
    ログファイル記録
    """
    log_dir.mkdir(exist_ok=True)
    safe_version = v_name.replace(" ", "_").replace(".", "_")
    safe_script = tf_name.replace(".", "_")
    log_file_path = log_dir / f"{safe_version}_{safe_script}.log"
    with open(log_file_path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(f"""\
            Blender Version: {v_name}
            Test Script: {tf_name}
            Process Return Code: {return_code}
            Test Status: {status}
            --------------------------------------------------
             
            """))
        f.write(log)
    return log_file_path


def generate_table(versions: list[str], test_files: list[str], status_matrix: dict) -> Table:
    """
    richのTableオブジェクトを生成
    """
    table = Table(
        title="Blender-CM3D2-Converter Multi-Version Test Matrix",
        title_justify="left",
        title_style="bold blue",
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
    )

    # 列定義（行ヘッダーとなるテストファイル名列を追加）
    table.add_column("Test File", style="dim", width=25)
    for v in versions:
        table.add_column(v, justify="center", width=11)

    # 行データの追加
    for tf in test_files:
        row_cells = [tf]
        for v in versions:
            status = status_matrix.get((v, tf), "[dim]-[/]")
            row_cells.append(status)
        table.add_row(*row_cells)

    return table


def run_all_tests():
    """
    全Blenderバージョン x 全テストケース を実施
    """
    test_dir = Path(__file__).parent
    runner_script = test_dir / "runner.py"

    test_scripts = test_dir.glob("test_*.py")
    blender_paths = []
    for path in BLENDER_PATHS:
        if os.path.exists(path):
            blender_paths.append(path)
        else:
            console.print(f"[bold red][ERROR] Blender path not found：[/] {path}\n")
    versions = [Path(p).parent.name for p in blender_paths]
    test_files = [p.name for p in test_scripts]

    # ステータスの初期化（未実行は灰色のハイフン）
    status_matrix = {(v, tf): "[dim]-[/]" for v in versions for tf in test_files}

    # 進捗マトリックス表を動的更新
    failed_logs = []
    with Live(generate_table(versions, test_files, status_matrix), console=console, refresh_per_second=10) as live:
        # テストランナーの並列起動
        with ThreadPoolExecutor(max_workers=MAX_WORKER_NUM) as executor:
            futures = []
            for blender_path in blender_paths:
                f = executor.submit(run_runner, blender_path, runner_script, versions, test_files, status_matrix, live)
                futures.append(f)
            # 並列タスクの完了を待機しながらリアルタイム更新
            for future in as_completed(futures):
                failed_logs.extend(future.result())

    # エラーログ報告
    if failed_logs:
        console.print("\n[bold red][ERROR] Some tests have failed.")
        for v_name, tf, log_file_path in sorted(failed_logs):
            console.print(f"[bold red]  {v_name} -> {tf}[/]: [underline cyan]{log_file_path.resolve()}[/]")
    else:
        console.print("\n[bold green]Successfully passed all tests![/]")


if __name__ == "__main__":
    run_all_tests()
