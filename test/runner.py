import argparse
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


def ensure_pytest():
    """
    (実Blender環境向け) pytestが利用可能か確認し、なければ自動インストールして返す
    """
    import site
    user_site = site.getusersitepackages()
    if user_site not in sys.path:
        sys.path.append(user_site)

    try:
        import pytest
    except ImportError:
        import importlib
        import subprocess
        print("pytest is not found. Installing pytest...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pytest", "--user"])
        importlib.invalidate_caches()
        import pytest
        print("Successfully installed pytest.")
        
    return pytest


def main():
    pytest = ensure_pytest()

    # 引数のパース
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Common Pytest Executor")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("-m", "--marker", type=str, default="", help="pytest marker expression")
    parser.add_argument("tests", nargs="*", help="Specify test files")
    args = parser.parse_args(argv)

    # テストディレクトリのパス強制追加
    test_dir = Path(__file__).parent
    if str(test_dir) not in sys.path:
        sys.path.append(str(test_dir))
    log_dir = test_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    # テストファイルごとに pytest プロセスを変えて実行（ログを分離する用）
    all_success = True
    for i, test in enumerate(args.tests):
        raw_log_path = log_dir / f"_raw_{args.job_id}_{i}.log"
        with open(raw_log_path, "w", encoding="utf-8") as f, redirect_stdout(f), redirect_stderr(f):
            pytest_args = ["-v", "--capture=no", test]
            if args.marker:
                pytest_args.extend(["-m", args.marker])

            exit_code = pytest.main(pytest_args)

            if exit_code not in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
                all_success = False

    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    main()
