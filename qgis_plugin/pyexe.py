"""Locate the real Python interpreter that belongs to this QGIS.

Inside QGIS, ``sys.executable`` is the QGIS program itself (``qgis-bin.exe``,
``/usr/bin/qgis``, the .app binary), never a ``python`` executable. That
breaks two things unless worked around:

* ``pip install`` (``debugpy``/``pydevd-pycharm``) would try to run pip
  *inside the QGIS program*.
* ``debugpy.listen()`` spawns its own background "adapter" process via
  ``sys.executable`` unless told otherwise; pointed at the QGIS binary,
  that adapter never starts and ``debugpy.listen()`` fails after a long
  timeout with "timed out waiting for adapter to connect" — confirmed by
  running this for real inside QGIS 3.44.5 (``qgis-bin.exe --code``), not
  just assumed.

No ``qgis.*`` imports, same rule as ``debug_bridge.py`` / ``pycharm_bridge.py``:
independently unit-testable and reusable from the QGIS Python console.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path


class PythonNotFoundError(RuntimeError):
    pass


def _no_window() -> int:
    return subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


def _python_version_of(exe: Path) -> str | None:
    try:
        out = subprocess.run(
            [str(exe), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
            capture_output=True, text=True, timeout=20, creationflags=_no_window(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def find_python_executable() -> str:
    """A real `python` matching the interpreter QGIS embeds: verified by
    actually running it and checking its version, not just guessed from a
    name pattern, so a look-alike on PATH is never picked by mistake."""
    major, minor = sys.version_info[:2]
    want = f"{major}.{minor}"
    exe = Path(sys.executable)

    candidates: list[Path] = []
    if exe.name.lower().startswith("python"):          # console / python-qgis.bat
        candidates.append(exe)
    base_exe = getattr(sys, "_base_executable", None)   # CPython's own record of the real interpreter
    if base_exe:
        candidates.append(Path(base_exe))
    for prefix in dict.fromkeys((sys.exec_prefix, sys.base_exec_prefix)):
        base = Path(prefix)
        if platform.system() == "Windows":
            candidates.append(base / "python.exe")
        else:
            candidates += [base / "bin" / f"python{want}", base / "bin" / "python3", base / "bin" / "python"]
    candidates += [exe.parent / "bin" / "python3", exe.parent / "python3"]       # macOS .app layouts
    for name in (f"python{want}", "python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    for cand in dict.fromkeys(candidates):
        if cand.exists() and _python_version_of(cand) == want:
            return str(cand)
    raise PythonNotFoundError("python_not_found")
