"""``devbridge uninstall``: undo what ``install-plugin``/``link-plugin`` and
``setup`` did. Two independent things, either or both:

- the QGIS plugin itself (``uninstall_plugin``): removed from every profile
  it was linked/copied into and disabled in QGIS's own settings ini -
  DevBridge by default, or any other name (e.g. one set up with
  ``link-plugin``).
- one project's debug setup (``uninstall_project``, ``--project-dir``): its
  ``.venv/``, ``.devbridge.json`` and ``.pycharm-debug/``, plus *only* the
  entries DevBridge itself wrote inside ``.vscode/{launch,tasks}.json`` (by
  name/label) - never the rest of a user's own ``.vscode/`` content.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable

from . import bridge_plugin, project_config, vscode_config
from .i18n_util import t


def uninstall_plugin(profile: str | None = None, name: str = bridge_plugin.PLUGIN_NAME,
                     log: Callable[[str], None] = print) -> int:
    """Removes ``name`` from every matching QGIS profile and disables it in
    the ini. Returns 1 only if QGIS was running and something had to be
    left in place (rerun once it's closed)."""
    targets = bridge_plugin.profile_dirs(profile)
    if not targets:
        log(t("bridge_no_profile"))
        return 1

    running = bridge_plugin.qgis_running()
    found_any = False
    status = 0
    for prof in targets:
        target = prof / "python" / "plugins" / name
        if not target.exists() and not target.is_symlink():
            continue
        found_any = True
        if running:
            log(t("uninstall_skipped_running", target=target))
            status = 1
            continue
        bridge_plugin._remove(target)
        log(t("uninstall_removed_plugin", target=target))
        ini = bridge_plugin.find_ini(prof)
        if ini is not None:
            bridge_plugin.set_plugin_enabled(ini, name=name, enabled=False)
    if not found_any:
        log(t("uninstall_not_installed", name=name))
    return status


def _remove_entry(items: list, key: str, value: str) -> bool:
    for i, item in enumerate(items):
        if isinstance(item, dict) and item.get(key) == value:
            del items[i]
            return True
    return False


def _clean_json(path: Path, list_key: str, entry_key: str, names: tuple[str, ...],
                log: Callable[[str], None]) -> None:
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return          # not our concern to fix an already-broken file
    if not isinstance(data, dict) or not isinstance(data.get(list_key), list):
        return
    removed = any([_remove_entry(data[list_key], entry_key, n) for n in names])
    if removed:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        log(t("uninstall_vscode_cleaned", path=path))


def _clean_vscode(project_dir: Path, log: Callable[[str], None]) -> None:
    vscode_dir = project_dir / ".vscode"
    _clean_json(vscode_dir / "launch.json", "configurations", "name",
               (vscode_config.ATTACH_NAME, vscode_config.LAUNCH_NAME), log)
    _clean_json(vscode_dir / "tasks.json", "tasks", "label", (vscode_config.TASK_LABEL,), log)


def uninstall_project(project_dir: Path, log: Callable[[str], None] = print) -> int:
    """Removes what ``devbridge setup`` created for one project. Always
    succeeds (nothing here needs QGIS to be closed)."""
    project_dir = Path(project_dir).resolve()

    venv_path = project_dir / ".venv"
    if venv_path.is_dir():
        shutil.rmtree(venv_path, ignore_errors=True)
        log(t("uninstall_removed_path", path=venv_path))

    cfg_path = project_dir / project_config.CONFIG_NAME
    if cfg_path.exists():
        cfg_path.unlink()
        log(t("uninstall_removed_path", path=cfg_path))

    pycharm_dir = project_dir / ".pycharm-debug"
    if pycharm_dir.is_dir():
        shutil.rmtree(pycharm_dir, ignore_errors=True)
        log(t("uninstall_removed_path", path=pycharm_dir))

    _clean_vscode(project_dir, log)
    log(t("uninstall_project_done"))
    return 0
