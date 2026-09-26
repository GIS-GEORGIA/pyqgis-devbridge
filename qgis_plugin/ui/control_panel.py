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
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QSpinBox,
    QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
)

from .. import i18n_util, profile_plugins, shared_config, tool_launcher
from ..i18n_util import t
from ..pycharm_bridge import PyCharmBridgeError


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


class _PyCharmWorker(QThread):
    """Detect PyCharm + install the matching pydevd-pycharm (slow) off the GUI thread;
    the connection itself must then be made on the GUI thread (it traces that thread)."""
    line = pyqtSignal(str)
    done = pyqtSignal(object, str)      # (installation | None, error key)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self._bridge = bridge

    def run(self) -> None:
        try:
            installation = self._bridge.prepare(self.line.emit)
        except PyCharmBridgeError as exc:
            self.done.emit(None, str(exc))
        except Exception as exc:
            self.done.emit(None, f"pip_failed: {exc}")
        else:
            self.done.emit(installation, "")


class ControlPanel(QDialog):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin           # DevBridgePlugin: owns the two bridge objects
        self._i18n: list = []          # (callable(str), key) pairs re-applied on language change
        self._worker: _SetupWorker | None = None
        self._py_worker: _PyCharmWorker | None = None
        self._entries: list = []
        self._just_created = False
        self.setMinimumWidth(800)

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
        self.tabs.addTab(self._build_guide_tab(), "")
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

        self._load_plugins()
        self._retranslate()
        self._refresh_status()

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
        for i, key in enumerate(("cp_tab_guide", "cp_tab_vscode", "cp_tab_pycharm", "cp_tab_project", "cp_tab_tool")):
            self.tabs.setTabText(i, t(key))
        self.plugin_combo.setItemText(0, t("cp_plugin_placeholder"))     # keep the user's pick, retitle entry 0
        self._retitle_prepare()
        self._refresh_status()

    def _on_lang_change(self) -> None:
        lang = self.lang_box.currentData()
        i18n_util.set_lang(lang)
        self.plugin.remember_lang(lang)
        self._retranslate()

    # --- guide tab ----------------------------------------------------------
    def _build_guide_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.guide = QPlainTextEdit()
        self.guide.setReadOnly(True)
        self.guide.setMinimumHeight(360)
        self._bind(self.guide.setPlainText, "cp_guide")
        lay.addWidget(self.guide)
        return w

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
        self.py_start = self._button("menu_pycharm_auto", self._start_pycharm)
        row.addWidget(self.py_start)
        row.addWidget(self._button("menu_pycharm_stop", self._stop_pycharm))
        row.addWidget(self._button("menu_pycharm_help", self.plugin._on_pycharm_help))
        row.addStretch(1)
        lay.addLayout(row)
        self.py_busy = QProgressBar()
        self.py_busy.setRange(0, 0)
        self.py_busy.setTextVisible(False)
        self.py_busy.hide()
        lay.addWidget(self.py_busy)
        self.py_log = QPlainTextEdit()
        self.py_log.setReadOnly(True)
        self.py_log.setMinimumHeight(110)
        lay.addWidget(self.py_log)
        return w

    def _start_pycharm(self) -> None:
        if not self.plugin.pycharm_bridge.is_running:
            self.plugin.pycharm_bridge.host = self.py_host.text().strip() or self.plugin.pycharm_bridge.host
            self.plugin.pycharm_bridge.port = self.py_port.value()
            self.plugin.persist_settings()
        if self._py_worker is not None or self.plugin.pycharm_bridge.is_running:
            self.plugin._on_pycharm_auto()      # reports "already running"
            return
        self.py_log.clear()
        self.py_log.appendPlainText(t("pycharm_detecting"))
        self.py_start.setEnabled(False)
        self.py_busy.show()
        self._py_worker = _PyCharmWorker(self.plugin.pycharm_bridge, self)
        self._py_worker.line.connect(self.py_log.appendPlainText)
        self._py_worker.done.connect(self._pycharm_prepared)
        self._py_worker.start()

    def _pycharm_prepared(self, installation, error: str) -> None:
        """Back on the GUI thread: report a failure, or make the connection here."""
        self.py_busy.hide()
        self.py_start.setEnabled(True)
        self._py_worker = None
        if installation is None:
            exc = PyCharmBridgeError(error)
            self.py_log.appendPlainText(self.plugin._pycharm_error_message(exc))
            self.plugin._pycharm_failed(exc)
        else:
            try:
                self.plugin.pycharm_bridge.connect(installation)
            except PyCharmBridgeError as exc:
                self.py_log.appendPlainText(self.plugin._pycharm_error_message(exc))
                self.plugin._pycharm_failed(exc)
            else:
                self.py_log.appendPlainText(t("pycharm_bridge_started", host=self.plugin.pycharm_bridge.host,
                                              port=self.plugin.pycharm_bridge.port, build=installation.build))
                self.plugin._pycharm_connected(installation)
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

        # what do you want to do?
        modes = QHBoxLayout()
        self.mode_existing = QRadioButton()
        self.mode_new = QRadioButton()
        self.mode_folder = QRadioButton()
        for radio, key in ((self.mode_existing, "cp_mode_existing"), (self.mode_new, "cp_mode_new"),
                           (self.mode_folder, "cp_mode_folder")):
            self._bind(radio.setText, key)
            radio.toggled.connect(self._show_mode)
            modes.addWidget(radio)
        modes.addStretch(1)
        lay.addLayout(modes)

        self.mode_pages = QStackedWidget()
        # 0: an existing plugin, from every QGIS profile; nothing is pre-selected
        page, page_lay = self._top_page()
        row = QHBoxLayout()
        self.plugin_combo = QComboBox()
        self.plugin_combo.setMinimumWidth(300)
        row.addWidget(self.plugin_combo, 1)
        row.addWidget(self._button("cp_refresh", self._load_plugins))
        page_lay.addLayout(row)
        page_lay.addStretch(1)
        self.mode_pages.addWidget(page)
        # 1: a new plugin
        page, page_lay = self._top_page()
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        page_lay.addLayout(form)
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("my_plugin")
        self.new_parent = QLineEdit(str(profile_plugins.new_plugin_parent(self._profile_dir())))
        name_lbl, parent_lbl = QLabel(), QLabel()
        self._bind(name_lbl.setText, "cp_new_name")
        self._bind(parent_lbl.setText, "cp_new_parent")
        parent_row = QHBoxLayout()
        parent_row.addWidget(self.new_parent, 1)
        parent_row.addWidget(self._button("cp_browse", self._browse_parent))
        form.addRow(name_lbl, self.new_name)
        form.addRow(parent_lbl, parent_row)
        page_lay.addStretch(1)
        self.mode_pages.addWidget(page)
        # 2: any folder
        page, page_lay = self._top_page()
        row = QHBoxLayout()
        self.project_edit = QLineEdit()
        row.addWidget(self.project_edit, 1)
        row.addWidget(self._button("cp_browse", self._browse))
        page_lay.addLayout(row)
        page_lay.addStretch(1)
        self.mode_pages.addWidget(page)
        self.mode_pages.setMaximumHeight(84)      # room for the two-row 'new plugin' form, no more
        lay.addWidget(self.mode_pages)

        row = QHBoxLayout()
        self.prepare_btn = QPushButton()
        self.prepare_btn.clicked.connect(self._prepare)
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
        self.mode_existing.setChecked(True)      # last: this fires _show_mode, which needs the widgets above
        return w

    @staticmethod
    def _top_page():
        """A stacked-widget page whose content sits at the top instead of floating in the middle."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 4, 0, 0)
        return page, lay

    def _profile_dir(self) -> Path:
        return Path(QgsApplication.qgisSettingsDirPath())

    def _mode(self) -> str:
        return "new" if self.mode_new.isChecked() else "folder" if self.mode_folder.isChecked() else "existing"

    def _show_mode(self, *_args) -> None:
        mode = self._mode()
        self.mode_pages.setCurrentIndex({"existing": 0, "new": 1, "folder": 2}[mode])
        self._retitle_prepare()

    def _retitle_prepare(self) -> None:
        self.prepare_btn.setText(t("cp_create_prepare" if self._mode() == "new" else "cp_prepare"))

    def _load_plugins(self) -> None:
        """Every plugin of every QGIS profile (the running one first). Entry 0 is a placeholder,
        so nothing is chosen until the user picks."""
        self._entries = profile_plugins.list_all(self._profile_dir())
        self.plugin_combo.clear()
        self.plugin_combo.addItem(t("cp_plugin_placeholder"))
        for entry in self._entries:
            self.plugin_combo.addItem(entry.label)
        self.plugin_combo.setCurrentIndex(0)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, t("cp_browse_title"), self.project_edit.text())
        if chosen:
            self.project_edit.setText(chosen)

    def _browse_parent(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, t("cp_browse_title"), self.new_parent.text())
        if chosen:
            self.new_parent.setText(chosen)

    def _target_path(self, create: bool = False) -> Path | None:
        """The folder the buttons act on; `create=True` also writes a new plugin's starter files."""
        mode = self._mode()
        if mode == "existing":
            idx = self.plugin_combo.currentIndex() - 1
            if not 0 <= idx < len(self._entries):
                QMessageBox.warning(self, "DevBridge", t("cp_choose_plugin_first"))
                return None
            return self._entries[idx].path
        if mode == "new":
            name, parent = self.new_name.text().strip(), Path(self.new_parent.text().strip())
            if not create:
                path = parent / name
                if not name or not path.is_dir():
                    QMessageBox.warning(self, "DevBridge", t("cp_new_not_created_yet"))
                    return None
                return path
            try:
                path = tool_launcher.create_plugin(parent, name)
            except tool_launcher.ToolMissingError:
                QMessageBox.warning(self, "DevBridge", t("cp_tool_missing"))
                return None
            except ValueError as exc:                        # ScaffoldError
                QMessageBox.warning(self, "DevBridge", t("cp_new_" + str(exc), name=name, path=parent))
                return None
            except OSError as exc:
                QMessageBox.warning(self, "DevBridge", str(exc))
                return None
            self.log.appendPlainText(t("cp_new_created", path=path))
            self._just_created = True
            return path
        raw = self.project_edit.text().strip()
        if not raw or not Path(raw).is_dir():
            QMessageBox.warning(self, "DevBridge", t("cp_project_missing"))
            return None
        return Path(raw)

    def _prepare(self) -> None:
        if self._worker is not None:
            return
        self._just_created = False
        self.log.clear()
        path = self._target_path(create=self._mode() == "new")
        if path is None:
            return
        self._apply_vscode_settings()
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
            self.log.appendPlainText("ERROR: " + error)
        elif self._just_created:
            self.log.appendPlainText(t("cp_new_next"))
        self._worker = None

    def _open_project_folder(self) -> None:
        path = self._target_path()
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_project_vscode(self) -> None:
        path = self._target_path()
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
