"""Well-known per-user QGIS locations. No QGIS import needed - see
detectors/ for locating an *installation*; this is only about where a
running QGIS keeps its profiles."""
from __future__ import annotations

import os
import platform
from pathlib import Path


def qgis_profiles_dir(major: str = "QGIS3") -> Path:
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "QGIS" / major / "profiles"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "QGIS" / major / "profiles"
    xdg = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(xdg) / "QGIS" / major / "profiles"


def qgis_user_plugins_dir(profile: str = "default", major: str = "QGIS3") -> Path:
    return qgis_profiles_dir(major) / profile / "python" / "plugins"
