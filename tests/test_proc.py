"""run_logged streaming/exit handling and the pip --user fallback."""
from __future__ import annotations

import sys

import pytest

from devbridge import debugpy_installer, proc


def test_run_logged_streams_lines_and_returns_output():
    seen: list[str] = []
    out = proc.run_logged([sys.executable, "-c", "print('a'); print('b')"], seen.append)
    assert seen == ["a", "b"] and out == "a\nb"


def test_run_logged_raises_with_tail_on_failure():
    with pytest.raises(proc.CommandError) as info:
        proc.run_logged([sys.executable, "-c", "import sys; print('boom'); sys.exit(3)"], lambda _l: None)
    assert info.value.code == 3 and "boom" in str(info.value)


def test_pip_falls_back_to_user_install_when_not_writable(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, log=print, env=None):
        calls.append(list(cmd))
        if "--user" not in cmd:
            raise proc.CommandError(cmd, 1, "ERROR: [WinError 5] Access is denied: 'C:\\Program Files\\QGIS'")
        return ""

    monkeypatch.setattr(debugpy_installer, "run_logged", fake_run)
    debugpy_installer._pip_install("python", lambda _m: None)
    assert "--user" not in calls[0] and "--user" in calls[1] and calls[1][-1] == "debugpy"


def test_pip_does_not_swallow_other_errors(monkeypatch):
    def fake_run(cmd, log=print, env=None):
        raise proc.CommandError(cmd, 1, "ERROR: No matching distribution found for debugpy")

    monkeypatch.setattr(debugpy_installer, "run_logged", fake_run)
    with pytest.raises(proc.CommandError):
        debugpy_installer._pip_install("python", lambda _m: None)
