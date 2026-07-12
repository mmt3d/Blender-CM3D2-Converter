import argparse
import os
import re
import subprocess
import textwrap
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import config
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table

SIGNAL_RE = re.compile(r"__TEST_([\w]+)__ (.+)$")
console = Console()


def run_runner(blender_mode: bool, v_name: str, cmd: list[str], v_names: list, tests: list,
               status_matrix: dict, live: Live):
    """
    Blenderを起動してテストランナースクリプトを実行する
    """
    # 各種パス
    test_dir = Path(__file__).parent
    runner = test_dir / "runner.py"
    log_dir = test_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    job_id = threading.get_ident()

    # Venv/Blenderモード区別してテスト環境起動
    cmd += [runner, "--", "--job-id", str(job_id), "-m", "not profile"] + tests
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore',
        cwd=test_dir
    )

    for test in tests:
        status_matrix[(v_name, test)] =  Spinner("point", text="[bold yellow]Booting[/]")
    live.update(generate_table(blender_mode, v_names, tests, status_matrix))

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
                        for test in tests:
                            status_matrix[(v_name, test)] = ""
                        is_running = True
                    if event == "START":
                        status_matrix[(v_name, current_tf)] = Spinner("dots", text="[bold cyan]Running[/]")
                    elif event == "PASS":
                        status_matrix[(v_name, current_tf)] = "[bold green]✔ Pass[/]"
                    elif event == "FAIL":
                        status_matrix[(v_name, current_tf)] = "[bold red]✘ Fail[/]"
                    elif event == "FATAL":
                        status_matrix[(v_name, current_tf)] = "[bold red]☠ Critical[/]"
                    live.update(generate_table(blender_mode, v_names, tests, status_matrix))
            else:
                other_log += line

    # 生ログを読み込みメタ情報を追記してログを保存
    return_code = process.poll()
    failed_logs = []
    for i, test in enumerate(tests):
        current_status = status_matrix[(v_name, test)]
        raw_log_path = log_dir / f"_raw_{job_id}_{i}.log"
        if raw_log_path.exists():
            with open(raw_log_path, encoding="utf-8") as f:
                content = f.read()
            status = "PASS" if "Pass" in str(current_status) else "FAIL"
            log_path = save_log(v_name, test, content, log_dir, return_code, status)
            if status == "FAIL":
                failed_logs.append((v_name, test, log_path))
            raw_log_path.unlink()
        else:
            # 生ログがない場合、致命的な強制終了が発生していると解釈、ログは作らない
            status_matrix[(v_name, test)] = "[bold red]☠ Critical[/]"
            log_path = save_log(v_name, test, other_log, log_dir, return_code, "CRITICAL")
            failed_logs.append((v_name, test, log_path))

    live.update(generate_table(blender_mode, v_names, tests, status_matrix))
    return failed_logs


def save_log(v_name: str, test: str, log: str, log_dir: Path, return_code: int | None, status: str):
    """
    ログファイル記録
    """
    log_dir.mkdir(exist_ok=True)
    safe_version = v_name.replace(" ", "_").replace(".", "_")
    safe_test = test.replace(".", "_").replace(":", "_")
    log_file_path = log_dir / f"{safe_version}_{safe_test}.log"
    with open(log_file_path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(f"""\
            Blender Version: {v_name}
            Test Script: {test}
            Process Return Code: {return_code}
            Test Status: {status}
            --------------------------------------------------
             
            """))
        f.write(log)
    return log_file_path


def generate_table(blender_mode: bool, v_names: list[str], tests: list[str], status_matrix: dict) -> Table:
    """
    richのTableオブジェクトを生成
    """
    mode = "Blender" if blender_mode else "Venv"
    table = Table(
        title=f"Blender-CM3D2-Converter Multi-Version Test Matrix\n[bold yellow]Mode: {mode}[/]",
        title_justify="left",
        title_style="bold blue",
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
    )

    # 列定義（行ヘッダーとなるテストファイル名列を追加）
    table.add_column("Test", style="dim", width=25)
    for v_name in v_names:
        table.add_column(v_name, justify="center", width=11)

    # 行データの追加
    for test in tests:
        row_cells = [test]
        for v_name in v_names:
            status = status_matrix.get((v_name, test), "[dim]-[/]")
            row_cells.append(status)
        table.add_row(*row_cells)

    return table


def run_all_tests():
    """
    全Blenderバージョン x 全テストケース を実施
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", action="store_true", help="Test by real blender application")
    parser.add_argument("--version", "-v", action="append", help="Specify version")
    parser.add_argument("tests", nargs="*", help="Specify test files")
    args = parser.parse_args()

    paths = {}
    if args.blender:
        for version in config.BLENDER_VERSIONS:
            if args.version and version not in args.version:
                continue
            path = config.BLENDER_PATH_FMT.format(version)
            if os.path.exists(path):
                paths[f"Blender {version}"] = [path, "-b", "-P"]
            else:
                console.print(f"[bold red][ERROR] Blender path not found：[/] {path}")
    else:
        for version, spec in config.BLENDER_SPEC_MAP.items():
            if args.version and version not in args.version:
                continue
            if not spec['bpy']:
                continue
            cmd = ["uv", "run", "--no-project", "--python", spec["python"]]
            if spec.get('find-links'):
                cmd += ["--find-links", spec["find-links"]]
            cmd += ["--with", "bpy==" + spec["bpy"], "--with", "pytest", "--", "python"]
            paths[f"Venv {version}"] = cmd

    v_names = list(paths.keys())
    tests = args.tests if args.tests else sorted([f.name for f in Path(__file__).parent.glob("test_*.py")])

    # ステータスの初期化（未実行は灰色のハイフン）
    status_matrix = {(v, test): "[dim]-[/]" for v in v_names for test in tests}

    # 進捗マトリックス表を動的更新
    failed_logs = []
    with Live(generate_table(args.blender, v_names, tests, status_matrix), console=console, refresh_per_second=10) as live:
        # テストランナーの並列起動
        with ThreadPoolExecutor(max_workers=config.MAX_WORKER_NUM) as executor:
            futures = []
            for v_name, cmd in paths.items():
                f = executor.submit(run_runner, args.blender, v_name, cmd, v_names, tests, status_matrix, live)
                futures.append(f)
            # 並列タスクの完了を待機しながらリアルタイム更新
            for future in as_completed(futures):
                failed_logs.extend(future.result())

    # エラーログ報告
    if failed_logs:
        console.print("\n[bold red][ERROR] Some tests have failed.[/]")
        for v_name, test, log_file_path in sorted(failed_logs):
            console.print(f"[bold red]  {v_name} -> {test}[/]: [underline cyan]{log_file_path.resolve()}[/]")
    else:
        console.print("\n[bold green]Successfully passed all tests![/]")


if __name__ == "__main__":
    run_all_tests()
