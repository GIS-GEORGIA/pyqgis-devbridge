"""QGIS integration layer: menu entries, message bar feedback, and
bilingual labels. Keeps all QGIS-API-specific code out of debug_bridge.py
so the bridge logic stays unit-testable outside a running QGIS process.
"""
from __future__ import annotations

from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import Qgis

from .debug_bridge import DebugBridge, DebugBridgeError
from .pycharm_bridge import PyCharmBridge, PyCharmBridgeError, write_bridge_script
from .i18n_util import t


class DevBridgePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.bridge = DebugBridge()
        self.pycharm_bridge = PyCharmBridge()
        self._actions: list[QAction] = []
        self._menu = t("menu_title")

    # --- QGIS plugin lifecycle -------------------------------------------------
    def initGui(self) -> None:
        self._add_action(t("menu_start_bridge"), self._on_start_bridge)
        self._add_action(t("menu_stop_bridge"), self._on_stop_bridge)
        self._add_action(t("menu_settings"), self._on_settings)
        self._add_action(t("menu_pycharm_auto"), self._on_pycharm_auto)
        self._add_action(t("menu_pycharm_stop"), self._on_pycharm_stop)
        self._add_action(t("menu_pycharm_settings"), self._on_pycharm_settings)
        self._add_action(t("menu_pycharm_help"), self._on_pycharm_help)

    def unload(self) -> None:
        for action in self._actions:
            self.iface.removePluginMenu(self._menu, action)
            self.iface.removeToolBarIcon(action)
        self._actions.clear()

    def _add_action(self, text: str, callback) -> QAction:
        action = QAction(text, self.iface.mainWindow())
        action.triggered.connect(callback)
        self.iface.addPluginToMenu(self._menu, action)
        self._actions.append(action)
        return action

    # --- actions -----------------------------------------------------------
    def _on_start_bridge(self) -> None:
        try:
            self.bridge.start()
        except DebugBridgeError as exc:
            key = str(exc) if str(exc) in ("already_running", "debugpy_missing") else "debugpy_missing"
            msg = t(f"bridge_{key}" if key == "already_running" else key,
                    port=self.bridge.port)
            self.iface.messageBar().pushMessage("DevBridge", msg, level=Qgis.Warning)
            return
        msg = t("bridge_listening", host=self.bridge.host, port=self.bridge.port)
        self.iface.messageBar().pushMessage("DevBridge", msg, level=Qgis.Success)

    def _on_stop_bridge(self) -> None:
        try:
            self.bridge.stop()
        except DebugBridgeError:
            msg = t("bridge_not_running")
            self.iface.messageBar().pushMessage("DevBridge", msg, level=Qgis.Warning)
            return
        self.iface.messageBar().pushMessage("DevBridge", t("bridge_stopped"), level=Qgis.Info)

    def _on_settings(self) -> None:
        from .ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.bridge, self.iface.mainWindow())
        dialog.exec_()

    def _on_pycharm_auto(self) -> None:
        self.iface.messageBar().pushMessage("DevBridge", t("pycharm_detecting"), level=Qgis.Info)
        try:
            installation = self.pycharm_bridge.auto_configure_and_start()
        except PyCharmBridgeError as exc:
            self.iface.messageBar().pushMessage(
                "DevBridge", self._pycharm_error_message(exc), level=Qgis.Warning
            )
            return

        try:
            from pathlib import Path
            from qgis.core import QgsApplication
            script_dir = Path(QgsApplication.qgisSettingsDirPath()) / "devbridge"
            script_path = write_bridge_script(
                installation, self.pycharm_bridge.host, self.pycharm_bridge.port, script_dir
            )
            saved_note = " " + t("pycharm_script_saved", path=script_path)
        except OSError:
            saved_note = ""  # non-fatal: the live connection already succeeded

        msg = t("pycharm_bridge_started", host=self.pycharm_bridge.host,
                 port=self.pycharm_bridge.port, build=installation.build) + saved_note
        self.iface.messageBar().pushMessage("DevBridge", msg, level=Qgis.Success)

    def _on_pycharm_stop(self) -> None:
        try:
            self.pycharm_bridge.stop()
        except PyCharmBridgeError:
            self.iface.messageBar().pushMessage(
                "DevBridge", t("pycharm_bridge_not_running"), level=Qgis.Warning
            )
            return
        self.iface.messageBar().pushMessage(
            "DevBridge", t("pycharm_bridge_stopped"), level=Qgis.Info
        )

    def _on_pycharm_settings(self) -> None:
        from .ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.pycharm_bridge, self.iface.mainWindow())
        dialog.exec_()

    def _on_pycharm_help(self) -> None:
        from .i18n_util import _current_lang  # noqa: SLF001 - internal, read-only
        note_file = "README.ka.md" if _current_lang == "ka" else "README.en.md"
        QMessageBox.information(
            self.iface.mainWindow(),
            t("menu_pycharm_help"),
            f"See .pycharm-debug/{note_file} in your project "
            f"(generated by the pyqgis-devbridge setup tool). "
            f"This manual path is a fallback for PyCharm installs the "
            f"automatic detector can't find (portable/unzipped builds, "
            f"unusual install locations, or an offline machine).",
        )

    def _pycharm_error_message(self, exc: PyCharmBridgeError) -> str:
        key = str(exc)
        if key == "already_running":
            return t("pycharm_bridge_already_running")
        if key == "not_found":
            return t("pycharm_not_found")
        if key == "pydevd_missing":
            return t("pycharm_pydevd_missing")
        if key == "connection_refused":
            return t("pycharm_connection_refused",
                      host=self.pycharm_bridge.host, port=self.pycharm_bridge.port)
        if key.startswith("pypi_unreachable"):
            detail = key.split(":", 1)[-1].strip()
            return t("pycharm_pypi_unreachable", error=detail)
        return key
