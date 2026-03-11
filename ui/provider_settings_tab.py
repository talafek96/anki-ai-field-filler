"""Provider settings tab for the settings dialog."""

from __future__ import annotations

import threading

from aqt.qt import *
from aqt.utils import showInfo, tooltip

from ..config_manager import ConfigManager, ProviderConfig
from ..providers import test_provider_connection

PROVIDER_CAPABILITIES = {
    "openai": {"text": True, "tts": True, "image": True},
    "anthropic": {"text": True, "tts": False, "image": False},
    "google": {"text": True, "tts": False, "image": False},
}

PROVIDER_LABELS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google (Gemini)",
}


class ProviderSettingsTab(QWidget):
    """Tab for configuring AI provider credentials and model settings."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._current_provider = "openai"
        self._setup_ui()
        self._load_provider("openai")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # --- Provider selector ---
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Configure Provider:"))
        self._provider_combo = QComboBox()
        for ptype in self._config.get_all_provider_types():
            self._provider_combo.addItem(
                PROVIDER_LABELS.get(ptype, ptype), ptype
            )
        qconnect(
            self._provider_combo.currentIndexChanged, self._on_provider_changed
        )
        selector_layout.addWidget(self._provider_combo)
        selector_layout.addStretch()
        layout.addLayout(selector_layout)

        # --- Connection group ---
        conn_group = QGroupBox("Connection")
        conn_layout = QFormLayout()
        conn_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://api.openai.com/v1")
        self._url_edit.setToolTip(
            "Base URL for the provider's API.\n"
            "Change this to use Azure OpenAI, local LLMs, or other "
            "compatible endpoints."
        )
        conn_layout.addRow("API URL:", self._url_edit)

        key_layout = QHBoxLayout()
        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText("Enter your API key")
        key_layout.addWidget(self._key_edit)
        self._show_key_btn = QPushButton("Show")
        self._show_key_btn.setFixedWidth(60)
        self._show_key_btn.setCheckable(True)
        qconnect(self._show_key_btn.toggled, self._toggle_key_visibility)
        key_layout.addWidget(self._show_key_btn)
        conn_layout.addRow("API Key:", key_layout)

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setFixedWidth(150)
        self._test_btn.setToolTip(
            "Send a small test request to verify your credentials work."
        )
        qconnect(self._test_btn.clicked, self._test_connection)
        test_layout = QHBoxLayout()
        test_layout.addStretch()
        test_layout.addWidget(self._test_btn)
        conn_layout.addRow("", test_layout)

        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # --- Models group ---
        models_group = QGroupBox("Models")
        models_layout = QFormLayout()
        models_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self._text_model_edit = QLineEdit()
        self._text_model_edit.setToolTip("Model name for text generation.")
        models_layout.addRow("Text Model:", self._text_model_edit)

        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(256, 32768)
        self._max_tokens_spin.setSingleStep(256)
        self._max_tokens_spin.setToolTip(
            "Maximum number of tokens in AI responses."
        )
        models_layout.addRow("Max Tokens:", self._max_tokens_spin)

        self._tts_model_label = QLabel("TTS Model:")
        self._tts_model_edit = QLineEdit()
        self._tts_model_edit.setPlaceholderText(
            "e.g. tts-1 (leave empty to disable)"
        )
        self._tts_model_edit.setToolTip(
            "Model for text-to-speech audio generation."
        )
        models_layout.addRow(self._tts_model_label, self._tts_model_edit)

        self._tts_voice_label = QLabel("TTS Voice:")
        self._tts_voice_edit = QLineEdit()
        self._tts_voice_edit.setPlaceholderText(
            "alloy, echo, fable, onyx, nova, shimmer"
        )
        self._tts_voice_edit.setToolTip(
            "Voice to use for text-to-speech synthesis."
        )
        models_layout.addRow(self._tts_voice_label, self._tts_voice_edit)

        self._image_model_label = QLabel("Image Model:")
        self._image_model_edit = QLineEdit()
        self._image_model_edit.setPlaceholderText(
            "e.g. dall-e-3 (leave empty to disable)"
        )
        self._image_model_edit.setToolTip(
            "Model for image generation."
        )
        models_layout.addRow(self._image_model_label, self._image_model_edit)

        models_group.setLayout(models_layout)
        layout.addWidget(models_group)

        # --- Active providers group ---
        active_group = QGroupBox("Active Provider for Each Capability")
        active_layout = QFormLayout()

        self._active_text_combo = QComboBox()
        self._active_tts_combo = QComboBox()
        self._active_image_combo = QComboBox()

        for ptype in self._config.get_all_provider_types():
            label = PROVIDER_LABELS.get(ptype, ptype)
            caps = PROVIDER_CAPABILITIES.get(ptype, {})
            self._active_text_combo.addItem(label, ptype)
            if caps.get("tts"):
                self._active_tts_combo.addItem(label, ptype)
            if caps.get("image"):
                self._active_image_combo.addItem(label, ptype)

        self._active_tts_combo.addItem("Disabled", "disabled")
        self._active_image_combo.addItem("Disabled", "disabled")

        self._active_text_combo.setToolTip(
            "Which provider to use for generating text content."
        )
        self._active_tts_combo.setToolTip(
            "Which provider to use for text-to-speech audio.\n"
            "Set to Disabled if you don't need audio generation."
        )
        self._active_image_combo.setToolTip(
            "Which provider to use for image generation.\n"
            "Set to Disabled if you don't need image generation."
        )

        active_layout.addRow("Text Generation:", self._active_text_combo)
        active_layout.addRow("Text-to-Speech:", self._active_tts_combo)
        active_layout.addRow("Image Generation:", self._active_image_combo)

        active_group.setLayout(active_layout)
        layout.addWidget(active_group)

        layout.addStretch()
        self.setLayout(layout)

        self._load_active_providers()

    def _on_provider_changed(self, _index: int) -> None:
        self._save_current_provider()
        ptype = self._provider_combo.currentData()
        self._current_provider = ptype
        self._load_provider(ptype)

    def _load_provider(self, ptype: str) -> None:
        cfg = self._config.get_provider_config(ptype)
        self._url_edit.setText(cfg.api_url)
        self._key_edit.setText(cfg.api_key)
        self._text_model_edit.setText(cfg.text_model)
        self._max_tokens_spin.setValue(cfg.max_tokens)
        self._tts_model_edit.setText(cfg.tts_model)
        self._tts_voice_edit.setText(cfg.tts_voice)
        self._image_model_edit.setText(cfg.image_model)

        caps = PROVIDER_CAPABILITIES.get(ptype, {})
        has_tts = caps.get("tts", False)
        has_image = caps.get("image", False)

        for w in (self._tts_model_label, self._tts_model_edit,
                  self._tts_voice_label, self._tts_voice_edit):
            w.setVisible(has_tts)
        for w in (self._image_model_label, self._image_model_edit):
            w.setVisible(has_image)

    def _save_current_provider(self) -> None:
        ptype = self._current_provider
        cfg = ProviderConfig(
            provider_type=ptype,
            api_url=self._url_edit.text().strip(),
            api_key=self._key_edit.text().strip(),
            text_model=self._text_model_edit.text().strip(),
            max_tokens=self._max_tokens_spin.value(),
            tts_model=self._tts_model_edit.text().strip(),
            tts_voice=self._tts_voice_edit.text().strip(),
            image_model=self._image_model_edit.text().strip(),
        )
        self._config.set_provider_config(ptype, cfg)

    def _load_active_providers(self) -> None:
        for combo, capability in [
            (self._active_text_combo, "text"),
            (self._active_tts_combo, "tts"),
            (self._active_image_combo, "image"),
        ]:
            active = self._config.get_active_provider_type(capability)
            idx = combo.findData(active)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _toggle_key_visibility(self, checked: bool) -> None:
        if checked:
            self._key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._show_key_btn.setText("Hide")
        else:
            self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._show_key_btn.setText("Show")

    def _test_connection(self) -> None:
        self._save_current_provider()
        cfg = self._config.get_provider_config(self._current_provider)
        if not cfg.api_key:
            showInfo(
                "Please enter an API key first.",
                title="AI Field Filler",
            )
            return

        self._test_btn.setEnabled(False)
        self._test_btn.setText("Testing...")

        def test() -> None:
            success, message = test_provider_connection(cfg)
            from aqt import mw

            mw.taskman.run_on_main(
                lambda: self._show_test_result(success, message)
            )

        threading.Thread(target=test, daemon=True).start()

    def _show_test_result(self, success: bool, message: str) -> None:
        self._test_btn.setEnabled(True)
        self._test_btn.setText("Test Connection")
        if success:
            tooltip("Connection successful!", parent=self)
        else:
            showInfo(
                f"Connection failed:\n\n{message}",
                title="AI Field Filler",
            )

    def save(self) -> None:
        """Save all provider settings to the config manager."""
        self._save_current_provider()
        self._config.set_active_provider_type(
            "text", self._active_text_combo.currentData()
        )
        self._config.set_active_provider_type(
            "tts", self._active_tts_combo.currentData()
        )
        self._config.set_active_provider_type(
            "image", self._active_image_combo.currentData()
        )
