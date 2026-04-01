"""General settings tab for the settings dialog."""

from __future__ import annotations

from aqt.qt import *

from ..core.config_manager import ConfigManager, GeneralSettings


class GeneralSettingsTab(QWidget):
    """Tab for general addon settings: shortcuts, prompts, behavior."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # --- Shortcuts group ---
        shortcut_group = QGroupBox("Keyboard Shortcuts")
        shortcut_layout = QFormLayout()
        shortcut_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._fill_all_shortcut = QLineEdit()
        self._fill_all_shortcut.setPlaceholderText("e.g. Ctrl+Shift+G")
        self._fill_all_shortcut.setToolTip(
            "Keyboard shortcut to fill all blank fields in the editor.\n"
            "Leave empty to disable the shortcut."
        )
        shortcut_layout.addRow("Fill All Blank Fields:", self._fill_all_shortcut)

        self._fill_field_shortcut = QLineEdit()
        self._fill_field_shortcut.setPlaceholderText("e.g. Ctrl+Shift+F")
        self._fill_field_shortcut.setToolTip(
            "Keyboard shortcut to fill the currently focused field.\n"
            "Leave empty to disable the shortcut."
        )
        shortcut_layout.addRow("Fill Current Field:", self._fill_field_shortcut)

        shortcut_group.setLayout(shortcut_layout)
        layout.addWidget(shortcut_group)

        # --- Behavior group ---
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout()

        self._show_dialog_check = QCheckBox("Show confirmation dialog before filling")
        self._show_dialog_check.setToolTip(
            "When enabled, a dialog appears letting you review which "
            "fields will be filled and add an optional prompt.\n"
            "When disabled, fields are filled immediately using the "
            "default prompt."
        )
        behavior_layout.addWidget(self._show_dialog_check)

        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)

        # --- Default prompt group ---
        prompt_group = QGroupBox("Default User Prompt")
        prompt_layout = QVBoxLayout()

        prompt_info = QLabel(
            "This prompt will be included with every AI fill request as additional context:"
        )
        prompt_info.setWordWrap(True)
        prompt_layout.addWidget(prompt_info)

        self._default_prompt = QPlainTextEdit()
        self._default_prompt.setPlaceholderText(
            "e.g. 'Use formal language' or "
            "'Target JLPT N3 level vocabulary' or "
            "'Provide example sentences in both English and Japanese'"
        )
        self._default_prompt.setMaximumHeight(100)
        prompt_layout.addWidget(self._default_prompt)

        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)

        layout.addStretch()
        self.setLayout(layout)

    def _load(self) -> None:
        settings = self._config.get_general_settings()
        self._fill_all_shortcut.setText(settings.fill_all_shortcut)
        self._fill_field_shortcut.setText(settings.fill_field_shortcut)
        self._show_dialog_check.setChecked(settings.show_fill_dialog)
        self._default_prompt.setPlainText(settings.default_user_prompt)

    def save(self) -> None:
        """Save general settings to the config manager."""
        settings = GeneralSettings(
            fill_all_shortcut=self._fill_all_shortcut.text().strip(),
            fill_field_shortcut=self._fill_field_shortcut.text().strip(),
            default_user_prompt=self._default_prompt.toPlainText().strip(),
            show_fill_dialog=self._show_dialog_check.isChecked(),
        )
        self._config.set_general_settings(settings)
