#!/usr/bin/env python3
"""Load dist/DevBridge.zip in a real (headless) QGIS Python and drive the control panel.

Proves the universal-build claim on each QGIS you support, the same way
qgis-plugins-repo/tools/smoke_test.py does, but goes further: it opens the panel,
switches language, and runs the real "prepare a plugin" job in a temp folder.

    "C:\\Program Files\\QGIS 3.44.5\\bin\\python-qgis.bat" tools/qgis_headless_check.py dist/DevBridge.zip
    "C:\\Program Files\\QGIS 4.2.0\\bin\\python-qgis.bat"  tools/qgis_headless_check.py dist/DevBridge.zip

Add --no-setup to skip the slow venv/pip step. Uses a throw-away settings file
(DEVBRIDGE_CONFIG) and never writes to your QGIS profile.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FAILURES: list[str] = []


def check(cond: bool, what: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        FAILURES.append(what)


class _Bar:
    def __init__(self):
        self.messages: list[str] = []

    def pushMessage(self, title, text, level=None, *a, **k):  # noqa: N802
        self.messages.append(str(text))


class StubIface:
    def __init__(self):
        self.bar = _Bar()
        self.menu_actions = []
        self.toolbar_actions = []

    def mainWindow(self):  # noqa: N802
        return None

    def messageBar(self):  # noqa: N802
        return self.bar

    def addPluginToMenu(self, _menu, action):  # noqa: N802
        self.menu_actions.append(action)

    def removePluginMenu(self, _menu, action):  # noqa: N802
        if action in self.menu_actions:
            self.menu_actions.remove(action)

    def addToolBarIcon(self, action):  # noqa: N802
        self.toolbar_actions.append(action)

    def removeToolBarIcon(self, action):  # noqa: N802
        if action in self.toolbar_actions:     # QGIS ignores actions that were never added
            self.toolbar_actions.remove(action)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run_setup = "--no-setup" not in sys.argv
    zip_path = Path(args[0]).resolve()

    tmp = Path(tempfile.mkdtemp(prefix="devbridge_check_"))
    os.environ["DEVBRIDGE_CONFIG"] = str(tmp / "config.json")
    zipfile.ZipFile(zip_path).extractall(tmp / "plugins")
    sys.path.insert(0, str(tmp / "plugins"))

    from qgis.core import Qgis, QgsApplication
    from qgis.PyQt.QtCore import QEventLoop, QTimer

    from qgis.PyQt.QtCore import QCoreApplication
    # what real QGIS sets, so qgisSettingsDirPath() is the user's actual profile
    QCoreApplication.setOrganizationName("QGIS")
    QCoreApplication.setApplicationName("QGIS4" if Qgis.QGIS_VERSION_INT >= 40000 else "QGIS3")
    app = QgsApplication([], True)
    app.initQgis()
    print(f"QGIS {Qgis.version()}  |  Python {sys.version.split()[0]}  |  {zip_path.name}")

    import DevBridge  # the plugin package, as QGIS imports it
    from DevBridge import i18n_util, tool_launcher

    iface = StubIface()
    plugin = DevBridge.classFactory(iface)
    plugin.initGui()
    check(len(iface.menu_actions) == 8 and len(iface.toolbar_actions) == 1, "initGui: 8 menu actions + toolbar icon")

    tool = tool_launcher.tool_dir()
    check(tool is not None and (tool / "devbridge" / "pipeline.py").exists(), f"bundled tool found ({tool})")
    check(tool_launcher.folder_to_open() is not None, "tool folder resolvable for the 'Open folder' button")
    check((tool / "devbridge_gui.pyw").exists(), "launcher script devbridge_gui.pyw sits next to the tool package")

    plugin._on_control_panel()
    panel = plugin._panel
    check(panel is not None and panel.tabs.count() == 4, "control panel opens with 4 tabs")

    panel.lang_box.setCurrentIndex(panel.lang_box.findData("ka"))
    check(panel.tabs.tabText(0) == "VS Code" and panel.prepare_btn.text() == "დებაგისთვის მომზადება",
          "language switch to Georgian relabels the panel")
    check(any(a.text().startswith("მართვის") for a, _k in plugin._actions), "menu entries relabelled too")
    panel.lang_box.setCurrentIndex(panel.lang_box.findData("en"))
    check(panel.prepare_btn.text() == "Prepare for debugging", "…and back to English")
    check(i18n_util.get_lang() == "en", "plugin language state follows the switch")

    print(f"  info {panel.plugin_combo.count()} plugin(s) listed from this profile: "
          f"{[panel.plugin_combo.itemText(i) for i in range(min(4, panel.plugin_combo.count()))]}…")

    # bridges: start may legitimately fail if this QGIS python has no debugpy; it must not crash
    plugin._on_start_bridge()
    print("  info start-bridge message:", iface.bar.messages[-1][:110])
    panel._refresh_status()
    plugin._on_stop_bridge()
    check(True, "start/stop bridge handlers run without raising")

    # shared settings round-trip
    panel.vs_port.setValue(5999)
    panel._apply_vscode_settings()
    from DevBridge import shared_config
    check(shared_config.load()["port"] == 5999, "port change is written to the shared settings file")

    try:
        py = tool_launcher.find_gui_python()
        check(True, f"a Python with tkinter was found for the desktop tool: {py}")
    except tool_launcher.NoTkError:
        print("  info no Python with tkinter on this machine (the panel would show the install hint)")

    if run_setup:
        proj = tmp / "my_plugin"
        proj.mkdir()
        (proj / "__init__.py").write_text("")
        panel.project_edit.setText(str(proj))
        panel._prepare()
        loop_end = time.time() + 600
        while panel._worker is not None and time.time() < loop_end:
            loop = QEventLoop()
            QTimer.singleShot(200, loop.quit)
            loop.exec()
        log = panel.log.toPlainText()
        print("  --- setup log (tail) ---\n    " + "\n    ".join(log.splitlines()[-8:]))
        check(panel._worker is None, "setup worker finished")
        check("ERROR" not in log, "setup finished without ERROR")
        check((proj / ".venv").is_dir() and (proj / ".vscode" / "launch.json").exists(),
              ".venv and .vscode/launch.json were created")

    plugin.unload()
    check(not iface.menu_actions and not iface.toolbar_actions, "unload removes every action")

    app.exitQgis()
    print("RESULT:", "FAILED (" + str(len(FAILURES)) + ")" if FAILURES else "all checks passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
