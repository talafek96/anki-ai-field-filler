"""Model settings tab for the settings dialog."""

from __future__ import annotations

import os
import threading
from typing import List, Optional

from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, tooltip

from ...core.config import Config, ProviderConfig
from ...core.factory import fetch_available_models

# Shared constants
PROVIDER_LABELS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "vercel": "Vercel AI Gateway",
}

PROVIDER_CAPABILITIES = {
    "openai": {"text": True, "tts": True, "image": True},
    "anthropic": {"text": True, "tts": False, "image": False},
    "google": {"text": True, "tts": True, "image": True},
    "vercel": {"text": True, "tts": True, "image": True},
}

KNOWN_TTS_VOICES = {
    "openai": [
        "alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"
    ],
    "google": [
        "Aoede", "Charon", "Fenrir", "Kore", "Puck"
    ],
}


class _AutoFetchCombo(QComboBox):
    """QComboBox that emits popupAboutToShow before showing the list."""
    popupAboutToShow = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._suppress_popup = False

    def showPopup(self) -> None:  # noqa: N802
        self._suppress_popup = False
        self.popupAboutToShow.emit()
        if not self._suppress_popup:
            super().showPopup()


class ModelComboWithRefresh(QWidget):
    """Editable combo box paired with a refresh icon button."""
    modelsRequested = pyqtSignal()

    def __init__(self, placeholder: str = "", tool_tip: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._combo = _AutoFetchCombo()
        self._combo.setEditable(True)
        self._combo.lineEdit().setPlaceholderText(placeholder)
        self._combo.setToolTip(tool_tip)
        self._combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._combo.popupAboutToShow.connect(self._on_popup)
        lay.addWidget(self._combo)

        self._refresh_btn = QToolButton()
        self._refresh_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self._refresh_btn.setToolTip("Fetch available models from the API")
        self._refresh_btn.setFixedSize(26, 26)
        lay.addWidget(self._refresh_btn)
        self.setLayout(lay)
        self._fetching = False
        self._pending_popup = False

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
        if self._pending_popup:
            self._pending_popup = False
            if self._combo.count() > 0:
                self._combo.showPopup()

    def refreshButton(self) -> QToolButton:
        return self._refresh_btn

    def setRefreshing(self, busy: bool) -> None:
        self._fetching = busy
        self._refresh_btn.setEnabled(not busy)

    def _on_popup(self) -> None:
        if self._combo.count() == 0 and not self._fetching:
            self._combo._suppress_popup = True
            self._pending_popup = True
            self.modelsRequested.emit()


class ModelSettingsTab(QWidget):
    """Tab for configuring specific models for each supported category."""

    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config
        self._current_provider = "openai"
        self._setup_ui()
        self._load_provider("openai")

    def _setup_ui(self) -> None:
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- 1. Text Models ---
        text_group = QGroupBox("Text Models")
        tf = QFormLayout()
        tf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        tf.setHorizontalSpacing(12)
        tf.setVerticalSpacing(8)

        # Provider selection for Text
        self._active_text_combo = QComboBox()
        self._setup_provider_combo(self._active_text_combo, "text")
        tf.addRow("Text Provider:", self._active_text_combo)

        # Model selection for Text
        self._text_model_combo = ModelComboWithRefresh(
            placeholder="e.g. gpt-4o",
            tool_tip="Model for text generation. Click refresh to load from API."
        )
        qconnect(self._text_model_combo.modelsRequested, lambda: self._fetch_models("text"))
        qconnect(self._text_model_combo.refreshButton().clicked, lambda: self._fetch_models("text"))
        tf.addRow("Model ID:", self._text_model_combo)

        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(128, 65536)
        self._max_tokens_spin.setSingleStep(256)
        tf.addRow("Max Tokens:", self._max_tokens_spin)
        text_group.setLayout(tf)
        layout.addWidget(text_group)

        # --- 2. Audio (TTS) ---
        self._tts_group = QGroupBox("Audio (TTS)")
        tsf = QFormLayout()
        tsf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        tsf.setHorizontalSpacing(12)
        tsf.setVerticalSpacing(8)

        # Provider selection for TTS
        self._active_tts_combo = QComboBox()
        self._setup_provider_combo(self._active_tts_combo, "tts")
        tsf.addRow("TTS Provider:", self._active_tts_combo)

        # Model selection for TTS
        self._tts_model_combo = ModelComboWithRefresh(
            placeholder="e.g. tts-1",
            tool_tip="Model for speech generation."
        )
        qconnect(self._tts_model_combo.modelsRequested, lambda: self._fetch_models("tts"))
        qconnect(self._tts_model_combo.refreshButton().clicked, lambda: self._fetch_models("tts"))
        tsf.addRow("Model ID:", self._tts_model_combo)

        self._tts_voice_combo = QComboBox()
        self._tts_voice_combo.setEditable(True)
        tsf.addRow("Voice:", self._tts_voice_combo)
        self._tts_group.setLayout(tsf)
        layout.addWidget(self._tts_group)

        # --- 3. Images ---
        self._image_group = QGroupBox("Images")
        imf = QFormLayout()
        imf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        imf.setHorizontalSpacing(12)
        imf.setVerticalSpacing(8)

        # Provider selection for Image
        self._active_image_combo = QComboBox()
        self._setup_provider_combo(self._active_image_combo, "image")
        imf.addRow("Image Provider:", self._active_image_combo)

        # Model selection for Image
        self._image_model_combo = ModelComboWithRefresh(
            placeholder="e.g. dall-e-3",
            tool_tip="Model for image generation."
        )
        qconnect(self._image_model_combo.modelsRequested, lambda: self._fetch_models("image"))
        qconnect(self._image_model_combo.refreshButton().clicked, lambda: self._fetch_models("image"))
        imf.addRow("Model ID:", self._image_model_combo)
        self._image_group.setLayout(imf)
        layout.addWidget(self._image_group)

        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)
        outer.addWidget(scroll)
        self.setLayout(outer)

    def _setup_provider_combo(self, combo: QComboBox, capability: str) -> None:
        """Helper to populate a provider combo box with icons and labels."""
        addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        icons_dir = os.path.join(addon_dir, "assets", "icons", "providers")
        provider_icons = {
            "openai": "openai.svg",
            "anthropic": "claude.svg",
            "google": "gemini.svg",
            "vercel": "vercel.svg",
        }

        for ptype in self._config.get_all_provider_types():
            label = PROVIDER_LABELS.get(ptype, ptype)
            caps = PROVIDER_CAPABILITIES.get(ptype, {})
            
            # Check if provider supports the capability
            if capability != "text" and not caps.get(capability):
                continue
                
            icon_file = provider_icons.get(ptype)
            if icon_file:
                icon_path = os.path.join(icons_dir, icon_file)
                combo.addItem(QIcon(icon_path), label, ptype)
            else:
                combo.addItem(label, ptype)

        if capability in ("tts", "image"):
            combo.addItem("Disabled", "disabled")

    def set_current_provider(self, ptype: str) -> None:
        self._save_current_provider()
        self._current_provider = ptype
        self._load_provider(ptype)

    def _load_provider(self, ptype: str) -> None:
        cfg = self._config.get_provider_config(ptype)
        self._max_tokens_spin.setValue(cfg.max_tokens)

        # Restore cached models
        cached = self._config.get_all_cached_models(ptype)
        self._text_model_combo.setModels(cached.get("text", []))
        self._tts_model_combo.setModels(cached.get("tts", []))
        self._image_model_combo.setModels(cached.get("image", []))

        self._text_model_combo.setCurrentText(cfg.text_model)
        self._tts_model_combo.setCurrentText(cfg.tts_model)
        self._image_model_combo.setCurrentText(cfg.image_model)

        self._tts_voice_combo.clear()
        voices = KNOWN_TTS_VOICES.get(ptype, [])
        if voices:
            self._tts_voice_combo.addItems(voices)
        self._tts_voice_combo.setEditText(cfg.tts_voice or "")

        # Visibility based on capabilities
        caps = PROVIDER_CAPABILITIES.get(ptype, {})
        self._tts_group.setVisible(caps.get("tts", False))
        self._image_group.setVisible(caps.get("image", False))

    def _save_current_provider(self) -> None:
        ptype = self._current_provider
        existing = self._config.get_provider_config(ptype)
        cfg = ProviderConfig(
            provider_type=ptype,
            api_url=existing.api_url,
            api_key=existing.api_key,
            text_model=self._text_model_combo.currentText().strip(),
            max_tokens=self._max_tokens_spin.value(),
            tts_model=self._tts_model_combo.currentText().strip(),
            tts_voice=self._tts_voice_combo.currentText().strip(),
            image_model=self._image_model_combo.currentText().strip(),
        )
        self._config.set_provider_config(ptype, cfg)

    def _fetch_models(self, capability: str) -> None:
        self._save_current_provider()
        ptype = self._current_provider
        cfg = self._config.get_provider_config(ptype)
        if not cfg.api_key:
            showInfo("Please configure an API key in the General tab first.", title="AI Filler")
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
                mw.taskman.run_on_main(
                    lambda: self._on_models_fetched(ptype, capability, target, [], str(e))
                )

        threading.Thread(target=do_fetch, daemon=True).start()

    def _on_models_fetched(self, ptype: str, capability: str, combo: ModelComboWithRefresh, models: List[str], error: Optional[str]) -> None:
        combo.setRefreshing(False)
        if error:
            tooltip(f"Failed to fetch models: {error}", parent=self)
        elif models:
            self._config.set_cached_models(ptype, capability, models)
            combo.setModels(models)
            tooltip(f"Loaded {len(models)} model(s).", parent=self)
        else:
            tooltip("No models found.", parent=self)

    def load(self) -> None:
        """Load active provider choices."""
        for combo, cap in [
            (self._active_text_combo, "text"),
            (self._active_tts_combo, "tts"),
            (self._active_image_combo, "image"),
        ]:
            active = self._config.get_active_provider_type(cap)
            idx = combo.findData(active)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        self._load_provider(self._current_provider)

    def save(self) -> None:
        """Save both specific model settings and active provider choices."""
        self._save_current_provider()
        self._config.set_active_provider_type("text", self._active_text_combo.currentData())
        self._config.set_active_provider_type("tts", self._active_tts_combo.currentData())
        self._config.set_active_provider_type("image", self._active_image_combo.currentData())
