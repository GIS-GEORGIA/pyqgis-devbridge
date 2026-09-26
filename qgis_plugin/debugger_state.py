"""Which debugger backend is already loaded in this QGIS process.

debugpy (VS Code) and pydevd-pycharm (PyCharm) both load their own copy of pydevd
under the same top-level names (`_pydevd_bundle`, `pydevd`). Loading the second one
next to the first fails with an ImportError at best and can take QGIS down at worst,
and Python cannot unload either. So: one debugger per QGIS session.

No qgis.* imports — unit-testable.
"""
from __future__ import annotations

import sys


def active_backend() -> str | None:
    """"debugpy", "pycharm" or None (no pydevd loaded yet)."""
    module = sys.modules.get("_pydevd_bundle")
    if module is None:
        return "pycharm" if "pydevd_pycharm" in sys.modules else None
    origin = (getattr(module, "__file__", None) or "").replace("\\", "/")
    return "debugpy" if "/debugpy/" in origin else "pycharm"
