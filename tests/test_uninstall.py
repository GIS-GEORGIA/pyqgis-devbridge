"""devbridge uninstall: undoing install-plugin/link-plugin (the QGIS-profile
side) and one project's `setup` (the .venv/.devbridge.json/.vscode side)."""
from __future__ import annotations

import json
from pathlib import Path

from devbridge import bridge_plugin, project_config, uninstall, vscode_config


def _profile_with_plugin(tmp_path: Path, name: str = "DevBridge") -> Path:
    prof = tmp_path / "default"
    (prof / "python" / "plugins" / name).mkdir(parents=True)
    (prof / "python" / "plugins" / name / "__init__.py").write_text("")
    ini = prof / "QGIS" / "QGIS3.ini"
    ini.parent.mkdir(parents=True)
    ini.write_text(f"[PythonPlugins]\n{name}=true\n", encoding="utf-8")
    return prof


# --- uninstall_plugin --------------------------------------------------------------------------

def test_uninstall_plugin_removes_and_disables(tmp_path: Path, monkeypatch):
    prof = _profile_with_plugin(tmp_path)
    monkeypatch.setattr(uninstall.bridge_plugin.profiles, "profile_roots", lambda: [tmp_path])
    monkeypatch.setattr(uninstall.bridge_plugin, "qgis_running", lambda: False)

    logs = []
    assert uninstall.uninstall_plugin(log=logs.append) == 0
    assert not (prof / "python" / "plugins" / "DevBridge").exists()
    assert bridge_plugin.is_plugin_enabled(prof / "QGIS" / "QGIS3.ini") is False
    assert logs


def test_uninstall_plugin_can_target_another_name(tmp_path: Path, monkeypatch):
    prof = _profile_with_plugin(tmp_path, name="my_plugin")
    monkeypatch.setattr(uninstall.bridge_plugin.profiles, "profile_roots", lambda: [tmp_path])
    monkeypatch.setattr(uninstall.bridge_plugin, "qgis_running", lambda: False)

    assert uninstall.uninstall_plugin(name="my_plugin") == 0
    assert not (prof / "python" / "plugins" / "my_plugin").exists()


def test_uninstall_plugin_skips_while_qgis_running(tmp_path: Path, monkeypatch):
    prof = _profile_with_plugin(tmp_path)
    monkeypatch.setattr(uninstall.bridge_plugin.profiles, "profile_roots", lambda: [tmp_path])
    monkeypatch.setattr(uninstall.bridge_plugin, "qgis_running", lambda: True)

    assert uninstall.uninstall_plugin() == 1
    assert (prof / "python" / "plugins" / "DevBridge").exists()


def test_uninstall_plugin_reports_when_not_installed(tmp_path: Path, monkeypatch):
    (tmp_path / "default").mkdir(parents=True)
    monkeypatch.setattr(uninstall.bridge_plugin.profiles, "profile_roots", lambda: [tmp_path])
    logs = []
    assert uninstall.uninstall_plugin(log=logs.append) == 0
    assert logs


def test_uninstall_plugin_no_profile_found(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(uninstall.bridge_plugin.profiles, "profile_roots", lambda: [tmp_path / "nowhere"])
    assert uninstall.uninstall_plugin() == 1


# --- uninstall_project -------------------------------------------------------------------------

def test_uninstall_project_removes_venv_config_and_pycharm_debug(tmp_path: Path):
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    project_config.write_project_config(tmp_path, host="localhost", port=5678,
                                        plugin_name="p", venv_name=".venv")
    (tmp_path / ".pycharm-debug").mkdir()
    (tmp_path / ".pycharm-debug" / "README.en.md").write_text("x")

    logs = []
    assert uninstall.uninstall_project(tmp_path, log=logs.append) == 0
    assert not (tmp_path / ".venv").exists()
    assert not (tmp_path / project_config.CONFIG_NAME).exists()
    assert not (tmp_path / ".pycharm-debug").exists()
    assert logs


def test_uninstall_project_is_a_no_op_when_nothing_is_there(tmp_path: Path):
    assert uninstall.uninstall_project(tmp_path, log=lambda _m: None) == 0


def test_uninstall_project_cleans_only_our_vscode_entries(tmp_path: Path):
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    launch = {
        "version": "0.2.0",
        "configurations": [
            {"name": vscode_config.ATTACH_NAME},
            {"name": vscode_config.LAUNCH_NAME},
            {"name": "My own debug config"},
        ],
    }
    tasks = {
        "version": "2.0.0",
        "tasks": [
            {"label": vscode_config.TASK_LABEL},
            {"label": "My own task"},
        ],
    }
    (vscode_dir / "launch.json").write_text(json.dumps(launch), encoding="utf-8")
    (vscode_dir / "tasks.json").write_text(json.dumps(tasks), encoding="utf-8")

    uninstall.uninstall_project(tmp_path, log=lambda _m: None)

    left_launch = json.loads((vscode_dir / "launch.json").read_text(encoding="utf-8"))
    assert [c["name"] for c in left_launch["configurations"]] == ["My own debug config"]
    left_tasks = json.loads((vscode_dir / "tasks.json").read_text(encoding="utf-8"))
    assert [t["label"] for t in left_tasks["tasks"]] == ["My own task"]


def test_uninstall_project_leaves_malformed_vscode_files_untouched(tmp_path: Path):
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    (vscode_dir / "launch.json").write_text("not json", encoding="utf-8")
    uninstall.uninstall_project(tmp_path, log=lambda _m: None)
    assert (vscode_dir / "launch.json").read_text(encoding="utf-8") == "not json"
