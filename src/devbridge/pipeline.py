"""The 'prepare a project for debugging' sequence, shared by the CLI, the
standalone GUI and the QGIS plugin's control panel."""
from __future__ import annotations

import platform
from pathlib import Path
from typing import Callable

from . import debugpy_installer, env_builder, project_config, pycharm_config, vscode_config
from .detectors import get_detector
from .detectors.base import QgisInstallation
from .i18n_util import get_lang, t


class SetupError(RuntimeError):
    """`str(exc)` is a ready-to-show, translated message."""


def venv_python(venv_path: Path) -> Path:
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def find_qgis(log: Callable[[str], None] = print) -> QgisInstallation:
    log(t("detecting_qgis"))
    qgis = get_detector().find_qgis()
    if not qgis:
        raise SetupError(t("qgis_not_found"))
    log(t("qgis_found", path=qgis.root))
    return qgis


def run_setup(project_dir: Path, port: int = vscode_config.DEFAULT_PORT,
              venv_name: str = ".venv", log: Callable[[str], None] = print,
              qgis: QgisInstallation | None = None, host: str = "localhost",
              plugin_name: str | None = None) -> None:
    """Detect QGIS, build the venv, install debugpy, write .devbridge.json +
    IDE configs. `plugin_name` is auto-detected from the folder layout
    (`<profile>/python/plugins/<name>`) when not given explicitly."""
    qgis = qgis or find_qgis(log)
    project_dir = Path(project_dir).resolve()
    venv_path = project_dir / venv_name
    if plugin_name is None:
        plugin_name = vscode_config.infer_plugin_name(project_dir)

    env_builder.build_venv(qgis, venv_path, verbose_print=log)
    debugpy_installer.install_debugpy(qgis, venv_python=venv_python(venv_path), verbose_print=log)
    config_path = project_config.write_project_config(
        project_dir, host=host, port=port, plugin_name=plugin_name, venv_name=venv_name)
    log(t("wrote_file", path=config_path))
    vscode_config.write_vscode_config(
        project_dir, venv_path, port=port, verbose_print=log,
        host=host, plugin_name=plugin_name, lang=get_lang())
    pycharm_config.write_pycharm_notes(project_dir, verbose_print=log)
    log(t("done"))
