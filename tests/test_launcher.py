"""devbridge launch: the bootstrap script, QGIS-executable resolution, and the
ready-file handshake. The bootstrap's core trick (debugpy.configure(python=...)
before listen()) was verified for real against QGIS 3.44.5 (qgis-bin.exe --code) -
see CHANGELOG 0.2.2 / qgis_plugin/debug_bridge.py's docstring; what's tested here
is everything around it (Popen and the filesystem are injectable)."""
from __future__ import annotations

import sys
import threading
import types
from pathlib import Path

from devbridge import launcher
from devbridge.detectors.base import QgisInstallation


def _qgis(tmp_path: Path, python_name="python3") -> QgisInstallation:
    py = tmp_path / python_name
    py.write_text("")
    return QgisInstallation(root=tmp_path, python_exe=py, qgis_python_dir=tmp_path / "apps" / "qgis" / "python")


class FakeProcess:
    def __init__(self, exit_code=None):
        self._code = exit_code

    def poll(self):
        return self._code


def test_bootstrap_is_valid_python_and_configures_before_listen():
    compile(launcher.BOOTSTRAP_SOURCE, "bootstrap", "exec")
    src = launcher.BOOTSTRAP_SOURCE
    assert src.index("debugpy.configure") < src.index("debugpy.listen")


def test_bootstrap_writes_ok_with_fake_debugpy(tmp_path, monkeypatch):
    calls = []
    fake = types.ModuleType("debugpy")
    fake.configure = lambda **kw: calls.append(("configure", kw))
    fake.listen = lambda addr: calls.append(("listen", addr))
    monkeypatch.setitem(sys.modules, "debugpy", fake)
    ready = tmp_path / "ready.txt"
    monkeypatch.setenv("DEVBRIDGE_READY_FILE", str(ready))
    monkeypatch.setenv("DEVBRIDGE_PORT", "6001")
    monkeypatch.setenv("DEVBRIDGE_PYTHON", "/opt/py")
    exec(compile(launcher.BOOTSTRAP_SOURCE, "bootstrap", "exec"), {})
    assert ready.read_text() == "ok"
    assert calls == [("configure", {"python": "/opt/py"}), ("listen", ("localhost", 6001))]


def test_bootstrap_reports_errors_instead_of_raising(tmp_path, monkeypatch):
    fake = types.ModuleType("debugpy")
    fake.configure = lambda **kw: None

    def boom(addr):
        raise OSError("address in use")

    fake.listen = boom
    monkeypatch.setitem(sys.modules, "debugpy", fake)
    ready = tmp_path / "ready.txt"
    monkeypatch.setenv("DEVBRIDGE_READY_FILE", str(ready))
    exec(compile(launcher.BOOTSTRAP_SOURCE, "bootstrap", "exec"), {})
    assert ready.read_text().startswith("error:")
    assert "address in use" in ready.read_text()


def test_find_executable_windows_prefers_bat_wrapper(tmp_path: Path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "qgis.bat").write_text("")
    (tmp_path / "bin" / "qgis-bin.exe").write_text("")
    q = _qgis(tmp_path)
    assert launcher.find_qgis_executable(q, system="Windows") == tmp_path / "bin" / "qgis.bat"


def test_find_executable_windows_matches_ltr_flavour(tmp_path: Path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "qgis-ltr.bat").write_text("")
    q = _qgis(tmp_path)
    q.qgis_python_dir = tmp_path / "apps" / "qgis-ltr" / "python"
    assert launcher.find_qgis_executable(q, system="Windows") == tmp_path / "bin" / "qgis-ltr.bat"


def test_find_executable_windows_falls_back_to_standalone_layout(tmp_path: Path):
    """Verified layout: <root>\\bin\\qgis-bin.exe, no flavoured wrapper at all."""
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "qgis-bin.exe").write_text("")
    q = _qgis(tmp_path)
    q.qgis_python_dir = tmp_path / "apps" / "qgis-ltr" / "python"
    assert launcher.find_qgis_executable(q, system="Windows") == tmp_path / "bin" / "qgis-bin.exe"


def test_find_executable_windows_none_when_missing(tmp_path: Path):
    assert launcher.find_qgis_executable(_qgis(tmp_path), system="Windows") is None


def test_find_executable_linux_uses_path(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda n: "/usr/bin/qgis" if n == "qgis" else None)
    assert launcher.find_qgis_executable(_qgis(tmp_path), system="Linux") == Path("/usr/bin/qgis")


def test_find_executable_macos_uses_bundle_binary(tmp_path: Path):
    (tmp_path / "MacOS").mkdir()
    (tmp_path / "MacOS" / "QGIS").write_text("")
    q = _qgis(tmp_path)           # root plays the role of <app>/Contents here
    assert launcher.find_qgis_executable(q, system="Darwin") == tmp_path / "MacOS" / "QGIS"
    (tmp_path / "MacOS" / "QGIS").unlink()
    assert launcher.find_qgis_executable(q, system="Darwin") is None


def test_real_python_for_rejects_bat_wrappers(tmp_path: Path):
    q = _qgis(tmp_path, python_name="python-qgis.bat")
    assert launcher.real_python_for(q) is None
    assert launcher.real_python_for(_qgis(tmp_path, "python.exe")) is not None


def test_build_command_and_env(tmp_path: Path):
    exe, bootstrap = Path("/usr/bin/qgis"), Path("/tmp/b.py")
    cmd = launcher.build_launch_command(exe, bootstrap, "/p/a.qgz", ["--nologo"])
    assert cmd == [str(exe), "--code", str(bootstrap), "--nologo", "/p/a.qgz"]
    env = launcher.build_launch_env(host="h", port=1234, wait_for_client=True,
                                    ready_file=tmp_path / "r", python_exe=None)
    assert env["DEVBRIDGE_PORT"] == "1234" and env["DEVBRIDGE_WAIT_FOR_CLIENT"] == "1"
    assert "DEVBRIDGE_PYTHON" not in env


def test_wait_for_ready_ok_error_timeout_exit(tmp_path: Path):
    f = tmp_path / "r"
    f.write_text("ok")
    assert launcher.wait_for_ready(f, 1) == (True, "ok")
    f.write_text("error: nope")
    assert launcher.wait_for_ready(f, 1) == (False, "error: nope")
    f.unlink()
    now = [0.0]
    ok, detail = launcher.wait_for_ready(f, 2, poll=1, sleep=lambda s: now.__setitem__(0, now[0] + s),
                                         clock=lambda: now[0])
    assert (ok, detail) == (False, "timeout")
    ok, detail = launcher.wait_for_ready(f, 5, process=FakeProcess(3), sleep=lambda s: None)
    assert (ok, detail) == (False, "exited:3")


def test_wait_for_ready_sees_file_written_later(tmp_path: Path):
    f = tmp_path / "r"
    threading.Timer(0.3, lambda: f.write_text("ok")).start()
    assert launcher.wait_for_ready(f, 5, poll=0.05) == (True, "ok")


def test_wait_for_ready_ignores_a_zero_exit_and_keeps_polling(tmp_path: Path):
    """OSGeo4W's qgis*.bat wrappers `start /B` the real exe and exit 0
    immediately - confirmed for real - while QGIS keeps loading in a
    detached grandchild. That must not be reported as a failure."""
    f = tmp_path / "r"
    threading.Timer(0.3, lambda: f.write_text("ok")).start()
    ok, detail = launcher.wait_for_ready(f, 5, poll=0.05, process=FakeProcess(0))
    assert (ok, detail) == (True, "ok")


def test_wait_for_ready_still_fails_fast_on_a_real_crash(tmp_path: Path):
    f = tmp_path / "r"       # never written
    ok, detail = launcher.wait_for_ready(f, 5, poll=0.05, process=FakeProcess(1))
    assert (ok, detail) == (False, "exited:1")


def test_launch_qgis_end_to_end_with_fake_popen(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda n: "/usr/bin/qgis" if n == "qgis" else None)
    seen = {}

    def fake_popen(cmd, **kwargs):
        seen["cmd"], seen["kwargs"] = cmd, kwargs
        Path(kwargs["env"]["DEVBRIDGE_READY_FILE"]).write_text("ok")   # what the bootstrap would do
        return FakeProcess()

    msgs = []
    rc = launcher.launch_qgis(_qgis(tmp_path), host="localhost", port=5999, wait_ready=True,
                              timeout=5, popen=fake_popen, work_dir=tmp_path / "w",
                              verbose_print=msgs.append, system="Linux")
    assert rc == 0
    assert seen["cmd"][:2] == [str(Path("/usr/bin/qgis")), "--code"]
    assert seen["kwargs"]["env"]["DEVBRIDGE_PORT"] == "5999"
    assert seen["kwargs"]["env"]["DEVBRIDGE_PYTHON"].endswith("python3")
    assert seen["kwargs"]["stdout"] is not None          # detached: no inherited pipes
    assert not list((tmp_path / "w").glob("ready-*.txt"))  # cleaned up


def test_launch_qgis_reports_bridge_error(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda n: "/usr/bin/qgis" if n == "qgis" else None)

    def fake_popen(cmd, **kwargs):
        Path(kwargs["env"]["DEVBRIDGE_READY_FILE"]).write_text("error: port busy")
        return FakeProcess()

    msgs = []
    rc = launcher.launch_qgis(_qgis(tmp_path), wait_ready=True, popen=fake_popen,
                              work_dir=tmp_path / "w", verbose_print=msgs.append, system="Linux")
    assert rc == 1 and any("port busy" in m for m in msgs)


def test_launch_qgis_without_executable_fails_cleanly(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda n: None)
    monkeypatch.setattr(launcher.Path, "is_file", lambda self: False)
    msgs = []
    assert launcher.launch_qgis(_qgis(tmp_path), verbose_print=msgs.append, system="Linux") == 1
    assert msgs


def test_launch_qgis_warns_but_still_launches_when_port_busy(tmp_path: Path, monkeypatch):
    """A busy port (typically a still-running earlier QGIS session) should
    not block launching a new one - just warn, since the user may want to
    attach to the already-running bridge instead."""
    monkeypatch.setattr(launcher.shutil, "which", lambda n: "/usr/bin/qgis" if n == "qgis" else None)
    monkeypatch.setattr(launcher, "port_free", lambda host, port: False)

    def fake_popen(cmd, **kwargs):
        Path(kwargs["env"]["DEVBRIDGE_READY_FILE"]).write_text("ok")
        return FakeProcess()

    msgs = []
    rc = launcher.launch_qgis(_qgis(tmp_path), host="localhost", port=5999, wait_ready=True,
                              timeout=5, popen=fake_popen, work_dir=tmp_path / "w",
                              verbose_print=msgs.append, system="Linux")
    assert rc == 0
    assert any("5999" in m for m in msgs)


def test_launch_qgis_warns_about_a_non_local_host(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda n: "/usr/bin/qgis" if n == "qgis" else None)

    def fake_popen(cmd, **kwargs):
        Path(kwargs["env"]["DEVBRIDGE_READY_FILE"]).write_text("ok")
        return FakeProcess()

    msgs = []
    launcher.launch_qgis(_qgis(tmp_path), host="0.0.0.0", port=5999, wait_ready=True, timeout=5,
                         popen=fake_popen, work_dir=tmp_path / "w", verbose_print=msgs.append, system="Linux")
    assert any("0.0.0.0" in m for m in msgs)


def test_launch_qgis_does_not_warn_about_localhost(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda n: "/usr/bin/qgis" if n == "qgis" else None)

    def fake_popen(cmd, **kwargs):
        Path(kwargs["env"]["DEVBRIDGE_READY_FILE"]).write_text("ok")
        return FakeProcess()

    msgs = []
    launcher.launch_qgis(_qgis(tmp_path), host="localhost", port=5999, wait_ready=True, timeout=5,
                         popen=fake_popen, work_dir=tmp_path / "w", verbose_print=msgs.append, system="Linux")
    assert not any("not local" in m for m in msgs)
