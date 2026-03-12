"""Provider settings tab for the settings dialog."""

from __future__ import annotations

import threading
from typing import List, Optional

from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, tooltip

from ..config_manager import ConfigManager, ProviderConfig
from ..providers import fetch_available_models, test_provider_connection

PROVIDER_CAPABILITIES = {
    "openai": {"text": True, "tts": True, "image": True},
    "anthropic": {"text": True, "tts": False, "image": False},
    "google": {"text": True, "tts": True, "image": True},
}

PROVIDER_LABELS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google (Gemini)",
}

KNOWN_TTS_VOICES = {
    "openai": [
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "nova",
        "onyx",
        "sage",
        "shimmer",
    ],
    "google": [
        "Aoede",
        "Charon",
        "Fenrir",
        "Kore",
        "Puck",
    ],
}


class ModelComboWithRefresh(QWidget):
    """Editable combo box paired with a compact refresh icon button."""

    def __init__(
        self,
        placeholder: str = "",
        tool_tip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._combo = QComboBox()
        self._combo.setEditable(True)
        self._combo.lineEdit().setPlaceholderText(placeholder)
        self._combo.setToolTip(tool_tip)
        self._combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(self._combo)

        self._refresh_btn = QToolButton()
        self._refresh_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self._refresh_btn.setToolTip("Fetch available models from the API")
        self._refresh_btn.setIconSize(QSize(16, 16))
        self._refresh_btn.setFixedSize(26, 26)
        lay.addWidget(self._refresh_btn)

        self.setLayout(lay)

    # -- public helpers --

    def currentText(self) -> str:
        return self._combo.currentText()

    def setCurrentText(self, text: str) -> None:
        idx = self._combo.findText(text)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        else:
            self._combo.setCurrentText(text)

    def setModels(self, models: List[str]) -> None:
        current = self._combo.currentText()
        self._combo.clear()
        self._combo.addItems(models)
        if current:
            self.setCurrentText(current)

    def refreshButton(self) -> QToolButton:
        return self._refresh_btn

    def setRefreshing(self, busy: bool) -> None:
        self._refresh_btn.setEnabled(not busy)


# -----------------------------------------------------------------------


class ProviderSettingsTab(QWidget):
    """Tab for configuring AI provider credentials and model settings."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._current_provider = "openai"
        # Cache fetched models per provider: {"openai": {"text": [...], "tts": [...], ...}}
        self._model_cache: dict[str, dict[str, List[str]]] = {}
        self._setup_ui()
        self._load_provider("openai")

    # ---- layout --------------------------------------------------------

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

        # --- Provider selector ---
        sel = QHBoxLayout()
        lbl = QLabel("Configure Provider:")
        lbl.setStyleSheet("font-weight: bold;")
        sel.addWidget(lbl)
        self._provider_combo = QComboBox()
        self._provider_combo.setMinimumWidth(180)
        for ptype in self._config.get_all_provider_types():
            self._provider_combo.addItem(PROVIDER_LABELS.get(ptype, ptype), ptype)
        qconnect(
            self._provider_combo.currentIndexChanged,
            self._on_provider_changed,
        )
        sel.addWidget(self._provider_combo)
        sel.addStretch()
        layout.addLayout(sel)

        # --- Connection ---
        conn = QGroupBox("Connection")
        cf = QFormLayout()
        cf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        cf.setHorizontalSpacing(12)
        cf.setVerticalSpacing(8)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://api.openai.com/v1")
        self._url_edit.setToolTip(
            "Base URL for the provider's API.\n"
            "Change this to use Azure OpenAI, local LLMs, or other "
            "compatible endpoints."
        )
        cf.addRow("API URL:", self._url_edit)

        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText("Enter your API key")
        key_row.addWidget(self._key_edit)

        self._show_key_check = QCheckBox("Show")
        self._show_key_check.setToolTip("Toggle API key visibility")
        qconnect(self._show_key_check.toggled, self._toggle_key_visibility)
        key_row.addWidget(self._show_key_check)
        cf.addRow("API Key:", key_row)

        self._test_btn = QPushButton("  Test Connection  ")
        self._test_btn.setToolTip("Send a small test request to verify your credentials.")
        qconnect(self._test_btn.clicked, self._test_connection)
        test_row = QHBoxLayout()
        test_row.addStretch()
        test_row.addWidget(self._test_btn)
        cf.addRow("", test_row)

        conn.setLayout(cf)
        layout.addWidget(conn)

        # --- Models ---
        models = QGroupBox("Models")
        mf = QFormLayout()
        mf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        mf.setHorizontalSpacing(12)
        mf.setVerticalSpacing(8)

        self._text_model_combo = ModelComboWithRefresh(
            placeholder="e.g. gpt-4o",
            tool_tip="Model for text generation. Click the refresh icon to "
            "load available models from the API.",
        )
        qconnect(
            self._text_model_combo.refreshButton().clicked,
            lambda: self._fetch_models("text"),
        )
        mf.addRow("Text Model:", self._text_model_combo)

        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(256, 32768)
        self._max_tokens_spin.setSingleStep(256)
        self._max_tokens_spin.setToolTip("Maximum number of tokens in AI responses.")
        mf.addRow("Max Tokens:", self._max_tokens_spin)

        self._tts_model_label = QLabel("TTS Model:")
        self._tts_model_combo = ModelComboWithRefresh(
            placeholder="e.g. tts-1 (leave empty to disable)",
            tool_tip="Model for text-to-speech. Click the refresh icon to "
            "load available TTS models from the API.",
        )
        qconnect(
            self._tts_model_combo.refreshButton().clicked,
            lambda: self._fetch_models("tts"),
        )
        mf.addRow(self._tts_model_label, self._tts_model_combo)

        self._tts_voice_label = QLabel("TTS Voice:")
        self._tts_voice_combo = QComboBox()
        self._tts_voice_combo.setEditable(True)
        self._tts_voice_combo.setToolTip("Voice to use for text-to-speech synthesis.")
        mf.addRow(self._tts_voice_label, self._tts_voice_combo)

        self._image_model_label = QLabel("Image Model:")
        self._image_model_combo = ModelComboWithRefresh(
            placeholder="e.g. dall-e-3 (leave empty to disable)",
            tool_tip="Model for image generation. Click the refresh icon to "
            "load available image models from the API.",
        )
        qconnect(
            self._image_model_combo.refreshButton().clicked,
            lambda: self._fetch_models("image"),
        )
        mf.addRow(self._image_model_label, self._image_model_combo)

        models.setLayout(mf)
        layout.addWidget(models)

        # --- Active providers ---
        active = QGroupBox("Active Provider for Each Capability")
        af = QFormLayout()
        af.setHorizontalSpacing(12)
        af.setVerticalSpacing(8)

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

        self._active_text_combo.setToolTip("Which provider to use for generating text content.")
        self._active_tts_combo.setToolTip(
            "Which provider to use for text-to-speech audio.\n"
            "Set to Disabled if you don't need audio generation."
        )
        self._active_image_combo.setToolTip(
            "Which provider to use for image generation.\n"
            "Set to Disabled if you don't need image generation."
        )

        af.addRow("Text Generation:", self._active_text_combo)
        af.addRow("Text-to-Speech:", self._active_tts_combo)
        af.addRow("Image Generation:", self._active_image_combo)

        active.setLayout(af)
        layout.addWidget(active)

        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        outer.addWidget(scroll)
        self.setLayout(outer)

        self._load_active_providers()

    # ---- provider switching -------------------------------------------

    def _on_provider_changed(self, _index: int) -> None:
        self._save_current_provider()
        ptype = self._provider_combo.currentData()
        self._current_provider = ptype
        self._load_provider(ptype)

    def _load_provider(self, ptype: str) -> None:
        cfg = self._config.get_provider_config(ptype)
        self._url_edit.setText(cfg.api_url)
        self._key_edit.setText(cfg.api_key)
        self._show_key_check.setChecked(False)
        self._max_tokens_spin.setValue(cfg.max_tokens)

        # Restore cached model lists (or clear if none were fetched)
        cached = self._model_cache.get(ptype, {})
        for capability, combo in [
            ("text", self._text_model_combo),
            ("tts", self._tts_model_combo),
            ("image", self._image_model_combo),
        ]:
            combo.setModels(cached.get(capability, []))

        # Set the configured model values (may be custom / not in the list)
        self._text_model_combo.setCurrentText(cfg.text_model)
        self._tts_model_combo.setCurrentText(cfg.tts_model)
        self._image_model_combo.setCurrentText(cfg.image_model)

        # Swap voice list for this provider
        self._tts_voice_combo.clear()
        voices = KNOWN_TTS_VOICES.get(ptype, [])
        if voices:
            self._tts_voice_combo.addItems(voices)
        idx = self._tts_voice_combo.findText(cfg.tts_voice)
        if idx >= 0:
            self._tts_voice_combo.setCurrentIndex(idx)
        else:
            self._tts_voice_combo.setCurrentText(cfg.tts_voice)

        # Visibility of TTS / image rows
        caps = PROVIDER_CAPABILITIES.get(ptype, {})
        has_tts = caps.get("tts", False)
        has_image = caps.get("image", False)

        for w in (
            self._tts_model_label,
            self._tts_model_combo,
            self._tts_voice_label,
            self._tts_voice_combo,
        ):
            w.setVisible(has_tts)
        for w in (self._image_model_label, self._image_model_combo):
            w.setVisible(has_image)

    def _save_current_provider(self) -> None:
        ptype = self._current_provider
        cfg = ProviderConfig(
            provider_type=ptype,
            api_url=self._url_edit.text().strip(),
            api_key=self._key_edit.text().strip(),
            text_model=self._text_model_combo.currentText().strip(),
            max_tokens=self._max_tokens_spin.value(),
            tts_model=self._tts_model_combo.currentText().strip(),
            tts_voice=self._tts_voice_combo.currentText().strip(),
            image_model=self._image_model_combo.currentText().strip(),
        )
        self._config.set_provider_config(ptype, cfg)

    def _load_active_providers(self) -> None:
        for combo, cap in [
            (self._active_text_combo, "text"),
            (self._active_tts_combo, "tts"),
            (self._active_image_combo, "image"),
        ]:
            active = self._config.get_active_provider_type(cap)
            idx = combo.findData(active)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    # ---- model fetching -----------------------------------------------

    def _fetch_models(self, capability: str) -> None:
        self._save_current_provider()
        ptype = self._current_provider
        cfg = self._config.get_provider_config(ptype)
        if not cfg.api_key:
            showInfo(
                "Please enter an API key first.",
                title="AI Field Filler",
            )
            return

        combo_map = {
            "text": self._text_model_combo,
            "tts": self._tts_model_combo,
            "image": self._image_model_combo,
        }
        target = combo_map.get(capability)
        if not target:
            return

        target.setRefreshing(True)

        def do_fetch() -> None:
            try:
                models = fetch_available_models(cfg, capability)
                mw.taskman.run_on_main(
                    lambda: self._on_models_fetched(ptype, capability, target, models, None)
                )
            except Exception as e:
                err_msg = str(e)
                mw.taskman.run_on_main(
                    lambda: self._on_models_fetched(ptype, capability, target, [], err_msg)
                )

        threading.Thread(target=do_fetch, daemon=True).start()

    def _on_models_fetched(
        self,
        ptype: str,
        capability: str,
        combo: ModelComboWithRefresh,
        models: List[str],
        error: Optional[str],
    ) -> None:
        combo.setRefreshing(False)
        if error:
            tooltip(f"Failed to fetch models: {error}", parent=self)
        elif models:
            # Cache the results for this provider + capability
            if ptype not in self._model_cache:
                self._model_cache[ptype] = {}
            self._model_cache[ptype][capability] = models
            combo.setModels(models)
            tooltip(f"Loaded {len(models)} model(s).", parent=self)
        else:
            tooltip("No models found for this capability.", parent=self)

    # ---- key visibility -----------------------------------------------

    def _toggle_key_visibility(self, visible: bool) -> None:
        self._key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )

    # ---- connection test ----------------------------------------------

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
            showInfo(
                f"Connection failed:\n\n{message}",
                title="AI Field Filler",
            )

    # ---- save ----------------------------------------------------------

    def save(self) -> None:
        self._save_current_provider()
        self._config.set_active_provider_type("text", self._active_text_combo.currentData())
        self._config.set_active_provider_type("tts", self._active_tts_combo.currentData())
        self._config.set_active_provider_type("image", self._active_image_combo.currentData())
