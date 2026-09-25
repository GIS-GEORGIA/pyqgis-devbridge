"""Platform-specific QGIS detectors."""
from __future__ import annotations

import platform
from types import ModuleType


def get_detector() -> ModuleType:
    """Return the detector module for the current OS (each exposes ``find_qgis()``)."""
    system = platform.system()
    if system == "Windows":
        from . import windows as detector
    elif system == "Darwin":
        from . import macos as detector
    else:
        from . import linux as detector
    return detector
