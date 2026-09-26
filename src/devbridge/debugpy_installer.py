"""Install debugpy into both the QGIS-bundled interpreter (so QGIS itself
can host a debug server) and the project venv (so the IDE side resolves
the same protocol version)."""
from __future__ import annotations

from pathlib import Path

from .detectors.base import QgisInstallation
from .i18n_util import t
from .proc import CommandError, run_logged

# A system-wide QGIS (e.g. C:\Program Files\QGIS 3.44.5) is usually read-only for a normal user.
_NOT_WRITABLE = ("permission denied", "access is denied", "winerror 5", "errno 13",
                 "externally-managed-environment", "read-only file system")


def _pip_install(python_exe: str, verbose_print=print) -> None:
    base = [python_exe, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", "debugpy"]
    try:
        run_logged(base, verbose_print)
    except CommandError as err:
        if not any(marker in str(err).lower() for marker in _NOT_WRITABLE):
            raise
        verbose_print(t("pip_retry_user"))
        run_logged(base[:-1] + ["--user", "debugpy"], verbose_print)


def install_debugpy(qgis: QgisInstallation, venv_python: Path | None = None,
                     verbose_print=print) -> None:
    verbose_print(t("installing_debugpy", target=str(qgis.python_exe)))
    _pip_install(str(qgis.python_exe), verbose_print)

    if venv_python:
        verbose_print(t("installing_debugpy", target=str(venv_python)))
        _pip_install(str(venv_python), verbose_print)
