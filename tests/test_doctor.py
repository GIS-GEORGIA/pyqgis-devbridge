"""devbridge doctor: each check in isolation (subprocess imports are faked;
the wrapper-script resolution and the overall report assembly are real).
Verified for real, once, against this repo's own QGIS installs (both an
OSGeo4W 'qgis-ltr' edition and a standalone 'qgis' edition): a bare
`python -c "import qgis.core"` on the QGIS-bundled interpreter itself fails
with "DLL load failed" even with PATH/PYTHONPATH/os.add_dll_directory set by
hand, but its own python-qgis[-ltr].bat wrapper works first try - that's why
_qgis_python_wrapper exists instead of reconstructing the environment."""
from __future__ import annotations

import json
from pathlib import Path

from devbridge import doctor
from devbridge.detectors.base import QgisInstallation


def _qgis(tmp_path: Path, edition: str = "qgis-ltr", with_wrapper: bool = True) -> QgisInstallation:
    root = tmp_path / "QGIS"
    qgis_python_dir = root / "apps" / edition / "python"
    qgis_python_dir.mkdir(parents=True)
    py = root / "apps" / "Python312" / "python.exe"
    py.parent.mkdir(parents=True)
    py.write_text("")
    if with_wrapper:
        (root / "bin").mkdir(parents=True, exist_ok=True)
        (root / "bin" / f"python-{edition}.bat").write_text("")
    return QgisInstallation(root=root, python_exe=py, qgis_python_dir=qgis_python_dir)


def test_qgis_python_wrapper_found_by_edition(tmp_path: Path):
    ltr = _qgis(tmp_path / "a", "qgis-ltr")
    assert doctor._qgis_python_wrapper(ltr) == ltr.root / "bin" / "python-qgis-ltr.bat"
    plain = _qgis(tmp_path / "b", "qgis")
    assert doctor._qgis_python_wrapper(plain) == plain.root / "bin" / "python-qgis.bat"


def test_qgis_python_wrapper_missing_is_none(tmp_path: Path):
    no_wrapper = _qgis(tmp_path, with_wrapper=False)
    assert doctor._qgis_python_wrapper(no_wrapper) is None


def test_python_can_import_prefers_the_wrapper_on_windows(tmp_path: Path, monkeypatch):
    qgis = _qgis(tmp_path)
    monkeypatch.setattr(doctor.platform, "system", lambda: "Windows")
    seen = []
    monkeypatch.setattr(doctor, "_try_import", lambda interp, mod, timeout: seen.append(interp) or True)
    assert doctor._python_can_import(qgis.python_exe, "qgis.core", qgis=qgis) is True
    assert seen == [doctor._qgis_python_wrapper(qgis)]       # not the bare python_exe


def test_python_can_import_falls_back_to_bare_exe_without_a_wrapper(tmp_path: Path, monkeypatch):
    qgis = _qgis(tmp_path, with_wrapper=False)
    monkeypatch.setattr(doctor.platform, "system", lambda: "Windows")
    seen = []
    monkeypatch.setattr(doctor, "_try_import", lambda interp, mod, timeout: seen.append(interp) or True)
    doctor._python_can_import(qgis.python_exe, "qgis.core", qgis=qgis)
    assert seen == [qgis.python_exe]


def test_python_can_import_ignores_qgis_off_windows(tmp_path: Path, monkeypatch):
    """A venv interpreter is passed with qgis=None from the call sites that
    matter (see run_checks); this just proves the wrapper logic itself
    never kicks in on Linux/macOS even if a qgis were (wrongly) passed."""
    qgis = _qgis(tmp_path)
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    seen = []
    monkeypatch.setattr(doctor, "_try_import", lambda interp, mod, timeout: seen.append(interp) or True)
    doctor._python_can_import(qgis.python_exe, "qgis.core", qgis=qgis)
    assert seen == [qgis.python_exe]


def test_port_free_true_then_false_while_bound():
    import socket
    assert doctor._port_free("localhost", 0) is True          # port 0: always bindable
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]
        s.listen(1)
        assert doctor._port_free("localhost", port) is False
    assert doctor._port_free("localhost", port) is True        # released after the socket closes


def test_vscode_attach_config_detection(tmp_path: Path):
    assert doctor._vscode_has_attach_config(tmp_path) is False        # no .vscode/ at all
    d = tmp_path / ".vscode"
    d.mkdir()
    (d / "launch.json").write_text(json.dumps({"configurations": [{"name": "something else"}]}))
    assert doctor._vscode_has_attach_config(tmp_path) is False
    (d / "launch.json").write_text(json.dumps(
        {"configurations": [{"name": "PyQGIS: Attach to running QGIS"}]}))
    assert doctor._vscode_has_attach_config(tmp_path) is True
    (d / "launch.json").write_text("not json")
    assert doctor._vscode_has_attach_config(tmp_path) is False       # malformed: treated as absent, not a crash


def test_plugin_enabled_anywhere_none_when_not_installed(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(doctor.bridge_plugin, "profile_dirs", lambda profile=None: [])
    assert doctor._plugin_enabled_anywhere() is None


def test_plugin_enabled_anywhere_false_when_installed_but_disabled(monkeypatch, tmp_path: Path):
    prof = tmp_path / "default"
    (prof / "python" / "plugins" / "DevBridge").mkdir(parents=True)
    ini = prof / "QGIS" / "QGIS3.ini"
    ini.parent.mkdir(parents=True)
    ini.write_text("[PythonPlugins]\nDevBridge=false\n", encoding="utf-8")
    monkeypatch.setattr(doctor.bridge_plugin, "profile_dirs", lambda profile=None: [prof])
    assert doctor._plugin_enabled_anywhere() is False


def test_plugin_enabled_anywhere_true_when_any_profile_has_it_on(monkeypatch, tmp_path: Path):
    off, on = tmp_path / "off", tmp_path / "on"
    for prof, enabled in ((off, "false"), (on, "true")):
        (prof / "python" / "plugins" / "DevBridge").mkdir(parents=True)
        ini = prof / "QGIS" / "QGIS3.ini"
        ini.parent.mkdir(parents=True)
        ini.write_text(f"[PythonPlugins]\nDevBridge={enabled}\n", encoding="utf-8")
    monkeypatch.setattr(doctor.bridge_plugin, "profile_dirs", lambda profile=None: [off, on])
    assert doctor._plugin_enabled_anywhere() is True


# --- the assembled report -----------------------------------------------------------------

def test_run_checks_and_print_report_all_green(monkeypatch, tmp_path: Path):
    qgis = _qgis(tmp_path)
    monkeypatch.setattr(doctor.pipeline, "find_all_qgis", lambda log=print: [qgis])
    monkeypatch.setattr(doctor, "_python_can_import", lambda *a, **k: True)
    monkeypatch.setattr(doctor, "_port_free", lambda host, port: True)
    monkeypatch.setattr(doctor, "_plugin_enabled_anywhere", lambda: True)

    checks = doctor.run_checks()
    lines: list[str] = []
    assert doctor.print_report(checks, log=lines.append) is True
    assert all("[FAIL]" not in line for line in lines)


def test_run_checks_reports_failure_and_hints(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(doctor.pipeline, "find_all_qgis", lambda log=print: [])
    checks = doctor.run_checks()
    lines: list[str] = []
    assert doctor.print_report(checks, log=lines.append) is False
    assert any("[FAIL]" in line for line in lines)
    assert any(line.strip() and not line.startswith("[") for line in lines)   # a hint line was printed too


def test_run_checks_flags_a_non_local_devbridge_json_host(monkeypatch, tmp_path: Path):
    from devbridge import project_config

    qgis = _qgis(tmp_path)
    monkeypatch.setattr(doctor.pipeline, "find_all_qgis", lambda log=print: [qgis])
    monkeypatch.setattr(doctor, "_python_can_import", lambda *a, **k: True)
    monkeypatch.setattr(doctor, "_port_free", lambda host, port: True)
    monkeypatch.setattr(doctor, "_plugin_enabled_anywhere", lambda: True)
    project_config.write_project_config(tmp_path, host="0.0.0.0", port=5678,
                                        plugin_name="p", venv_name=".venv")

    checks = doctor.run_checks(project_dir=tmp_path)
    flagged = [c for c in checks if c.label == doctor.t("doctor_host_local")]
    assert len(flagged) == 1 and flagged[0].ok is None and "0.0.0.0" in flagged[0].hint


def test_run_checks_does_not_flag_a_local_devbridge_json_host(monkeypatch, tmp_path: Path):
    from devbridge import project_config

    qgis = _qgis(tmp_path)
    monkeypatch.setattr(doctor.pipeline, "find_all_qgis", lambda log=print: [qgis])
    monkeypatch.setattr(doctor, "_python_can_import", lambda *a, **k: True)
    monkeypatch.setattr(doctor, "_port_free", lambda host, port: True)
    monkeypatch.setattr(doctor, "_plugin_enabled_anywhere", lambda: True)
    project_config.write_project_config(tmp_path, host="localhost", port=5678,
                                        plugin_name="p", venv_name=".venv")

    checks = doctor.run_checks(project_dir=tmp_path)
    assert not any(c.label == doctor.t("doctor_host_local") for c in checks)


def test_run_checks_skips_project_checks_when_no_project_dir_given(monkeypatch, tmp_path: Path):
    qgis = _qgis(tmp_path)
    monkeypatch.setattr(doctor.pipeline, "find_all_qgis", lambda log=print: [qgis])
    monkeypatch.setattr(doctor, "_python_can_import", lambda *a, **k: True)
    monkeypatch.setattr(doctor, "_port_free", lambda host, port: True)
    monkeypatch.setattr(doctor, "_plugin_enabled_anywhere", lambda: True)
    labels = [c.label for c in doctor.run_checks(project_dir=None)]
    assert not any("venv" in l or ".devbridge.json" in l or "launch.json" in l for l in labels)


# --- CLI wiring ------------------------------------------------------------------------

def test_cmd_doctor_reports_ok(monkeypatch, tmp_path: Path, capsys):
    from devbridge import cli
    import argparse

    qgis = _qgis(tmp_path)
    monkeypatch.setattr(cli.pipeline, "find_all_qgis", lambda log=print: [qgis])
    monkeypatch.setattr(doctor, "_python_can_import", lambda *a, **k: True)
    monkeypatch.setattr(doctor, "_port_free", lambda host, port: True)
    monkeypatch.setattr(doctor, "_plugin_enabled_anywhere", lambda: True)

    args = argparse.Namespace(project_dir=None, port=5678, qgis_root=None)
    assert cli.cmd_doctor(args) == 0
    assert "checked out" in capsys.readouterr().out


def test_cmd_doctor_with_bad_qgis_root_fails_cleanly(monkeypatch, tmp_path: Path, capsys):
    from devbridge import cli
    import argparse

    monkeypatch.setattr(cli.pipeline, "find_all_qgis", lambda log=print: [])
    args = argparse.Namespace(project_dir=None, port=5678, qgis_root=str(tmp_path / "nope"))
    assert cli.cmd_doctor(args) == 1
