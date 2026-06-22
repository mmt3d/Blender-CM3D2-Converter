import argparse
import os
import re
import subprocess
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.spinner import Spinner
import config


SIGNAL_RE = re.compile(r"__TEST_([\w]+)__:([\w._]+)$")
console = Console()


def run_runner(blender_mode: bool, v_name: str, cmd: list[str], v_names: list, test_files: list,
               status_matrix: dict, live):
    """
    Blenderを起動してテストランナースクリプトを実行する
    """
    # 各種パス
    test_dir = Path(__file__).parent
    runner = test_dir / "runner.py"
    log_dir = test_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    raw_log_path_fmt = log_dir / f"_raw_{v_name}_{{tf_name}}.log"

    # Venv/Blenderモード区別してテスト環境起動
    cmd += [runner, "--", "--raw-log-path-fmt", raw_log_path_fmt, "-m", "not profile"]
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore',
        cwd=test_dir
    )

    for tf in test_files:
        status_matrix[(v_name, tf)] =  Spinner("point", text="[bold yellow]Booting[/]")
    live.update(generate_table(blender_mode, v_names, test_files, status_matrix))

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
                    live.update(generate_table(blender_mode, v_names, test_files, status_matrix))
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

    live.update(generate_table(blender_mode, v_names, test_files, status_matrix))
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


def generate_table(blender_mode: bool, v_names: list[str], test_files: list[str], status_matrix: dict) -> Table:
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
    table.add_column("Test File", style="dim", width=25)
    for v_name in v_names:
        table.add_column(v_name, justify="center", width=11)

    # 行データの追加
    for tf in test_files:
        row_cells = [tf]
        for v_name in v_names:
            status = status_matrix.get((v_name, tf), "[dim]-[/]")
            row_cells.append(status)
        table.add_row(*row_cells)

    return table


def run_all_tests():
    """
    全Blenderバージョン x 全テストケース を実施
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", action="store_true", help="Test by real blender application")
    args = parser.parse_args()

    paths = {}
    if args.blender:
        for version in config.BLENDER_VERSIONS:
            path = config.BLENDER_PATH_FMT.format(version)
            if os.path.exists(path):
                paths[f"Blender {version}"] = [path, "-b", "-P"]
            else:
                console.print(f"[bold red][ERROR] Blender path not found：[/] {path}")
    else:
        for version, spec in config.BLENDER_SPEC_MAP.items():
            if not spec['bpy']:
                continue
            cmd = ["uv", "run", "--no-project", "--python", spec["python"]]
            if spec.get('find-links'):
                cmd += ["--find-links", spec["find-links"]]
            cmd += ["--with", "bpy==" + spec["bpy"], "--with", "pytest", "--", "python"]
            paths[f"Venv {version}"] = cmd

    v_names = list(paths.keys())
    test_files = [p.name for p in Path(__file__).parent.glob("test_*.py")]

    # ステータスの初期化（未実行は灰色のハイフン）
    status_matrix = {(v, tf): "[dim]-[/]" for v in v_names for tf in test_files}

    # 進捗マトリックス表を動的更新
    failed_logs = []
    with Live(generate_table(args.blender, v_names, test_files, status_matrix), console=console, refresh_per_second=10) as live:
        # テストランナーの並列起動
        with ThreadPoolExecutor(max_workers=config.MAX_WORKER_NUM) as executor:
            futures = []
            for v_name, cmd in paths.items():
                f = executor.submit(run_runner, args.blender, v_name, cmd, v_names, test_files, status_matrix, live)
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
