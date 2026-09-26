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
    check(panel is not None and panel.tabs.count() == 5, "control panel opens with 5 tabs")
    check(panel.tabs.tabText(0) == "How to use" and "Prepare for debugging" in panel.guide.toPlainText(),
          "first tab is the step-by-step guide (English)")

    panel.lang_box.setCurrentIndex(panel.lang_box.findData("ka"))
    check(panel.tabs.tabText(1) == "VS Code" and panel.prepare_btn.text() == "დებაგისთვის მომზადება"
          and "მომზადება" in panel.guide.toPlainText(),
          "language switch to Georgian relabels the panel")
    check(any(a.text().startswith("მართვის") for a, _k in plugin._actions), "menu entries relabelled too")
    panel.lang_box.setCurrentIndex(panel.lang_box.findData("en"))
    check(panel.prepare_btn.text() == "Prepare for debugging", "…and back to English")
    check(i18n_util.get_lang() == "en", "plugin language state follows the switch")

    items = [panel.plugin_combo.itemText(i) for i in range(panel.plugin_combo.count())]
    print(f"  info {len(items) - 1} plugin(s) listed across profiles: {items[1:4]}...")
    check(panel.plugin_combo.currentIndex() == 0 and items[0].startswith("- "),
          "nothing is pre-selected: entry 0 is a placeholder")
    from qgis.core import QgsApplication as _QA
    base = Path(_QA.qgisSettingsDirPath()).parents[2]
    other = "QGIS4" if "QGIS3" in str(_QA.qgisSettingsDirPath()) else "QGIS3"
    if (base / other / "profiles").is_dir() and any((base / other / "profiles").glob("*/python/plugins/*/__init__.py")):
        check(any(f"({other}/" in i for i in items), f"list also shows plugins of the {other} profile")
    panel.mode_new.setChecked(True)
    check(panel.mode_pages.currentIndex() == 1 and panel.prepare_btn.text() == "Create and prepare",
          "'Start a NEW plugin' switches the form and the button")
    panel.mode_folder.setChecked(True)
    check(panel.mode_pages.currentIndex() == 2 and panel.prepare_btn.text() == "Prepare for debugging", "'Any folder' mode")
    panel.mode_existing.setChecked(True)

    # a brand-new plugin: the scaffold must load and unload in this QGIS (Qt5 or Qt6)
    panel.mode_new.setChecked(True)
    panel.new_parent.setText(str(tmp / "scratch_plugins"))
    panel.new_name.setText("hello_new")
    created = panel._target_path(create=True)
    check(created is not None and (created / "plugin.py").exists() and (created / "metadata.txt").exists(),
          f"new plugin scaffold written ({created})")
    import importlib
    sys.path.insert(0, str(tmp / "scratch_plugins"))
    new_iface = StubIface()
    new_plugin = importlib.import_module("hello_new").classFactory(new_iface)
    new_plugin.initGui()
    check(len(new_iface.menu_actions) == 1, "the new plugin's initGui adds its menu entry")
    from qgis.PyQt.QtWidgets import QMessageBox
    shown, warned = [], []
    QMessageBox.information = staticmethod(lambda *a, **k: shown.append(a[2]))
    QMessageBox.warning = staticmethod(lambda *a, **k: warned.append(a[2]))   # modal boxes would block a headless run
    new_plugin.run()
    check(shown == ["Hello from Hello New!"], "the new plugin's action runs")
    new_plugin.unload()
    check(not new_iface.menu_actions, "the new plugin unloads cleanly")
    panel.new_name.setText("hello_new")
    check(panel._target_path(create=True) is None and warned and "already contains" in warned[-1],
          "creating the same plugin again is refused with a message, not overwritten")
    panel.new_name.setText("Bad Name")
    check(panel._target_path(create=True) is None and "not a valid plugin name" in warned[-1], "a bad name is explained")
    panel._just_created = False
    panel.mode_existing.setChecked(True)

    # --- PyCharm: the pip step must use QGIS's Python, never the QGIS program itself
    from DevBridge import pycharm_bridge as pb
    real_py = pb.find_python_executable()
    check(Path(real_py).name.lower().startswith("python") and Path(real_py).exists(), f"find_python_executable -> {real_py}")
    saved_exe = sys.executable
    sys.executable = str(Path(saved_exe).with_name("qgis-bin.exe"))      # what real QGIS reports
    try:
        check(pb.find_python_executable() == real_py or Path(pb.find_python_executable()).name.lower().startswith("python"),
              "…still finds Python when sys.executable is qgis-bin.exe")
    finally:
        sys.executable = saved_exe

    try:
        versions = pb._available_pydevd_versions()
    except pb.PyCharmBridgeError as exc:
        versions = []
        print("  info PyPI unreachable, skipping real pip test:", exc)
    if versions:
        newest = max((v for v in versions if v.count(".") == 2 and v.replace(".", "").isdigit()),
                     key=lambda v: tuple(int(x) for x in v.split(".")))
        fake_pc = pb.PyCharmInstallation(tmp / "pycharm", newest, "PY", "PyCharm (fake)")
        pb.find_pycharm_installations = lambda: [fake_pc]                # no real PyCharm needed
        plugin.pycharm_bridge.install_dir = tmp / "pydevd"
        panel.py_port.setValue(12399)                                    # nothing listens here
        panel._start_pycharm()
        end = time.time() + 240
        while panel._py_worker is not None and time.time() < end:
            loop = QEventLoop()
            QTimer.singleShot(200, loop.quit)
            loop.exec()
        text = panel.py_log.toPlainText()
        print("  --- pycharm log (tail) ---\n    " + "\n    ".join(text.splitlines()[-4:]))
        check(panel._py_worker is None, "PyCharm prepare worker finished (UI was not blocked)")
        check(any(tmp.joinpath("pydevd").glob("pydevd_pycharm-*.dist-info")), "pydevd-pycharm installed into our own folder")
        import importlib
        check(importlib.import_module("pydevd_pycharm") is not None, "…and importable inside QGIS")
        check("12399" in text and not plugin.pycharm_bridge.is_running,
              "no PyCharm server listening -> clear 'could not connect' message, bridge stays stopped")

    # bridges: start may legitimately fail if this QGIS python has no debugpy; it must not crash
    plugin._on_start_bridge()
    print("  info start-bridge message:", iface.bar.messages[-1][:110])
    if versions:   # PyCharm's pydevd was loaded above -> the VS Code bridge must refuse cleanly, not crash
        check("only one debugger" in iface.bar.messages[-1], "VS Code bridge refuses politely after PyCharm's pydevd is loaded")
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
        proj = tmp / "setup_plugins" / "my_plugin"
        panel.mode_new.setChecked(True)                      # the whole new-plugin path: scaffold + venv + debugpy
        panel.new_parent.setText(str(proj.parent))
        panel.new_name.setText("my_plugin")
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
        check((proj / ".venv").is_dir() and (proj / ".vscode" / "launch.json").exists() and (proj / "plugin.py").exists(),
              "new plugin: starter files + .venv + .vscode/launch.json were created")
        check("Next:" in log, "the panel tells what to do next")

    plugin.unload()
    check(not iface.menu_actions and not iface.toolbar_actions, "unload removes every action")

    app.exitQgis()
    print("RESULT:", "FAILED (" + str(len(FAILURES)) + ")" if FAILURES else "all checks passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
