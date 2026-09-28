"""Detect OSGeo4W / standalone QGIS installs on Windows.

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


def _installation_at(root: Path) -> QgisInstallation | None:
    """A single root's own installation, or None if it doesn't look like one -
    the per-root half of what used to be find_qgis()'s loop body."""
    if not root.exists():
        return None

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
        return None

    plugins_dir = qgis_python_dir / "plugins"
    # apps/<flavour>/bin - not just "apps/qgis/bin" - holds qgis_core.dll etc.
    # itself; hardcoding "qgis" here missed it entirely on a "qgis-ltr"
    # install (confirmed: import qgis.core failed with "DLL load failed"
    # until this exact directory was added to the search path).
    flavour = qgis_python_dir.parent.name
    bin_dirs = tuple(
        p for p in [
            root / "bin",
            apps / flavour / "bin",
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


def find_all_qgis() -> list[QgisInstallation]:
    """Every install found, most-preferred first (OSGEO4W_ROOT, then the
    hard-coded candidates, then any Program Files\\QGIS * - newest name
    first). One machine can genuinely have several (OSGeo4W plus one or
    more standalone versions side by side)."""
    roots = []
    env_root = _env_root()
    if env_root:
        roots.append(env_root)
    roots.extend(_CANDIDATE_ROOTS)
    roots.extend(_program_files_roots())

    found: list[QgisInstallation] = []
    seen: set[str] = set()
    for root_str in roots:
        root = Path(root_str)
        key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        installation = _installation_at(root)
        if installation is not None:
            found.append(installation)
    return found


def find_qgis() -> QgisInstallation | None:
    found = find_all_qgis()
    return found[0] if found else None
