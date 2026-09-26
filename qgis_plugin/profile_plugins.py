"""List the user's own plugins in the QGIS profiles. No qgis.* imports, so it is
unit-testable."""
from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class Entry:
    name: str
    path: Path
    label: str          # "my_plugin  (QGIS3/default)"
    current: bool       # lives in the profile of the running QGIS


def _profile_roots(current_profile_dir: Path) -> list[Path]:
    """`.../QGIS/QGIS3/profiles` and `.../QGIS4/profiles` next to the running profile, so a plugin
    from another QGIS version's profile shows up too; just the running profile's parent otherwise."""
    p = Path(current_profile_dir)
    if p.parent.name == "profiles" and p.parents[1].name.startswith("QGIS"):
        base = p.parents[2]
        roots = [base / major / "profiles" for major in ("QGIS3", "QGIS4")]
        return [r for r in roots if r.is_dir()]
    return [p.parent] if p.parent.is_dir() else []


def list_all(current_profile_dir: Path) -> list[Entry]:
    """Plugins of every QGIS profile, the running profile first, then by name."""
    current = Path(current_profile_dir)
    try:
        current_resolved = current.resolve()
    except OSError:
        current_resolved = current
    entries: list[Entry] = []
    for root in _profile_roots(current):
        profiles = sorted((d for d in root.iterdir() if d.is_dir()), key=lambda d: (d.name != "default", d.name))
        for prof in profiles:
            try:
                is_current = prof.resolve() == current_resolved
            except OSError:
                is_current = False
            for plugin in list_plugins(prof):
                major = root.parent.name if root.parent.name.startswith("QGIS") else ""
                where = f"{major}/{prof.name}" if major else prof.name
                entries.append(Entry(plugin.name, plugin, f"{plugin.name}  ({where})", is_current))
    return sorted(entries, key=lambda e: (not e.current, e.name.lower()))


def new_plugin_parent(current_profile_dir: Path) -> Path:
    """Where a new plugin goes by default: the running profile's plugins folder, so QGIS sees it."""
    return Path(current_profile_dir) / "python" / "plugins"
