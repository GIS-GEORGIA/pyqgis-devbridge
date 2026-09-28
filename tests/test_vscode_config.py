"""VS Code config: merge (not overwrite), pathMappings, the launch task, and
.devbridge.json. Before this, `devbridge setup` overwrote settings.json and
launch.json wholesale on every run, destroying anything the user had added -
a real bug, not a hypothetical one."""
from __future__ import annotations

import json
from pathlib import Path

from devbridge import project_config, vscode_config as vc


def _write(tmp_path, **kw):
    venv = tmp_path / ".venv"
    vc.write_vscode_config(tmp_path, venv, verbose_print=lambda *_: None, **kw)
    d = tmp_path / ".vscode"
    return (json.loads((d / "settings.json").read_text()),
            json.loads((d / "launch.json").read_text()),
            json.loads((d / "tasks.json").read_text()))


def test_fresh_write_creates_all_three_files(tmp_path: Path):
    settings, launch, tasks = _write(tmp_path, port=5700, host="127.0.0.1", lang="ka",
                                     devbridge_python="/py/python")
    names = [c["name"] for c in launch["configurations"]]
    assert names == [vc.ATTACH_NAME, vc.LAUNCH_NAME]
    assert launch["configurations"][0]["connect"] == {"host": "127.0.0.1", "port": 5700}
    assert launch["configurations"][1]["preLaunchTask"] == vc.TASK_LABEL
    task = tasks["tasks"][0]
    assert task["label"] == vc.TASK_LABEL and task["command"] == "/py/python"
    assert task["args"][:4] == ["-m", "devbridge", "--lang", "ka"]
    assert "launch" in task["args"] and "${workspaceFolder}" in task["args"]
    assert "python.defaultInterpreterPath" in settings


def test_existing_user_entries_are_kept_and_ours_are_not_duplicated(tmp_path: Path):
    d = tmp_path / ".vscode"
    d.mkdir()
    (d / "settings.json").write_text(json.dumps({"editor.tabSize": 2}))
    (d / "launch.json").write_text(json.dumps(
        {"version": "0.2.0", "configurations": [{"name": "mine", "type": "python", "request": "launch"}]}))
    (d / "tasks.json").write_text(json.dumps(
        {"version": "2.0.0", "tasks": [{"label": "build", "type": "shell", "command": "make"}]}))
    _write(tmp_path)
    settings, launch, tasks = _write(tmp_path)     # second run must be idempotent
    assert settings["editor.tabSize"] == 2
    assert [c["name"] for c in launch["configurations"]] == ["mine", vc.ATTACH_NAME, vc.LAUNCH_NAME]
    assert [t["label"] for t in tasks["tasks"]] == ["build", vc.TASK_LABEL]


def test_jsonc_file_is_not_modified_and_suggestion_is_written(tmp_path: Path):
    d = tmp_path / ".vscode"
    d.mkdir()
    original = '{\n  // my comment\n  "editor.tabSize": 2\n}\n'
    (d / "settings.json").write_text(original)
    msgs = []
    vc.write_vscode_config(tmp_path, tmp_path / ".venv", verbose_print=msgs.append)
    assert (d / "settings.json").read_text() == original
    suggested = json.loads((d / "settings.devbridge-suggested.json").read_text())
    assert "python.defaultInterpreterPath" in suggested
    assert any("settings.json" in m for m in msgs)
    assert (d / "launch.json").exists()             # the other files are still written


def test_path_mappings_only_with_plugin_name(tmp_path: Path, monkeypatch):
    _, launch, _ = _write(tmp_path)
    assert "pathMappings" not in launch["configurations"][0]
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr("platform.system", lambda: "Linux")
    _, launch, _ = _write(tmp_path, plugin_name="my_plugin")
    m = launch["configurations"][0]["pathMappings"][0]
    assert m["localRoot"] == "${workspaceFolder}"
    assert Path(m["remoteRoot"]).parts[-4:] == ("default", "python", "plugins", "my_plugin")


def test_plugin_name_is_inferred_from_a_profile_layout(tmp_path: Path):
    project = tmp_path / "python" / "plugins" / "my_plugin"
    project.mkdir(parents=True)
    assert vc.infer_plugin_name(project) == "my_plugin"
    assert vc.infer_plugin_name(tmp_path / "elsewhere" / "my_plugin") is None

    _, launch, _ = _write(project)
    assert "pathMappings" in launch["configurations"][0]      # inferred, no --plugin-name needed


def test_explicit_plugin_name_wins_over_inference(tmp_path: Path):
    project = tmp_path / "python" / "plugins" / "my_plugin"
    project.mkdir(parents=True)
    _, launch, _ = _write(project, plugin_name="other_name")
    assert launch["configurations"][0]["pathMappings"][0]["remoteRoot"].endswith("other_name")


def test_project_config_roundtrip_and_fallbacks(tmp_path: Path):
    assert project_config.read_project_config(tmp_path)["port"] == 5678
    project_config.write_project_config(tmp_path, host="h", port=6001, plugin_name="p", venv_name=".v")
    cfg = project_config.read_project_config(tmp_path)
    assert (cfg["host"], cfg["port"], cfg["pluginName"], cfg["venvName"]) == ("h", 6001, "p", ".v")
    (tmp_path / ".devbridge.json").write_text('{"port": "abc", "host": ""}')
    cfg = project_config.read_project_config(tmp_path)
    assert cfg["port"] == 5678 and cfg["host"] == "localhost"
    (tmp_path / ".devbridge.json").write_text("not json")
    assert project_config.read_project_config(tmp_path)["port"] == 5678
