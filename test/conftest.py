import sys
import pytest

_test_name = None
_result = None


def send_event(event: str):
    """
    run_all_test.py 向けの進捗報告用標準出力
    """
    sys.__stdout__.write(f"__TEST_{event}__ {_test_name}\n")
    sys.__stdout__.flush()


def pytest_sessionstart(session):
    """
    run_all_test.py 向けの進捗報告用フック
    全テストの最初に1回呼ばれる
    """
    global _test_name, _result
    _result = None
    _test_name = session.config.args[0]
    send_event("START")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    run_all_test.py 向けの進捗報告用フック
    テストの各フェーズ（setup, call, teardown）の成否を監視
    """
    global _result
    outcome = yield
    report = outcome.get_result()
    if _result == "FATAL":
        return
    if report.failed:
        _result = "FAIL"


def pytest_collectreport(report):
    """
    run_all_test.py 向けの進捗報告用フック
    SyntaxError, ImportError などが発生し、テストが全く実施されない場合に呼ばれる
    """
    global _result
    if report.failed:
        _result = "FATAL"
        send_event("FATAL")


def pytest_exception_interact(node, call, report):
    """
    run_all_test.py 向けの進捗報告用フック
    未キャッチ例外が発生したときに呼ばれる（テストは続行する）
    """
    global _result
    _result = "FAIL"


def pytest_sessionfinish(session, exitstatus):
    """
    run_all_test.py 向けの進捗報告用フック
    すべてのテストが終了した最後に呼ばれる
    """
    send_event(_result or "PASS")


def pytest_configure(config):
    """
    カスタムマーカーの事前定義
    """
    config.addinivalue_line(
        "markers", "profile: marker for profiling test"
    )
