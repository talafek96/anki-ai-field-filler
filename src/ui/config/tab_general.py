"""General settings tab for the settings dialog."""

from __future__ import annotations

import os
import threading

from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, tooltip

from ...core.config import Config, GeneralSettings, ProviderConfig
from ...core.factory import test_provider_connection

# Shared constants (could also be imported from provider_settings_tab)
PROVIDER_LABELS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "vercel": "Vercel",
}

PROVIDER_CAPABILITIES = {
    "openai": {"text": True, "tts": True, "image": True},
    "anthropic": {"text": True, "tts": False, "image": False},
    "google": {"text": True, "tts": True, "image": True},
    "vercel": {"text": True, "tts": False, "image": False},
}


class GeneralSettingsTab(QWidget):
    """Tab for general addon settings: connection, provider, shortcuts, behavior."""

    providerChanged = pyqtSignal(str)

    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config
        self._current_provider = "openai"
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- 1. API Config ---
        self._provider_group = QGroupBox("API Config")
        prov_layout = QVBoxLayout()

        # Selector inside the group
        sel_row = QHBoxLayout()
        lbl = QLabel("Provider to Configure:")
        lbl.setStyleSheet("font-weight: bold;")
        sel_row.addWidget(lbl)
        self._provider_combo = QComboBox()
        self._provider_combo.setMinimumWidth(180)

        # Icon paths
        addon_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        icons_dir = os.path.join(addon_dir, "assets", "providers")
        provider_icons = {
            "openai": "openai.svg",
            "anthropic": "claude.svg",
            "google": "gemini.svg",
            "vercel": "vercel.svg",
        }

        for ptype in self._config.get_all_provider_types():
            label = PROVIDER_LABELS.get(ptype, ptype)
            icon_file = provider_icons.get(ptype)
            if icon_file:
                icon_path = os.path.join(icons_dir, icon_file)
                self._provider_combo.addItem(QIcon(icon_path), label, ptype)
            else:
                self._provider_combo.addItem(label, ptype)

        qconnect(self._provider_combo.currentIndexChanged, self._on_provider_changed)
        sel_row.addWidget(self._provider_combo)
        sel_row.addStretch()
        prov_layout.addLayout(sel_row)

        prov_layout.addSpacing(4)

        # Connection fields inside the same group
        cf = QFormLayout()
        cf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        cf.setHorizontalSpacing(12)
        cf.setVerticalSpacing(8)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://api.openai.com/v1")
        self._url_edit.setToolTip("Base URL for the provider's API.")
        cf.addRow("API URL:", self._url_edit)

        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText("Enter your API key")
        key_row.addWidget(self._key_edit)

        self._show_key_check = QCheckBox("Show")
        qconnect(self._show_key_check.toggled, self._toggle_key_visibility)
        key_row.addWidget(self._show_key_check)
        cf.addRow("API Key:", key_row)

        self._test_btn = QPushButton("  Test Connection  ")
        qconnect(self._test_btn.clicked, self._test_connection)
        test_row = QHBoxLayout()
        test_row.addStretch()
        test_row.addWidget(self._test_btn)
        cf.addRow("", test_row)

        prov_layout.addLayout(cf)
        self._provider_group.setLayout(prov_layout)
        layout.addWidget(self._provider_group)

        # --- 2. Keyboard Shortcuts ---
        automation_group = QGroupBox("Keyboard Shortcuts")
        auto_layout = QVBoxLayout()

        # Shortcuts row
        shortcut_layout = QFormLayout()
        self._fill_all_shortcut = QLineEdit()
        self._fill_all_shortcut.setPlaceholderText("e.g. Ctrl+Shift+G")
        shortcut_layout.addRow(
            "Fill Shortcut (opens selection dialog):", self._fill_all_shortcut
        )
        auto_layout.addLayout(shortcut_layout)

        auto_layout.addSpacing(4)

        automation_group.setLayout(auto_layout)
        layout.addWidget(automation_group)

        # --- 3. Prompt Config ---
        prompt_group = QGroupBox("Prompts")
        prompt_layout = QVBoxLayout()

        prompt_layout.addSpacing(6)

        # Fill All Prompt
        fa_lbl = QLabel("Global Prompt (prepended to AI instructions):")
        fa_lbl.setStyleSheet("color: gray; font-size: 11px;")
        prompt_layout.addWidget(fa_lbl)
        self._fill_all_prompt = QPlainTextEdit()
        self._fill_all_prompt.setMaximumHeight(60)
        prompt_layout.addWidget(self._fill_all_prompt)

        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)

        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        outer.addWidget(scroll)
        self.setLayout(outer)

    def _on_provider_changed(self, _index: int) -> None:
        self._save_current_provider()
        ptype = self._provider_combo.currentData()
        self._current_provider = ptype
        self._load_provider(ptype)
        self.providerChanged.emit(ptype)

    def _load_provider(self, ptype: str) -> None:
        cfg = self._config.get_provider_config(ptype)
        self._url_edit.setText(cfg.api_url)
        self._key_edit.setText(cfg.api_key)
        self._show_key_check.setChecked(False)

    def _save_current_provider(self) -> None:
        ptype = self._current_provider
        # We need to preserve model settings when saving connection settings
        existing = self._config.get_provider_config(ptype)
        cfg = ProviderConfig(
            provider_type=ptype,
            api_url=self._url_edit.text().strip(),
            api_key=self._key_edit.text().strip(),
            text_model=existing.text_model,
            max_tokens=existing.max_tokens,
            tts_model=existing.tts_model,
            tts_voice=existing.tts_voice,
            image_model=existing.image_model,
        )
        self._config.set_provider_config(ptype, cfg)

    def _toggle_key_visibility(self, visible: bool) -> None:
        self._key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )

    def _test_connection(self) -> None:
        self._save_current_provider()
        cfg = self._config.get_provider_config(self._current_provider)
        if not cfg.api_key:
            showInfo("Please enter an API key first.", title="AI Filler")
            return

        self._test_btn.setEnabled(False)
        self._test_btn.setText("  Testing...  ")

        def test() -> None:
            success, message = test_provider_connection(cfg)
            mw.taskman.run_on_main(lambda: self._show_test_result(success, message))

        threading.Thread(target=test, daemon=True).start()

    def _show_test_result(self, success: bool, message: str) -> None:
        self._test_btn.setEnabled(True)
        self._test_btn.setText("  Test Connection  ")
        if success:
            tooltip("Connection successful!", parent=self)
        else:
            showInfo(f"Connection failed:\n\n{message}", title="AI Filler")

    def _load(self) -> None:
        # Load general settings
        settings = self._config.get_general_settings()
        self._fill_all_shortcut.setText(settings.fill_all_shortcut)
        self._fill_all_prompt.setPlainText(settings.fill_all_prompt)

        # Load first provider
        last_p = settings.last_configured_provider
        idx = self._provider_combo.findData(last_p)
        if idx >= 0:
            self._provider_combo.setCurrentIndex(idx)
        else:
            self._load_provider("openai")

    def save(self) -> None:
        """Save general settings to the config manager."""
        self._save_current_provider()

        # Save general settings
        settings = GeneralSettings(
            fill_all_shortcut=self._fill_all_shortcut.text().strip(),
            fill_all_prompt=self._fill_all_prompt.toPlainText().strip(),
            last_configured_provider=self._provider_combo.currentData(),
        )
        self._config.set_general_settings(settings)
