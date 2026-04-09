"""Main settings dialog for AI Field Filler.

Accessible from Tools -> AI Field Filler -> Settings... or from the
addon manager's Config button.
"""

from __future__ import annotations

import json

from aqt import mw
from aqt.qt import *
from aqt.utils import restoreGeom, saveGeom, showWarning, tooltip

from ..config_manager import ConfigManager
from ..settings_io import SettingsIOError, export_settings, import_settings
from .general_settings_tab import GeneralSettingsTab
from .note_type_settings_tab import NoteTypeSettingsTab
from .provider_settings_tab import ProviderSettingsTab
from .styles import GLOBAL_STYLE

_FILE_FILTER = "AI Field Filler Settings (*.aiff-settings);;All Files (*)"


class SettingsDialog(QDialog):
    """Main settings dialog with tabs for providers, note types, and general."""

    _GEOM_KEY = "ai_field_filler_settings"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent or mw)
        self._config = ConfigManager()
        self._setup_ui()
        restoreGeom(self, self._GEOM_KEY, adjustSize=True)

    def _setup_ui(self) -> None:
        self.setWindowTitle("AI Field Filler \u2014 Settings")
        self.setMinimumSize(740, 540)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setStyleSheet(GLOBAL_STYLE())

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Tabs ---
        self._tabs = QTabWidget()

        self._provider_tab = ProviderSettingsTab(self._config)
        self._note_type_tab = NoteTypeSettingsTab(self._config)
        self._general_tab = GeneralSettingsTab(self._config)

        self._tabs.addTab(self._provider_tab, "\U0001f916  AI Providers")
        self._tabs.addTab(self._note_type_tab, "\U0001f4dd  Note Types")
        self._tabs.addTab(self._general_tab, "\u2699\ufe0f  General")

        layout.addWidget(self._tabs)

        # --- Bottom bar: export/import on the left, OK/Cancel on the right ---
        bottom_bar = QHBoxLayout()

        export_btn = QPushButton("Export Settings\u2026")
        export_btn.setToolTip("Save all settings to a file for backup or transfer")
        qconnect(export_btn.clicked, self._on_export)
        bottom_bar.addWidget(export_btn)

        import_btn = QPushButton("Import Settings\u2026")
        import_btn.setToolTip("Load settings from a previously exported file")
        qconnect(import_btn.clicked, self._on_import)
        bottom_bar.addWidget(import_btn)

        bottom_bar.addStretch()

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(button_box.accepted, self.accept)
        qconnect(button_box.rejected, self.reject)
        bottom_bar.addWidget(button_box)

        layout.addLayout(bottom_bar)
        self.setLayout(layout)

    # -- export / import -----------------------------------------------------

    def _ask_password(self, title: str, confirm: bool = False) -> str | None:
        """Prompt the user for a password.

        Returns the password string (possibly empty) or ``None`` if the
        user cancelled.  When *confirm* is ``True`` the password must be
        entered twice.
        """
        password, ok = QInputDialog.getText(
            self,
            title,
            "Enter a password to encrypt API keys\n(leave blank to export without encryption):"
            if not confirm
            else "Enter the password used when exporting:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return None

        if confirm or not password:
            return password

        # Ask for confirmation
        password2, ok2 = QInputDialog.getText(
            self,
            title,
            "Confirm password:",
            QLineEdit.EchoMode.Password,
        )
        if not ok2:
            return None
        if password != password2:
            showWarning("Passwords do not match.", parent=self)
            return None
        return password

    def _on_export(self) -> None:
        """Export current settings to a user-chosen file."""
        # Save current tab state first so the export reflects latest edits
        self._provider_tab.save()
        self._note_type_tab.save()
        self._general_tab.save()

        password = self._ask_password("Export Settings")
        if password is None:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Settings",
            "ai_field_filler_settings.aiff-settings",
            _FILE_FILTER,
        )
        if not path:
            return

        try:
            export_settings(
                self._config.get_exportable_config(),
                path,
                password or None,
            )
        except Exception as exc:
            showWarning(f"Export failed:\n{exc}", parent=self)
            return

        tooltip("Settings exported successfully.", parent=self)

    def _on_import(self) -> None:
        """Import settings from a user-chosen file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Settings",
            "",
            _FILE_FILTER,
        )
        if not path:
            return

        # Peek to see if encrypted
        password: str | None = None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                peek = json.load(fh)
            if peek.get("_encrypted", False):
                password = self._ask_password("Import Settings", confirm=False)
                if password is None:
                    return
        except Exception:
            pass  # let import_settings handle the error

        try:
            data = import_settings(path, password)
        except SettingsIOError as exc:
            showWarning(str(exc), parent=self)
            return
        except Exception as exc:
            showWarning(f"Import failed:\n{exc}", parent=self)
            return

        ok = QMessageBox.question(
            self,
            "Import Settings",
            "This will replace your current settings.\n"
            "Unsaved changes in this dialog will be lost.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return

        self._config.import_config(data)
        self._config.write()

        # Reload all tabs to reflect the new config
        self._reload_tabs()
        tooltip("Settings imported successfully.", parent=self)

    def _reload_tabs(self) -> None:
        """Tear down and recreate all tabs to reflect the current config."""
        current_idx = self._tabs.currentIndex()

        self._tabs.removeTab(2)
        self._tabs.removeTab(1)
        self._tabs.removeTab(0)

        self._provider_tab = ProviderSettingsTab(self._config)
        self._note_type_tab = NoteTypeSettingsTab(self._config)
        self._general_tab = GeneralSettingsTab(self._config)

        self._tabs.addTab(self._provider_tab, "\U0001f916  AI Providers")
        self._tabs.addTab(self._note_type_tab, "\U0001f4dd  Note Types")
        self._tabs.addTab(self._general_tab, "\u2699\ufe0f  General")

        if current_idx < self._tabs.count():
            self._tabs.setCurrentIndex(current_idx)

    # -- standard dialog slots -----------------------------------------------

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
