"""Write/merge the .vscode/ files:

  settings.json  interpreter for autocomplete of qgis / PyQt
  launch.json    "Attach to running QGIS" and "Launch QGIS + attach"
  tasks.json     the preLaunchTask that starts QGIS with the bridge
                 (backs "Launch QGIS + attach"; see launcher.py)

Existing files are MERGED: our entries are upserted by name/label, the
user's own other entries and settings are kept. A file that fails to
parse as strict JSON (VS Code itself tolerates comments there, we don't)
is left untouched; what we would have written goes to a sibling
*.devbridge-suggested.json instead, so nothing is silently overwritten.
"""
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import Callable

from .i18n_util import t
from .paths import qgis_user_plugins_dir

DEFAULT_PORT = 5678
ATTACH_NAME = "PyQGIS: Attach to running QGIS"
LAUNCH_NAME = "PyQGIS: Launch QGIS + attach"
HEADLESS_NAME = "PyQGIS: Debug current file (no QGIS)"
TASK_LABEL = "devbridge: launch QGIS (debug)"


def _dump(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _upsert(items: list, key: str, value: dict) -> None:
    for i, item in enumerate(items):
        if isinstance(item, dict) and item.get(key) == value[key]:
            items[i] = value
            return
    items.append(value)


def _merge_json(path: Path, update: Callable[[dict], dict], verbose_print) -> None:
    existing: dict = {}
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if text.strip():
            try:
                existing = json.loads(text)
                if not isinstance(existing, dict):
                    raise ValueError("top-level value is not an object")
            except ValueError:
                suggested = path.with_name(f"{path.stem}.devbridge-suggested.json")
                suggested.write_text(_dump(update({})), encoding="utf-8")
                verbose_print(t("vscode_file_unparsable", path=path, suggested=suggested))
                return
    path.write_text(_dump(update(existing)), encoding="utf-8")


def _venv_interpreter(venv_path: Path) -> Path:
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def infer_plugin_name(project_dir: Path) -> str | None:
    """When `project_dir` is `<profile>/python/plugins/<name>` (the usual case
    for a plugin taken from the QGIS profile, or a freshly scaffolded one),
    the plugin name is already known - no need to ask for it separately."""
    project_dir = Path(project_dir)
    if project_dir.parent.name == "plugins" and project_dir.parent.parent.name == "python":
        return project_dir.name
    return None


def build_path_mappings(plugin_name: str | None, profile: str = "default") -> list[dict]:
    """QGIS imports a plugin from <profile>/python/plugins/<name>. When the
    workspace is a checkout elsewhere (symlinked or copied in), frames report
    the profile path, so breakpoints set on the workspace files never match
    unless the two roots are mapped."""
    if not plugin_name:
        return []
    remote = qgis_user_plugins_dir(profile) / plugin_name
    return [{"localRoot": "${workspaceFolder}", "remoteRoot": str(remote)}]


def build_launch_configurations(host: str, port: int, plugin_name: str | None,
                                profile: str = "default") -> list[dict]:
    base = {
        "type": "debugpy",
        "request": "attach",
        "connect": {"host": host, "port": port},
        "justMyCode": False,
    }
    mappings = build_path_mappings(plugin_name, profile)
    if mappings:
        base["pathMappings"] = mappings
    attach = {"name": ATTACH_NAME, **base}
    launch = {"name": LAUNCH_NAME, **base, "preLaunchTask": TASK_LABEL}
    return [attach, launch]


def build_headless_configuration(python_exe: str) -> dict:
    """A plain "launch" config for a standalone script that just needs
    `import qgis.core` and no running QGIS at all - `QgsApplication([],
    False)` + `initQgis()` is enough on its own, no QGIS_PREFIX_PATH or
    `setPrefixPath()` needed: confirmed for real against both an OSGeo4W
    and a standalone QGIS install, `QgsApplication` finds its own prefix
    from where its compiled core module sits once the venv's `pyvenv.cfg`
    points `home` at the QGIS-bundled Python (`env_builder._patch_pyvenv_
    cfg`). Setting QGIS_PREFIX_PATH explicitly was tried first and instead
    broke `import qgis.core` outright ("DLL load failed") - so this
    config deliberately sets nothing beyond the interpreter itself."""
    return {
        "name": HEADLESS_NAME,
        "type": "debugpy",
        "request": "launch",
        "program": "${file}",
        "console": "integratedTerminal",
        "justMyCode": False,
        "python": python_exe,
    }


def build_task(devbridge_python: str, lang: str | None) -> dict:
    args = ["-m", "devbridge"]
    if lang:
        args += ["--lang", lang]
    # host/port are read from .devbridge.json by `devbridge launch`
    args += ["launch", "--wait-ready", "--project-dir", "${workspaceFolder}"]
    return {
        "label": TASK_LABEL,
        "type": "process",
        "command": devbridge_python,
        "args": args,
        "problemMatcher": [],
        "presentation": {"reveal": "silent", "panel": "shared"},
    }


def write_vscode_config(project_dir: Path, venv_path: Path, port: int = DEFAULT_PORT,
                        verbose_print=print, *, host: str = "localhost",
                        plugin_name: str | None = None,
                        devbridge_python: str | None = None,
                        lang: str | None = None, profile: str = "default") -> None:
    verbose_print(t("writing_vscode"))
    project_dir = Path(project_dir)
    vscode_dir = project_dir / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)

    interpreter = str(_venv_interpreter(Path(venv_path)))
    if plugin_name is None:
        plugin_name = infer_plugin_name(project_dir)

    def _settings(d: dict) -> dict:
        d["python.defaultInterpreterPath"] = interpreter
        d["python.terminal.activateEnvironment"] = True
        return d

    def _launch(d: dict) -> dict:
        d.setdefault("version", "0.2.0")
        configs = d.setdefault("configurations", [])
        for cfg in build_launch_configurations(host, port, plugin_name, profile):
            _upsert(configs, "name", cfg)
        _upsert(configs, "name", build_headless_configuration(interpreter))
        return d

    def _tasks(d: dict) -> dict:
        d.setdefault("version", "2.0.0")
        tasks = d.setdefault("tasks", [])
        _upsert(tasks, "label", build_task(devbridge_python or sys.executable, lang))
        return d

    _merge_json(vscode_dir / "settings.json", _settings, verbose_print)
    _merge_json(vscode_dir / "launch.json", _launch, verbose_print)
    _merge_json(vscode_dir / "tasks.json", _tasks, verbose_print)
