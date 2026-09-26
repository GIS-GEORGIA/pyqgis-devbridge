"""Detect an OSGeo4W / standalone QGIS install on Windows.

No external dependencies. Safe to import on non-Windows platforms (all
filesystem probes simply return no results there).
"""
from __future__ import annotations

import os
from pathlib import Path

from .base import QgisInstallation

_CANDIDATE_ROOTS = [
    r"C:\OSGeo4W64",
    r"C:\OSGeo4W",
    r"C:\Program Files\QGIS 3.34",
    r"C:\Program Files\QGIS 3.28",
    r"C:\Program Files\QGIS",
]


def _env_root() -> str | None:
    return os.environ.get("OSGEO4W_ROOT")


def _program_files_roots() -> list[str]:
    """Standalone-installer folders such as "QGIS 3.44.5", newest first."""
    found: list[Path] = []
    for var in ("ProgramFiles", "ProgramW6432"):
        base = os.environ.get(var)
        if base:
            found.extend(p for p in Path(base).glob("QGIS *") if p.is_dir())
    unique = sorted({str(p) for p in found}, reverse=True)
    return unique


def find_qgis() -> QgisInstallation | None:
    roots = []
    env_root = _env_root()
    if env_root:
        roots.append(env_root)
    roots.extend(_CANDIDATE_ROOTS)
    roots.extend(_program_files_roots())

    for root_str in roots:
        root = Path(root_str)
        if not root.exists():
            continue

        # OSGeo4W layout: <root>\apps\qgis\python  and  <root>\apps\Python3XX
        apps = root / "apps"
        qgis_python_dir = None
        for candidate in apps.glob("qgis*/python"):
            if (candidate / "qgis").exists():
                qgis_python_dir = candidate
                break

        python_exe = None
        for py_candidate in apps.glob("Python3*/python.exe"):
            python_exe = py_candidate
            break
        if python_exe is None:
            # Standalone installer layout: <root>\bin\python-qgis.bat wraps its own interpreter
            batch = root / "bin" / "python-qgis.bat"
            if batch.exists():
                python_exe = batch

        if qgis_python_dir is None or python_exe is None:
            continue

        plugins_dir = qgis_python_dir / "plugins"
        bin_dirs = tuple(
            p for p in [
                root / "bin",
                apps / "qgis" / "bin",
                apps / "Qt5" / "bin",
                apps / "Qt6" / "bin",
            ] if p.exists()
        )

        return QgisInstallation(
            root=root,
            python_exe=python_exe,
            qgis_python_dir=qgis_python_dir,
            plugins_dir=plugins_dir if plugins_dir.exists() else None,
            bin_dirs=bin_dirs,
            version_hint=root.name,
        )
    return None
