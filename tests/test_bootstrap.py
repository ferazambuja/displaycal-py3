"""Regression coverage for the test session's native-runtime setup."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_ci_bootstrap_survives_threads_exiting(tmp_path):
    """CI diagnostics must not crash a process while its threads finish."""
    code = textwrap.dedent(
        """
        import faulthandler
        from pathlib import Path
        import runpy
        import sys
        import threading
        import time

        def unsafe_watchdog(*args, **kwargs):
            raise AssertionError("CI must not start the native traceback watchdog")

        faulthandler.dump_traceback_later = unsafe_watchdog
        sys.path.insert(0, str(Path(sys.argv[1]).parent.parent))
        bootstrap = runpy.run_path(sys.argv[1])
        assert faulthandler.is_enabled()
        dumped = threading.Event()
        original = faulthandler.dump_traceback

        def dump(**kwargs):
            original(**kwargs)
            dumped.set()

        faulthandler.dump_traceback = dump
        with open("thread-churn.log", "w") as log:
            stop = bootstrap["_start_ci_thread_dumps"](log, interval=0.005)
            try:
                for _ in range(64):
                    threads = [threading.Thread(target=lambda: time.sleep(0.0001))
                               for _ in range(4)]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join()
                assert dumped.wait(5)
            finally:
                stop()
        assert "Thread" in Path("thread-churn.log").read_text()
        """
    )
    env = os.environ.copy()
    env["GITHUB_ACTIONS"] = "true"
    result = subprocess.run(
        [sys.executable, "-c", code, str(Path(__file__).with_name("conftest.py"))],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr[-4000:]
