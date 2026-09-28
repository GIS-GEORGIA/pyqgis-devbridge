"""Detect a QGIS install on Linux (apt, flatpak-less system installs,
and conda-forge environments)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .base import QgisInstallation

_COMMON_PYTHON_DIRS = [
    "/usr/share/qgis/python",
    "/usr/lib/python3/dist-packages",
    "/usr/local/lib/qgis/python",
]


def _probe_python_import(python_exe: str) -> tuple[Path, Path] | None:
    """Ask an interpreter where its `qgis` package + plugins dir live."""
    code = (
        "import qgis, os, pathlib;"
        "p = pathlib.Path(qgis.__file__).resolve().parent.parent;"
        "print(p);"
        "print(p / 'plugins')"
    )
    try:
        out = subprocess.run(
            [python_exe, "-c", code],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    lines = out.stdout.strip().splitlines()
    if len(lines) < 2:
        return None
    return Path(lines[0]), Path(lines[1])


def find_qgis() -> QgisInstallation | None:
    # 1. System python3 (most common on Debian/Ubuntu with apt-installed QGIS)
    for py in ("python3", "python"):
        exe = shutil.which(py)
        if not exe:
            continue
        result = _probe_python_import(exe)
        if result:
            qgis_python_dir, plugins_dir = result
            return QgisInstallation(
                root=Path("/usr"),
                python_exe=Path(exe),
                qgis_python_dir=qgis_python_dir,
                plugins_dir=plugins_dir if plugins_dir.exists() else None,
                bin_dirs=(),
                version_hint="system",
            )

    # 2. Fallback: known static paths without needing a working import
    qgis_bin = shutil.which("qgis")
    for candidate in _COMMON_PYTHON_DIRS:
        p = Path(candidate)
        if (p / "qgis").exists():
            return QgisInstallation(
                root=Path("/usr"),
                python_exe=Path(shutil.which("python3") or "/usr/bin/python3"),
                qgis_python_dir=p,
                plugins_dir=(p / "plugins") if (p / "plugins").exists() else None,
                bin_dirs=(),
                version_hint="system (static path)",
            )

    if qgis_bin:
        # QGIS binary exists but python bindings couldn't be located automatically.
        return QgisInstallation(
            root=Path(qgis_bin).parent,
            python_exe=Path(shutil.which("python3") or "/usr/bin/python3"),
            qgis_python_dir=None,
            plugins_dir=None,
            bin_dirs=(),
            version_hint="binary-only (manual PYTHONPATH needed)",
        )
    return None


def find_all_qgis() -> list[QgisInstallation]:
    """Linux systems realistically have one QGIS on PATH; kept as a list for a
    uniform cross-platform API (Windows can have several side by side)."""
    found = find_qgis()
    return [found] if found else []
