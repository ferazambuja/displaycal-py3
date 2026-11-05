"""Regression coverage for the test session's native-runtime setup."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


@pytest.mark.skipif(
    sys.platform != "win32" or sys.version_info[:2] != (3, 12),
    reason="CPython 3.12 Windows traceback watchdog regression",
)
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

        # Accelerate the session watchdog without changing the bootstrap's
        # decision to enable it. The old native traceback walk can fault.
        original = faulthandler.dump_traceback_later
        faulthandler.dump_traceback_later = (
            lambda timeout, **kwargs: original(0.005, **kwargs)
        )
        sys.path.insert(0, str(Path(sys.argv[1]).parent.parent))
        runpy.run_path(sys.argv[1])
        assert faulthandler.is_enabled()
        for _ in range(64):
            threads = [threading.Thread(target=lambda: time.sleep(0.0001))
                       for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        faulthandler.cancel_dump_traceback_later()
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
