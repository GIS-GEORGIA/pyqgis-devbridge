"""Install debugpy into both the QGIS-bundled interpreter (so QGIS itself
can host a debug server) and the project venv (so the IDE side resolves
the same protocol version)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .detectors.base import QgisInstallation
from .i18n_util import t


def _pip_install(python_exe: str, verbose_print=print) -> None:
    subprocess.run(
        [python_exe, "-m", "pip", "install", "--upgrade", "debugpy"],
        check=True,
    )


def install_debugpy(qgis: QgisInstallation, venv_python: Path | None = None,
                     verbose_print=print) -> None:
    verbose_print(t("installing_debugpy", target=str(qgis.python_exe)))
    _pip_install(str(qgis.python_exe), verbose_print)

    if venv_python:
        verbose_print(t("installing_debugpy", target=str(venv_python)))
        _pip_install(str(venv_python), verbose_print)
