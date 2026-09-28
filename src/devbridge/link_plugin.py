"""``devbridge link-plugin``: put an arbitrary plugin folder - typically a
git checkout that lives outside any QGIS profile - into a QGIS profile's
``python/plugins/`` (linked by default, exactly like ``bridge_plugin.py``
does for DevBridge itself) and enable it, so QGIS loads it without a
manual copy or a trip through the Plugin Manager.

This is ``bridge_plugin.install_into_profiles`` generalized from "always
DevBridge" to "any plugin folder, any name".
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import bridge_plugin
from .i18n_util import t


def validate_source(source: Path) -> str | None:
    """None if ``source`` looks like a loadable QGIS plugin folder, else a
    translation key explaining why not."""
    if not source.is_dir():
        return "link_source_missing"
    if not (source / "__init__.py").exists():
        return "link_source_not_a_plugin"
    return None


def link_into_profiles(source: Path, name: str | None = None, profile: str | None = None,
                       copy: bool = False, force: bool = False,
                       log: Callable[[str], None] = print) -> int:
    """Link (or copy) ``source`` into each matching QGIS profile as
    ``name`` (default: the source folder's own name) and enable it.
    Returns a process-style exit code (0 = fine everywhere it applied)."""
    source = Path(source).resolve()
    problem = validate_source(source)
    if problem:
        log(t(problem, path=source))
        return 1
    name = name or source.name

    targets = bridge_plugin.profile_dirs(profile)
    if not targets:
        log(t("bridge_no_profile"))
        return 1

    status = 0
    running = bridge_plugin.qgis_running()
    for prof in targets:
        plugins_dir = prof / "python" / "plugins"
        result = bridge_plugin.install(source, plugins_dir, copy=copy, force=force, name=name)
        target = plugins_dir / name
        if result == "exists":
            log(t("link_exists", target=target))
            status = 1
            continue
        log(t(f"link_{result}", name=name, target=target))

        ini = bridge_plugin.find_ini(prof)
        if ini is None:
            log(t("link_enable_no_ini", name=name, profile=prof))
        elif running:
            log(t("link_enable_skipped_running", name=name))
        else:
            bridge_plugin.set_plugin_enabled(ini, name=name)
            log(t("link_enabled", name=name))
    log(t("link_restart_hint", name=name))
    return status
