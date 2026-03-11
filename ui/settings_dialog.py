"""Main settings dialog for AI Field Filler.

Accessible from Tools → AI Field Filler → Settings... or from the
addon manager's Config button.
"""

from __future__ import annotations

from aqt.qt import *
from aqt import mw
from aqt.utils import restoreGeom, saveGeom

from ..config_manager import ConfigManager
from .provider_settings_tab import ProviderSettingsTab
from .note_type_settings_tab import NoteTypeSettingsTab
from .general_settings_tab import GeneralSettingsTab


class SettingsDialog(QDialog):
    """Main settings dialog with tabs for providers, note types, and general."""

    _GEOM_KEY = "ai_field_filler_settings"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent or mw)
        self._config = ConfigManager()
        self._setup_ui()
        restoreGeom(self, self._GEOM_KEY, adjustSize=True)

    def _setup_ui(self) -> None:
        self.setWindowTitle("AI Field Filler — Settings")
        self.setMinimumSize(720, 520)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        layout = QVBoxLayout()
        layout.setSpacing(10)

        # --- Tabs ---
        self._tabs = QTabWidget()

        self._provider_tab = ProviderSettingsTab(self._config)
        self._note_type_tab = NoteTypeSettingsTab(self._config)
        self._general_tab = GeneralSettingsTab(self._config)

        self._tabs.addTab(self._provider_tab, "AI Providers")
        self._tabs.addTab(self._note_type_tab, "Note Types")
        self._tabs.addTab(self._general_tab, "General")

        layout.addWidget(self._tabs)

        # --- Button box ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(button_box.accepted, self.accept)
        qconnect(button_box.rejected, self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def accept(self) -> None:
        self._provider_tab.save()
        self._note_type_tab.save()
        self._general_tab.save()
        self._config.write()
        saveGeom(self, self._GEOM_KEY)
        super().accept()

    def reject(self) -> None:
        saveGeom(self, self._GEOM_KEY)
        super().reject()
