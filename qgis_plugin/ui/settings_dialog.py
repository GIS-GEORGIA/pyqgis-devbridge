"""Tiny host/port settings dialog, bilingual labels via i18n_util."""
from __future__ import annotations

from qgis.PyQt.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QSpinBox, QDialogButtonBox, QVBoxLayout,
)

from ..i18n_util import t


class SettingsDialog(QDialog):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.setWindowTitle(t("settings_title"))

        self.host_edit = QLineEdit(bridge.host)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(bridge.port)

        form = QFormLayout()
        form.addRow(t("settings_host_label"), self.host_edit)
        form.addRow(t("settings_port_label"), self.port_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(t("settings_save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t("settings_cancel"))
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_save(self) -> None:
        if not self.bridge.is_running:
            self.bridge.host = self.host_edit.text().strip() or self.bridge.host
            self.bridge.port = self.port_spin.value()
        self.accept()
