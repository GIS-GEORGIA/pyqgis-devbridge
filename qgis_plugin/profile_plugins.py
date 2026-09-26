"""List the user's own plugins in the running QGIS profile. No qgis.*
imports, so it is unit-testable."""
from __future__ import annotations

from pathlib import Path

PLUGIN_NAME = "DevBridge"


def list_plugins(profile_dir: Path) -> list[Path]:
    """Plugin folders in ``<profile>/python/plugins`` (excluding DevBridge itself)."""
    plugins_dir = Path(profile_dir) / "python" / "plugins"
    if not plugins_dir.is_dir():
        return []
    return [
        p for p in sorted(plugins_dir.iterdir(), key=lambda p: p.name.lower())
        if p.is_dir() and p.name != PLUGIN_NAME
        and not p.name.startswith((".", "_")) and (p / "__init__.py").exists()
    ]
