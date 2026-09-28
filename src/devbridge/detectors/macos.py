"""Detect a QGIS install on macOS.

Covers the official .app bundle (``/Applications/QGIS*.app``, also in
``~/Applications``) and falls back to a Homebrew/conda-style interpreter
that can already ``import qgis``. Safe to import on any platform: every
filesystem probe just returns nothing where the paths don't exist.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .base import QgisInstallation
from .linux import _probe_python_import

_APP_DIRS = [
    "/Applications",
    str(Path.home() / "Applications"),
]


def _bundle_python(contents: Path) -> Path | None:
    """Interpreter shipped inside the .app bundle, if any."""
    candidates = [contents / "MacOS" / "bin" / "python3"]
    candidates += sorted(contents.glob("Frameworks/Python.framework/Versions/*/bin/python3"))
    candidates += sorted(contents.glob("MacOS/bin/python3.*"))
    return next((c for c in candidates if c.exists()), None)


def _find_bundle() -> QgisInstallation | None:
    for apps_dir in _APP_DIRS:
        # newest-looking name first: "QGIS-LTR.app", "QGIS 3.40.app", "QGIS.app"
        for app in sorted(Path(apps_dir).glob("QGIS*.app"), reverse=True):
            contents = app / "Contents"
            qgis_python_dir = contents / "Resources" / "python"
            if not (qgis_python_dir / "qgis").exists():
                continue
            python_exe = _bundle_python(contents) or Path(shutil.which("python3") or "/usr/bin/python3")
            plugins_dir = qgis_python_dir / "plugins"
            bin_dirs = tuple(
                p for p in (contents / "MacOS", contents / "MacOS" / "bin", contents / "Frameworks")
                if p.exists()
            )
            return QgisInstallation(
                root=app,
                python_exe=python_exe,
                qgis_python_dir=qgis_python_dir,
                plugins_dir=plugins_dir if plugins_dir.exists() else None,
                bin_dirs=bin_dirs,
                version_hint=app.stem,
            )
    return None


def find_qgis() -> QgisInstallation | None:
    bundle = _find_bundle()
    if bundle:
        return bundle

    # Homebrew / conda / any interpreter that can already `import qgis`
    for py in ("python3", "python"):
        exe = shutil.which(py)
        if not exe:
            continue
        result = _probe_python_import(exe)
        if result:
            qgis_python_dir, plugins_dir = result
            return QgisInstallation(
                root=qgis_python_dir,
                python_exe=Path(exe),
                qgis_python_dir=qgis_python_dir,
                plugins_dir=plugins_dir if plugins_dir.exists() else None,
                bin_dirs=(),
                version_hint="system (import probe)",
            )
    return None


def find_all_qgis() -> list[QgisInstallation]:
    """Kept as a list for a uniform cross-platform API (Windows can have
    several installs side by side); not yet worth enumerating every
    QGIS*.app bundle here since this detector itself is unverified on real
    macOS hardware."""
    found = find_qgis()
    return [found] if found else []
