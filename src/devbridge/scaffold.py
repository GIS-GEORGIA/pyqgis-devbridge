"""Create the starting files of a brand-new QGIS plugin.

The result is a tiny but complete plugin that loads on QGIS 3.40+ (Qt5) and
QGIS 4 (Qt6): it adds one menu entry that shows a message. It is meant to be
edited, debugged (`devbridge setup` / the DevBridge panel) and grown.
"""
from __future__ import annotations

import re
from pathlib import Path

# Plugin id == folder name == Python package name: keep it a plain lowercase identifier.
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
_RESERVED = {"devbridge", "qgis", "test", "tests", "plugin", "plugins", "core", "gui", "utils"}

# A script is just a file name, not an importable package - only bad path
# characters and an unreasonable length are actually disallowed.
_SCRIPT_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\-]{0,79}$")


class ScaffoldError(ValueError):
    """`str(exc)` is a translation key (name_invalid, name_reserved, exists, parent_missing)."""


def validate_name(name: str) -> None:
    if not _NAME_RE.match(name or ""):
        raise ScaffoldError("name_invalid")
    if name in _RESERVED:
        raise ScaffoldError("name_reserved")


def validate_script_name(name: str) -> None:
    if not _SCRIPT_NAME_RE.match((name or "").removesuffix(".py")):
        raise ScaffoldError("script_name_invalid")


def default_title(name: str) -> str:
    return name.replace("_", " ").strip().title()


_INIT = '''\
"""{title} — QGIS plugin entry point."""


def classFactory(iface):  # noqa: N802 - QGIS requires this exact name
    from .plugin import {cls}
    return {cls}(iface)
'''

_PLUGIN = '''\
"""Main class of {title}.

Qt is imported through `qgis.PyQt` and enums are written in their scoped form,
so the same code runs on QGIS 3.40+ (Qt5) and QGIS 4 (Qt6).
"""
from qgis.PyQt.QtWidgets import QAction, QMessageBox


class {cls}:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.menu = "{title}"

    def initGui(self):  # noqa: N802
        self.action = QAction("Say hello", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(self.menu, self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginMenu(self.menu, self.action)
            self.action = None

    def run(self):
        # Put a breakpoint on the next line, then use the menu entry while debugging.
        message = "Hello from {title}!"
        QMessageBox.information(self.iface.mainWindow(), "{title}", message)
'''

_METADATA = '''\
[general]
name={title}
qgisMinimumVersion=3.40
qgisMaximumVersion=4.99
supportsQt6=True
description={title}: a new QGIS plugin.
about=Created with DevBridge. Edit plugin.py, then use the DevBridge panel to debug it.
version=0.1.0
author={author}
email={email}
tracker=
repository=
homepage=
tags=
category=Plugins
experimental=True
deprecated=False
'''

_GITIGNORE = '''\
.venv/
__pycache__/
*.pyc
.idea/
.pycharm-debug/
'''


_SCRIPT = '''\
"""{title} - standalone PyQGIS script, no running QGIS needed.

Run it with the "PyQGIS: Debug current file (no QGIS)" launch config
(.vscode/launch.json, written by `devbridge setup`): open this file, pick
that configuration in Run and Debug, press F5. Or from a terminal with the
venv active: python {filename}
"""
from qgis.core import Qgis, QgsApplication

qgs = QgsApplication([], False)   # False = no GUI
qgs.initQgis()

try:
    # Put a breakpoint on the next line, then start debugging.
    print("QGIS", Qgis.QGIS_VERSION)
finally:
    qgs.exitQgis()
'''


def create_script(parent_dir: Path, name: str, title: str | None = None) -> Path:
    """Write `<parent_dir>/<name>.py` (adding `.py` if missing) and return
    its path. Unlike `create_plugin`, the parent folder is created if
    needed - a script has no QGIS-profile-layout requirement to get right."""
    validate_script_name(name)
    parent_dir = Path(parent_dir)
    parent_dir.mkdir(parents=True, exist_ok=True)
    filename = name if name.endswith(".py") else f"{name}.py"
    target = parent_dir / filename
    if target.exists():
        raise ScaffoldError("script_exists")

    title = (title or default_title(filename.removesuffix(".py"))).replace('"', "'")
    target.write_text(_SCRIPT.format(title=title, filename=filename), encoding="utf-8", newline="\n")
    return target


def create_plugin(parent_dir: Path, name: str, title: str | None = None,
                  author: str = "", email: str = "") -> Path:
    """Write the skeleton to `<parent_dir>/<name>` and return that folder."""
    validate_name(name)
    parent_dir = Path(parent_dir)
    if not parent_dir.is_dir():
        raise ScaffoldError("parent_missing")
    target = parent_dir / name
    if target.exists() and any(target.iterdir()):
        raise ScaffoldError("exists")

    title = (title or default_title(name)).replace('"', "'")
    cls = "".join(part.capitalize() for part in name.split("_")) + "Plugin"
    fields = dict(title=title, cls=cls, author=author or "Your Name", email=email or "you@example.com")

    target.mkdir(exist_ok=True)
    files = {
        "__init__.py": _INIT,
        "plugin.py": _PLUGIN,
        "metadata.txt": _METADATA,
        ".gitignore": _GITIGNORE,
    }
    for filename, template in files.items():
        (target / filename).write_text(template.format(**fields), encoding="utf-8", newline="\n")
    return target
