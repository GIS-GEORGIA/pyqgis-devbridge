"""DevBridge control panel: every operation as a button, in English or Georgian.

Tabs: VS Code bridge / PyCharm bridge / Prepare a plugin for debugging /
Desktop tool. Written for both Qt5 (QGIS 3.40+) and Qt6 (QGIS 4): Qt is
imported via qgis.PyQt only and enums are always scoped.
"""
from __future__ import annotations

from pathlib import Path

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt, QThread, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from .. import i18n_util, profile_plugins, shared_config, tool_launcher
from ..i18n_util import t


class _SetupWorker(QThread):
    """Runs the (slow, blocking) project preparation off the GUI thread."""
    line = pyqtSignal(str)
    finished_ok = pyqtSignal(bool, str)

    def __init__(self, project_dir: Path, port: int, lang: str, prefix_path: str, parent=None):
        super().__init__(parent)
        self._args = (project_dir, port, lang, prefix_path)

    def run(self) -> None:
        project_dir, port, lang, prefix_path = self._args
        try:
            tool_launcher.run_setup(project_dir, port, lang, self.line.emit, prefix_path)
        except tool_launcher.ToolMissingError:
            self.finished_ok.emit(False, t("cp_tool_missing"))
        except Exception as exc:  # shown in the panel's log, never a crash dialog
            self.finished_ok.emit(False, str(exc) or exc.__class__.__name__)
        else:
            self.finished_ok.emit(True, "")


class ControlPanel(QDialog):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin           # DevBridgePlugin: owns the two bridge objects
        self._i18n: list = []          # (callable(str), key) pairs re-applied on language change
        self._worker: _SetupWorker | None = None
        self._plugin_dirs: list[Path] = []
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self._lang_label = QLabel()
        self._bind(self._lang_label.setText, "cp_language")
        self.lang_box = QComboBox()
        self.lang_box.addItem("English", "en")
        self.lang_box.addItem("ქართული", "ka")
        self.lang_box.setCurrentIndex(max(0, self.lang_box.findData(i18n_util.get_lang())))
        self.lang_box.currentIndexChanged.connect(self._on_lang_change)
        top.addWidget(self._lang_label)
        top.addWidget(self.lang_box)
        top.addStretch(1)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_vscode_tab(), "")
        self.tabs.addTab(self._build_pycharm_tab(), "")
        self.tabs.addTab(self._build_project_tab(), "")
        self.tabs.addTab(self._build_tool_tab(), "")
        layout.addWidget(self.tabs)

        close = QPushButton()
        self._bind(close.setText, "cp_close")
        close.clicked.connect(self.close)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)

        self._retranslate()
        self._refresh_status()
        self._load_plugins()

    # --- helpers ------------------------------------------------------------
    def _bind(self, setter, key: str) -> None:
        self._i18n.append((setter, key))

    def _button(self, key: str, slot) -> QPushButton:
        btn = QPushButton()
        self._bind(btn.setText, key)
        btn.clicked.connect(slot)
        return btn

    def _retranslate(self) -> None:
        self.setWindowTitle(t("cp_title"))
        for setter, key in self._i18n:
            setter(t(key))
        for i, key in enumerate(("cp_tab_vscode", "cp_tab_pycharm", "cp_tab_project", "cp_tab_tool")):
            self.tabs.setTabText(i, t(key))
        self._refresh_status()

    def _on_lang_change(self) -> None:
        lang = self.lang_box.currentData()
        i18n_util.set_lang(lang)
        self.plugin.remember_lang(lang)
        self._retranslate()

    # --- VS Code tab ------------------------------------------------------
    def _build_vscode_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        info = QLabel()
        info.setWordWrap(True)
        self._bind(info.setText, "cp_vscode_info")
        lay.addWidget(info)

        form = QFormLayout()
        self.vs_host = QLineEdit(self.plugin.bridge.host)
        self.vs_port = QSpinBox()
        self.vs_port.setRange(1024, 65535)
        self.vs_port.setValue(self.plugin.bridge.port)
        host_lbl, port_lbl = QLabel(), QLabel()
        self._bind(host_lbl.setText, "settings_host_label")
        self._bind(port_lbl.setText, "settings_port_label")
        form.addRow(host_lbl, self.vs_host)
        form.addRow(port_lbl, self.vs_port)
        lay.addLayout(form)

        self.vs_status = QLabel()
        lay.addWidget(self.vs_status)
        row = QHBoxLayout()
        self.vs_start = self._button("menu_start_bridge", self._start_vscode)
        self.vs_stop = self._button("menu_stop_bridge", self._stop_vscode)
        row.addWidget(self.vs_start)
        row.addWidget(self.vs_stop)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _apply_vscode_settings(self) -> None:
        if not self.plugin.bridge.is_running:
            self.plugin.bridge.host = self.vs_host.text().strip() or self.plugin.bridge.host
            self.plugin.bridge.port = self.vs_port.value()
            self.plugin.persist_settings()

    def _start_vscode(self) -> None:
        self._apply_vscode_settings()
        self.plugin._on_start_bridge()
        self._refresh_status()

    def _stop_vscode(self) -> None:
        self.plugin._on_stop_bridge()
        self._refresh_status()

    # --- PyCharm tab --------------------------------------------------------
    def _build_pycharm_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        info = QLabel()
        info.setWordWrap(True)
        self._bind(info.setText, "cp_pycharm_info")
        lay.addWidget(info)

        form = QFormLayout()
        self.py_host = QLineEdit(self.plugin.pycharm_bridge.host)
        self.py_port = QSpinBox()
        self.py_port.setRange(1024, 65535)
        self.py_port.setValue(self.plugin.pycharm_bridge.port)
        host_lbl, port_lbl = QLabel(), QLabel()
        self._bind(host_lbl.setText, "settings_host_label")
        self._bind(port_lbl.setText, "settings_port_label")
        form.addRow(host_lbl, self.py_host)
        form.addRow(port_lbl, self.py_port)
        lay.addLayout(form)

        self.py_status = QLabel()
        lay.addWidget(self.py_status)
        row = QHBoxLayout()
        row.addWidget(self._button("menu_pycharm_auto", self._start_pycharm))
        row.addWidget(self._button("menu_pycharm_stop", self._stop_pycharm))
        row.addWidget(self._button("menu_pycharm_help", self.plugin._on_pycharm_help))
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _start_pycharm(self) -> None:
        if not self.plugin.pycharm_bridge.is_running:
            self.plugin.pycharm_bridge.host = self.py_host.text().strip() or self.plugin.pycharm_bridge.host
            self.plugin.pycharm_bridge.port = self.py_port.value()
            self.plugin.persist_settings()
        QgsApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)   # may pip-install pydevd-pycharm
        try:
            self.plugin._on_pycharm_auto()
        finally:
            QgsApplication.restoreOverrideCursor()
        self._refresh_status()

    def _stop_pycharm(self) -> None:
        self.plugin._on_pycharm_stop()
        self._refresh_status()

    # --- project tab --------------------------------------------------------
    def _build_project_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        info = QLabel()
        info.setWordWrap(True)
        self._bind(info.setText, "cp_project_info")
        lay.addWidget(info)

        row = QHBoxLayout()
        self.plugin_combo = QComboBox()
        self.plugin_combo.setMinimumWidth(240)
        self.plugin_combo.currentIndexChanged.connect(self._on_plugin_pick)
        row.addWidget(self.plugin_combo, 1)
        row.addWidget(self._button("cp_refresh", self._load_plugins))
        lay.addLayout(row)

        row = QHBoxLayout()
        self.project_edit = QLineEdit()
        row.addWidget(self.project_edit, 1)
        row.addWidget(self._button("cp_browse", self._browse))
        lay.addLayout(row)

        row = QHBoxLayout()
        self.prepare_btn = self._button("cp_prepare", self._prepare)
        row.addWidget(self.prepare_btn)
        row.addWidget(self._button("cp_open_folder", self._open_project_folder))
        row.addWidget(self._button("cp_open_vscode", self._open_project_vscode))
        row.addStretch(1)
        lay.addLayout(row)

        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setTextVisible(False)
        self.busy.hide()
        lay.addWidget(self.busy)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(140)
        lay.addWidget(self.log)
        return w

    def _profile_dir(self) -> Path:
        return Path(QgsApplication.qgisSettingsDirPath())

    def _load_plugins(self) -> None:
        self._plugin_dirs = profile_plugins.list_plugins(self._profile_dir())
        self.plugin_combo.blockSignals(True)
        self.plugin_combo.clear()
        for p in self._plugin_dirs:
            self.plugin_combo.addItem(p.name)
        self.plugin_combo.blockSignals(False)
        if self._plugin_dirs and not self.project_edit.text():
            self.plugin_combo.setCurrentIndex(0)
            self._on_plugin_pick()

    def _on_plugin_pick(self) -> None:
        idx = self.plugin_combo.currentIndex()
        if 0 <= idx < len(self._plugin_dirs):
            self.project_edit.setText(str(self._plugin_dirs[idx]))

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, t("cp_browse_title"), self.project_edit.text())
        if chosen:
            self.project_edit.setText(chosen)

    def _project_path(self) -> Path | None:
        raw = self.project_edit.text().strip()
        if not raw or not Path(raw).is_dir():
            QMessageBox.warning(self, "DevBridge", t("cp_project_missing"))
            return None
        return Path(raw)

    def _prepare(self) -> None:
        path = self._project_path()
        if path is None or self._worker is not None:
            return
        self._apply_vscode_settings()
        self.log.clear()
        self.prepare_btn.setEnabled(False)
        self.busy.show()
        self._worker = _SetupWorker(path, self.vs_port.value(), i18n_util.get_lang(),
                                    QgsApplication.prefixPath(), self)
        self._worker.line.connect(self.log.appendPlainText)
        self._worker.finished_ok.connect(self._prepare_done)
        self._worker.start()

    def _prepare_done(self, ok: bool, error: str) -> None:
        self.busy.hide()
        self.prepare_btn.setEnabled(True)
        if not ok:
            self.log.appendPlainText(f"ERROR: {error}")
        self._worker = None

    def _open_project_folder(self) -> None:
        path = self._project_path()
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_project_vscode(self) -> None:
        path = self._project_path()
        if path and not tool_launcher.open_in_vscode(path):
            QMessageBox.information(self, "DevBridge", t("cp_vscode_missing"))

    # --- desktop tool tab ---------------------------------------------------
    def _build_tool_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        info = QLabel()
        info.setWordWrap(True)
        self._bind(info.setText, "cp_tool_info")
        lay.addWidget(info)
        row = QHBoxLayout()
        row.addWidget(self._button("cp_launch_gui", self._launch_gui))
        row.addWidget(self._button("cp_open_tool_folder", self._open_tool_folder))
        row.addStretch(1)
        lay.addLayout(row)
        self.settings_lbl = QLabel()
        self.settings_lbl.setWordWrap(True)
        self.settings_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.settings_lbl)
        lay.addStretch(1)
        return w

    def _launch_gui(self) -> None:
        QgsApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)   # first call probes for a Python with Tk
        try:
            tool_launcher.launch_gui()
        except tool_launcher.ToolMissingError:
            QMessageBox.warning(self, "DevBridge", t("cp_tool_missing"))
        except tool_launcher.NoTkError:
            QMessageBox.warning(self, "DevBridge", t("cp_no_tk"))
        except OSError as exc:
            QMessageBox.warning(self, "DevBridge", str(exc))
        finally:
            QgsApplication.restoreOverrideCursor()

    def _open_tool_folder(self) -> None:
        folder = tool_launcher.folder_to_open()
        if folder is None:
            QMessageBox.warning(self, "DevBridge", t("cp_tool_missing"))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # --- status -------------------------------------------------------------
    def _refresh_status(self) -> None:
        b, p = self.plugin.bridge, self.plugin.pycharm_bridge
        self.vs_status.setText(
            t("cp_status_running", host=b.host, port=b.port) if b.is_running else t("cp_status_stopped"))
        self.py_status.setText(
            t("cp_status_running", host=p.host, port=p.port) if p.is_running else t("cp_status_stopped"))
        self.vs_host.setEnabled(not b.is_running)
        self.vs_port.setEnabled(not b.is_running)
        self.py_host.setEnabled(not p.is_running)
        self.py_port.setEnabled(not p.is_running)
        self.settings_lbl.setText(t("cp_settings_file", path=shared_config.config_path()))
