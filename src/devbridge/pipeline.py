"""The 'prepare a project for debugging' sequence, shared by the CLI, the
standalone GUI and the QGIS plugin's control panel."""
from __future__ import annotations

import platform
from pathlib import Path
from typing import Callable

from . import debugpy_installer, env_builder, gitignore, project_config, pycharm_config, vscode_config
from .detectors import get_detector
from .detectors.base import QgisInstallation
from .i18n_util import get_lang, t
from .netutil import find_free_port, is_local_host, port_free


class SetupError(RuntimeError):
    """`str(exc)` is a ready-to-show, translated message."""


def venv_python(venv_path: Path) -> Path:
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def find_all_qgis(log: Callable[[str], None] = print) -> list[QgisInstallation]:
    """Every QGIS install this platform's detector can find, most-preferred
    first. Some machines genuinely have several side by side (OSGeo4W plus
    one or more standalone versions on Windows)."""
    log(t("detecting_qgis"))
    detector = get_detector()
    finder = getattr(detector, "find_all_qgis", None)
    if finder is not None:
        return finder()
    single = detector.find_qgis()
    return [single] if single else []


def find_qgis(log: Callable[[str], None] = print, qgis_root: str | Path | None = None,
              ask: Callable[[list[QgisInstallation]], "QgisInstallation | None"] | None = None
              ) -> QgisInstallation:
    """`qgis_root` picks a specific install by its root path (error if not
    found there). Otherwise: one install picks itself; several ask `ask`
    (an interactive picker) if given, else the most-preferred one - same
    silent default as before this function took an install-choosing hint,
    so no existing caller's behaviour changes."""
    installs = find_all_qgis(log)
    if qgis_root is not None:
        target = Path(qgis_root).resolve()
        match = next((q for q in installs if Path(q.root).resolve() == target), None)
        if match is None:
            raise SetupError(t("qgis_root_not_found", root=qgis_root))
        log(t("qgis_found", path=match.root))
        return match
    if not installs:
        raise SetupError(t("qgis_not_found"))
    chosen = installs[0]
    if len(installs) > 1 and ask is not None:
        chosen = ask(installs) or chosen
    log(t("qgis_found", path=chosen.root))
    return chosen


def _warn_if_remote_host(host: str, port: int, log: Callable[[str], None]) -> None:
    if not is_local_host(host):
        log(t("host_not_local_warning", host=host, port=port))


def _resolve_port(host: str, port: int, log: Callable[[str], None]) -> int:
    """The requested port, unless something is already listening on it - a
    stale QGIS session from an earlier debug run is the common cause. Picks
    the next free one nearby instead of silently writing a config that
    would fail the moment debugpy tries to bind it."""
    if port_free(host, port):
        return port
    alt = find_free_port(host, port + 1)
    if alt is None:
        raise SetupError(t("port_no_free_found", port=port))
    log(t("port_busy_using_alt", port=port, alt=alt))
    return alt


def run_setup(project_dir: Path, port: int = vscode_config.DEFAULT_PORT,
              venv_name: str = ".venv", log: Callable[[str], None] = print,
              qgis: QgisInstallation | None = None, host: str = "localhost",
              plugin_name: str | None = None, pycharm_host: str = "localhost",
              pycharm_port: int = 12345) -> None:
    """Detect QGIS, build the venv, install debugpy, write .devbridge.json +
    IDE configs. `plugin_name` is auto-detected from the folder layout
    (`<profile>/python/plugins/<name>`) when not given explicitly."""
    qgis = qgis or find_qgis(log)
    project_dir = Path(project_dir).resolve()
    venv_path = project_dir / venv_name
    if plugin_name is None:
        plugin_name = vscode_config.infer_plugin_name(project_dir)

    _warn_if_remote_host(host, port, log)
    port = _resolve_port(host, port, log)
    env_builder.build_venv(qgis, venv_path, verbose_print=log)
    debugpy_installer.install_debugpy(qgis, venv_python=venv_python(venv_path), verbose_print=log)
    config_path = project_config.write_project_config(
        project_dir, host=host, port=port, plugin_name=plugin_name, venv_name=venv_name)
    log(t("wrote_file", path=config_path))
    vscode_config.write_vscode_config(
        project_dir, venv_path, port=port, verbose_print=log,
        host=host, plugin_name=plugin_name, lang=get_lang())
    pycharm_config.write_pycharm_notes(project_dir, verbose_print=log)
    pycharm_config.write_pycharm_run_config(
        project_dir, host=pycharm_host, port=pycharm_port, plugin_name=plugin_name, verbose_print=log)
    ignored = gitignore.ensure_ignored(project_dir, venv_name)
    if ignored:
        log(t("wrote_file", path=ignored))
    log(t("done"))
