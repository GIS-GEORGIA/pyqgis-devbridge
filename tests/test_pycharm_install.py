"""PyCharm bridge: finding the right Python, installing into our own folder, and the
prepare()/connect() split — all without a real PyCharm, QGIS or network."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import types
from pathlib import Path

import pytest

from qgis_plugin import pycharm_bridge as pb
from qgis_plugin import pyexe

INSTALLATION = pb.PyCharmInstallation(Path("/opt/pycharm"), "233.13135.95", "PY", "PyCharm 2023.3.2 (Professional)")


def test_find_python_skips_the_qgis_program_and_uses_the_prefix(monkeypatch, tmp_path: Path):
    """Inside QGIS sys.executable is qgis-bin.exe / the qgis binary, not Python."""
    fake_qgis = tmp_path / "bin" / "qgis-bin.exe"
    monkeypatch.setattr(sys, "executable", str(fake_qgis))      # does not even exist
    found = Path(pb.find_python_executable())
    assert found != fake_qgis and found.name.lower().startswith("python")
    out = subprocess.run([str(found), "-c", "import sys;print(sys.version_info[:2])"],
                         capture_output=True, text=True)
    assert out.stdout.strip() == str(sys.version_info[:2])


def test_find_python_reports_when_nothing_matches(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "qgis"))
    monkeypatch.setattr(sys, "_base_executable", str(tmp_path / "qgis"), raising=False)
    monkeypatch.setattr(sys, "exec_prefix", str(tmp_path / "nowhere"))
    monkeypatch.setattr(sys, "base_exec_prefix", str(tmp_path / "nowhere"))
    monkeypatch.setattr(pyexe.shutil, "which", lambda _n: None)
    with pytest.raises(pyexe.PythonNotFoundError):
        pb.find_python_executable()


class _FakePopen:
    def __init__(self, lines, code):
        self.stdout = iter(l + "\n" for l in lines)
        self._code = code

    def wait(self):
        return self._code


def test_install_uses_target_dir_streams_output_and_clears_old_version(monkeypatch, tmp_path: Path):
    target = tmp_path / "pydevd"
    (target / "pydevd_pycharm-1.0.dist-info").mkdir(parents=True)        # leftover from an older build
    seen_cmd: list[str] = []

    def fake_popen(cmd, **kwargs):
        seen_cmd.extend(cmd)
        return _FakePopen(["Collecting pydevd-pycharm", "Successfully installed pydevd-pycharm-233.13135.95"], 0)

    monkeypatch.setattr(pb.subprocess, "Popen", fake_popen)
    log: list[str] = []
    pb.install_pydevd_pycharm("python", "233.13135.95", target, log.append)

    assert "--target" in seen_cmd and str(target) in seen_cmd and "pydevd-pycharm==233.13135.95" in seen_cmd
    assert "--user" not in seen_cmd
    assert any("Successfully installed" in line for line in log)
    assert not (target / "pydevd_pycharm-1.0.dist-info").exists()


def test_install_failure_becomes_a_bridge_error_with_the_reason(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pb.subprocess, "Popen", lambda cmd, **kw: _FakePopen(
        ["WARNING: Retrying", "ERROR: No matching distribution found for pydevd-pycharm==9"], 1))
    with pytest.raises(pb.PyCharmBridgeError) as info:
        pb.install_pydevd_pycharm("python", "9", tmp_path / "t", lambda _l: None)
    assert str(info.value).startswith("pip_failed") and "No matching distribution" in str(info.value)


def test_installed_version_is_read_from_our_folder(tmp_path: Path):
    (tmp_path / "pydevd_pycharm-233.13135.95.dist-info").mkdir()
    assert pb._installed_pydevd_version(tmp_path) == "233.13135.95"


def _bridge(tmp_path: Path) -> pb.PyCharmBridge:
    return pb.PyCharmBridge(install_dir=tmp_path / "pydevd")


def test_prepare_installs_only_when_needed(monkeypatch, tmp_path: Path):
    installs: list[str] = []
    monkeypatch.setattr(pb, "find_pycharm_installations", lambda: [INSTALLATION])
    monkeypatch.setattr(pb, "resolve_pydevd_version", lambda build: "233.13135.95")
    monkeypatch.setattr(pb, "find_python_executable", lambda: "python")
    monkeypatch.setattr(pb, "install_pydevd_pycharm",
                        lambda py, ver, target, log=print: installs.append(ver))
    monkeypatch.setattr(pb, "_installed_pydevd_version", lambda target=None: None)

    bridge = _bridge(tmp_path)
    assert bridge.prepare(lambda _l: None) is INSTALLATION
    assert installs == ["233.13135.95"]
    assert str(bridge.install_dir) in sys.path

    monkeypatch.setattr(pb, "_installed_pydevd_version", lambda target=None: "233.13135.95")
    bridge.prepare(lambda _l: None)
    assert installs == ["233.13135.95"]            # already there: no second install


def test_prepare_reports_missing_pycharm(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pb, "find_pycharm_installations", lambda: [])
    with pytest.raises(pb.PyCharmBridgeError) as info:
        _bridge(tmp_path).prepare()
    assert str(info.value) == "not_found"


def test_connect_success_and_refused(monkeypatch, tmp_path: Path):
    with socket.socket() as probe:                     # a port nobody listens on
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    calls: list[tuple] = []
    fake = types.ModuleType("pydevd_pycharm")
    fake.settrace = lambda host, **kw: calls.append((host, kw["port"]))
    monkeypatch.setitem(sys.modules, "pydevd_pycharm", fake)

    with socket.socket() as server:                    # stands in for PyCharm's debug server
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        bridge = pb.PyCharmBridge("127.0.0.1", port, install_dir=tmp_path)
        bridge.connect(INSTALLATION)
        assert calls == [("127.0.0.1", port)] and bridge.is_running and bridge.installation is INSTALLATION
        with pytest.raises(pb.PyCharmBridgeError) as info:
            bridge.connect(INSTALLATION)
        assert str(info.value) == "already_running"
    calls.clear()

    def refuse(*a, **k):
        raise ConnectionRefusedError()

    fake.settrace = refuse
    fake.stoptrace = lambda: calls.append(("stoptrace",))
    other = pb.PyCharmBridge(port=free_port, install_dir=tmp_path)
    with pytest.raises(pb.PyCharmBridgeError) as info:                 # nobody listens: never reaches settrace
        other.connect(INSTALLATION)
    assert str(info.value) == "connection_refused" and not other.is_running and calls == []

    with socket.socket() as server:                                    # something listens, but settrace fails
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        listening = pb.PyCharmBridge("127.0.0.1", server.getsockname()[1], install_dir=tmp_path)
        with pytest.raises(pb.PyCharmBridgeError) as info:
            listening.connect(INSTALLATION)
        assert str(info.value) == "connection_refused" and ("stoptrace",) in calls   # hooks were undone


def test_attach_script_can_find_the_installed_package(tmp_path: Path):
    script = pb.generate_bridge_script(INSTALLATION, "localhost", 12345, install_dir=tmp_path / "pydevd")
    compile(script, "pycharm_attach.py", "exec")                   # valid Python
    assert f'sys.path.insert(0, r"{tmp_path / "pydevd"}")' in script
    assert "sys.path" not in pb.generate_bridge_script(INSTALLATION, "localhost", 12345)


# --- translations stay in step ------------------------------------------------------------

@pytest.mark.parametrize("folder", ["qgis_plugin/i18n", "src/devbridge/i18n"])
def test_en_and_ka_have_the_same_keys_and_no_empty_values(folder: str):
    en = json.loads(Path(folder, "en.json").read_text(encoding="utf-8"))
    ka = json.loads(Path(folder, "ka.json").read_text(encoding="utf-8"))
    assert set(en) == set(ka), (sorted(set(en) ^ set(ka)))
    assert all(v.strip() for v in list(en.values()) + list(ka.values()))


# --- one debugger per QGIS session ---------------------------------------------------------

from qgis_plugin import debug_bridge, debugger_state  # noqa: E402


def _fake_pydevd(monkeypatch, origin: str | None):
    if origin is None:
        monkeypatch.delitem(sys.modules, "_pydevd_bundle", raising=False)
        monkeypatch.delitem(sys.modules, "pydevd_pycharm", raising=False)
    else:
        module = types.ModuleType("_pydevd_bundle")
        module.__file__ = origin
        monkeypatch.setitem(sys.modules, "_pydevd_bundle", module)


def test_active_backend_tells_the_two_pydevd_copies_apart(monkeypatch):
    _fake_pydevd(monkeypatch, None)
    assert debugger_state.active_backend() is None
    _fake_pydevd(monkeypatch, "C:/Users/k/AppData/Roaming/Python/site-packages/debugpy/_vendored/pydevd/_pydevd_bundle/__init__.py")
    assert debugger_state.active_backend() == "debugpy"
    _fake_pydevd(monkeypatch, "/home/k/.config/devbridge/pydevd/_pydevd_bundle/__init__.py")
    assert debugger_state.active_backend() == "pycharm"


def test_vscode_bridge_refuses_when_pycharm_pydevd_is_loaded(monkeypatch):
    _fake_pydevd(monkeypatch, "/x/devbridge/pydevd/_pydevd_bundle/__init__.py")
    with pytest.raises(debug_bridge.DebugBridgeError) as info:
        debug_bridge.DebugBridge().start()
    assert str(info.value) == "other_debugger_loaded"


def test_pycharm_bridge_refuses_when_debugpy_is_loaded(monkeypatch, tmp_path: Path):
    _fake_pydevd(monkeypatch, "/x/site-packages/debugpy/_vendored/pydevd/_pydevd_bundle/__init__.py")
    bridge = pb.PyCharmBridge(install_dir=tmp_path)
    for call in (lambda: bridge.prepare(), lambda: bridge.connect(INSTALLATION)):
        with pytest.raises(pb.PyCharmBridgeError) as info:
            call()
        assert str(info.value) == "other_debugger_loaded"


def test_debugpy_import_error_on_listen_becomes_a_conflict_error(monkeypatch):
    _fake_pydevd(monkeypatch, None)
    fake = types.ModuleType("debugpy")

    def listen(_addr):
        raise ImportError("cannot import name 'pydevd_defaults'")

    fake.listen = listen
    fake.configure = lambda **kw: None
    monkeypatch.setitem(sys.modules, "debugpy", fake)
    with pytest.raises(debug_bridge.DebugBridgeError) as info:
        debug_bridge.DebugBridge().start()
    assert str(info.value) == "other_debugger_loaded"


def test_debug_bridge_configures_debugpy_with_the_real_python(monkeypatch, tmp_path: Path):
    """The bug that actually broke the shipped VS Code bridge: without
    debugpy.configure(python=...), listen() spawns its adapter through
    sys.executable, which inside QGIS is the QGIS program itself."""
    _fake_pydevd(monkeypatch, None)
    calls: list = []
    fake = types.ModuleType("debugpy")
    fake.configure = lambda **kw: calls.append(("configure", kw))
    fake.listen = lambda addr: calls.append(("listen", addr))
    monkeypatch.setitem(sys.modules, "debugpy", fake)
    fake_python = str(tmp_path / "python.exe")
    monkeypatch.setattr(debug_bridge, "find_python_executable", lambda: fake_python)

    bridge = debug_bridge.DebugBridge("localhost", 5999)
    bridge.start()
    assert calls == [("configure", {"python": fake_python}), ("listen", ("localhost", 5999))]
    assert bridge.is_running


def test_debug_bridge_reports_when_no_python_is_found(monkeypatch):
    _fake_pydevd(monkeypatch, None)
    fake = types.ModuleType("debugpy")
    fake.configure = lambda **kw: None
    monkeypatch.setitem(sys.modules, "debugpy", fake)
    monkeypatch.setattr(debug_bridge, "find_python_executable",
                        lambda: (_ for _ in ()).throw(pyexe.PythonNotFoundError()))
    with pytest.raises(debug_bridge.DebugBridgeError) as info:
        debug_bridge.DebugBridge().start()
    assert str(info.value) == "python_not_found"
    assert not debug_bridge.DebugBridge().is_running


def test_debug_bridge_survives_a_second_listen_after_reload(monkeypatch):
    """Documented debugpy behaviour (one listener per process), not
    reproduced with a real plugin reload in this session."""
    _fake_pydevd(monkeypatch, None)
    fake = types.ModuleType("debugpy")
    fake.configure = lambda **kw: None

    def listen(_addr):
        raise RuntimeError("Listen has been called more than once")

    fake.listen = listen
    monkeypatch.setitem(sys.modules, "debugpy", fake)
    bridge = debug_bridge.DebugBridge()
    with pytest.raises(debug_bridge.DebugBridgeError) as info:
        bridge.start()
    assert str(info.value) == "already_running" and bridge.is_running
