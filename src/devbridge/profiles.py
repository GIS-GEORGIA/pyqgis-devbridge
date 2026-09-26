"""Find the user's own QGIS plugins in their QGIS profile folder(s), so
`devbridge setup` can work on a plugin in place without --project-dir.

The profile's ``python/plugins`` folder is where QGIS itself loads
plugins from, so setting up the environment there means edits are live
in QGIS and VS Code at the same time.
"""
from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# The bridge plugin itself is not a development target.
_EXCLUDED = {"DevBridge"}


@dataclass(frozen=True)
class ProfilePlugin:
    name: str
    path: Path
    profile: str        # e.g. "default"
    qgis_major: str     # "QGIS3" / "QGIS4"

    @property
    def label(self) -> str:
        return f"{self.name}  ({self.qgis_major}/{self.profile})"


def profile_roots() -> list[Path]:
    """`.../QGIS/QGIS3/profiles` (and QGIS4) for the current OS."""
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return [base / "QGIS" / major / "profiles" for major in ("QGIS3", "QGIS4")]


def default_plugins_dir(major: str | None = None) -> Path | None:
    """`python/plugins` of the first existing `default` profile (QGIS3 before QGIS4),
    or of the given major version ("3" / "4"). None if QGIS has never been started."""
    for root in profile_roots():
        if major and root.parent.name != f"QGIS{major}":
            continue
        if (root / "default").is_dir():
            return root / "default" / "python" / "plugins"
    return None


def _is_plugin_dir(path: Path) -> bool:
    return path.is_dir() and (path / "__init__.py").exists() and not path.name.startswith((".", "_"))


def find_plugins(profile: str | None = None) -> list[ProfilePlugin]:
    """All user plugins across QGIS profiles (optionally one profile name),
    "default" profile first."""
    found: list[ProfilePlugin] = []
    for root in profile_roots():
        if not root.is_dir():
            continue
        for prof_dir in sorted(root.iterdir(), key=lambda p: (p.name != "default", p.name)):
            if profile and prof_dir.name != profile:
                continue
            plugins_dir = prof_dir / "python" / "plugins"
            if not plugins_dir.is_dir():
                continue
            for p in sorted(plugins_dir.iterdir(), key=lambda p: p.name.lower()):
                if p.name not in _EXCLUDED and _is_plugin_dir(p):
                    found.append(ProfilePlugin(p.name, p, prof_dir.name, root.parent.name))
    return found


class PluginSelectionError(Exception):
    """Raised with a translation key + params when no single plugin can be chosen."""

    def __init__(self, key: str, **params: str):
        super().__init__(key)
        self.key = key
        self.params = params


def choose_plugin(
    name: str | None = None,
    profile: str | None = None,
    ask: Callable[[list[ProfilePlugin]], ProfilePlugin | None] | None = None,
) -> ProfilePlugin:
    """Pick the plugin to set up.

    - ``name`` given: exact (case-insensitive) match.
    - otherwise a single plugin is chosen automatically; with several,
      ``ask`` (an interactive picker) decides, and without one we fail
      with the list so the caller can print it.
    """
    plugins = find_plugins(profile)
    if not plugins:
        raise PluginSelectionError("no_profile_plugins")
    if name:
        matches = [p for p in plugins if p.name.lower() == name.lower()]
        if not matches:
            raise PluginSelectionError(
                "plugin_not_found", name=name,
                available=", ".join(p.name for p in plugins),
            )
        return matches[0]
    if len(plugins) == 1:
        return plugins[0]
    chosen = ask(plugins) if ask else None
    if chosen is None:
        raise PluginSelectionError(
            "multiple_plugins", available=", ".join(p.label for p in plugins),
        )
    return chosen
