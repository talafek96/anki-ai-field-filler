"""Model settings tab for the settings dialog."""

from __future__ import annotations

import os
import threading
from typing import List, Optional

from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, tooltip

from ...core.config import Config
from ...core.factory import fetch_available_models
from ..common.icons import get_themed_icon

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

    def __init__(
        self, placeholder: str = "", tool_tip: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._combo = _AutoFetchCombo()
        self._combo.setEditable(True)
        self._combo.lineEdit().setPlaceholderText(placeholder)
        self._combo.setToolTip(tool_tip)
        self._combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._combo.popupAboutToShow.connect(self._on_popup)
        lay.addWidget(self._combo)

        self._refresh_btn = QToolButton()
        self._refresh_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
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
        self._setup_ui()
        self.load()

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

        # --- 1. Text Generation ---
        text_group = QGroupBox("Text Generation")
        tf = QFormLayout()
        tf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        tf.setHorizontalSpacing(12)
        tf.setVerticalSpacing(8)

        # Provider selection for Text
        self._active_text_combo = QComboBox()
        self._setup_provider_combo(self._active_text_combo, "text")
        qconnect(
            self._active_text_combo.currentIndexChanged,
            lambda: self._load_capability_settings("text"),
        )
        tf.addRow("Text Provider:", self._active_text_combo)

        # Model selection for Text
        self._text_model_combo = ModelComboWithRefresh(
            placeholder="e.g. gpt-4o",
            tool_tip="Model for text generation. Click refresh to load from API.",
        )
        qconnect(
            self._text_model_combo.modelsRequested, lambda: self._fetch_models("text")
        )
        qconnect(
            self._text_model_combo.refreshButton().clicked,
            lambda: self._fetch_models("text"),
        )
        tf.addRow("Model ID:", self._text_model_combo)

        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(128, 65536)
        self._max_tokens_spin.setSingleStep(256)
        tf.addRow("Max Tokens:", self._max_tokens_spin)
        text_group.setLayout(tf)
        layout.addWidget(text_group)

        # --- 2. TTS ---
        self._tts_group = QGroupBox("TTS")
        tsf = QFormLayout()
        tsf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        tsf.setHorizontalSpacing(12)
        tsf.setVerticalSpacing(8)

        # Provider selection for TTS
        self._active_tts_combo = QComboBox()
        self._setup_provider_combo(self._active_tts_combo, "tts")
        qconnect(
            self._active_tts_combo.currentIndexChanged,
            lambda: self._load_capability_settings("tts"),
        )
        tsf.addRow("TTS Provider:", self._active_tts_combo)

        # Model selection for TTS
        self._tts_model_combo = ModelComboWithRefresh(
            placeholder="e.g. tts-1", tool_tip="Model for speech generation."
        )
        qconnect(
            self._tts_model_combo.modelsRequested, lambda: self._fetch_models("tts")
        )
        qconnect(
            self._tts_model_combo.refreshButton().clicked,
            lambda: self._fetch_models("tts"),
        )
        tsf.addRow("Model ID:", self._tts_model_combo)

        self._tts_voice_combo = QComboBox()
        self._tts_voice_combo.setEditable(True)
        tsf.addRow("Voice:", self._tts_voice_combo)
        self._tts_group.setLayout(tsf)
        layout.addWidget(self._tts_group)

        # --- 3. Image Generation ---
        self._image_group = QGroupBox("Image Generation")
        imf = QFormLayout()
        imf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        imf.setHorizontalSpacing(12)
        imf.setVerticalSpacing(8)

        # Provider selection for Image
        self._active_image_combo = QComboBox()
        self._setup_provider_combo(self._active_image_combo, "image")
        qconnect(
            self._active_image_combo.currentIndexChanged,
            lambda: self._load_capability_settings("image"),
        )
        imf.addRow("Image Provider:", self._active_image_combo)

        # Model selection for Image
        self._image_model_combo = ModelComboWithRefresh(
            placeholder="e.g. dall-e-3", tool_tip="Model for image generation."
        )
        qconnect(
            self._image_model_combo.modelsRequested, lambda: self._fetch_models("image")
        )
        qconnect(
            self._image_model_combo.refreshButton().clicked,
            lambda: self._fetch_models("image"),
        )
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
            caps = PROVIDER_CAPABILITIES.get(ptype, {})

            # Check if provider supports the capability
            if capability != "text" and not caps.get(capability):
                continue

            icon_file = provider_icons.get(ptype)
            if icon_file:
                icon_path = os.path.join(icons_dir, icon_file)
                combo.addItem(
                    get_themed_icon(icon_path, 18, should_tint=False), label, ptype
                )
            else:
                combo.addItem(label, ptype)

        if capability in ("tts", "image"):
            combo.addItem("Disabled", "disabled")

    def _load_capability_settings(self, capability: str) -> None:
        """Load specific settings for a capability when its provider changes."""
        combo_map = {
            "text": self._active_text_combo,
            "tts": self._active_tts_combo,
            "image": self._active_image_combo,
        }
        ptype = combo_map[capability].currentData()

        # If disabled for multi-capability groups (TTS/Image)
        is_disabled = not ptype or ptype == "disabled"

        if capability == "text":
            self._text_model_combo.setEnabled(not is_disabled)
            self._max_tokens_spin.setEnabled(not is_disabled)
        elif capability == "tts":
            # We keep groups visible but disable contents
            self._tts_model_combo.setEnabled(not is_disabled)
            self._tts_voice_combo.setEnabled(not is_disabled)
        elif capability == "image":
            self._image_model_combo.setEnabled(not is_disabled)

        if is_disabled:
            return

        cfg = self._config.get_provider_config(ptype)
        cached = self._config.get_all_cached_models(ptype)

        if capability == "text":
            self._text_model_combo.setModels(cached.get("text", []))
            self._text_model_combo.setCurrentText(cfg.text_model)
            self._max_tokens_spin.setValue(cfg.max_tokens)
        elif capability == "tts":
            self._tts_model_combo.setModels(cached.get("tts", []))
            self._tts_model_combo.setCurrentText(cfg.tts_model)
            self._tts_voice_combo.clear()
            self._tts_voice_combo.setEditText(cfg.tts_voice or "")
        elif capability == "image":
            self._image_group.setVisible(True)
            self._image_model_combo.setModels(cached.get("image", []))
            self._image_model_combo.setCurrentText(cfg.image_model)

    def _save_all_configs(self) -> None:
        """Save settings for all currently selected providers."""
        for cap in ["text", "tts", "image"]:
            combo_map = {
                "text": self._active_text_combo,
                "tts": self._active_tts_combo,
                "image": self._active_image_combo,
            }
            ptype = combo_map[cap].currentData()
            if not ptype or ptype == "disabled":
                continue

            existing = self._config.get_provider_config(ptype)

            # We only update the fields relevant to the current capability group's UI
            # to avoid overwriting other fields if multiple caps use the same provider.
            if cap == "text":
                existing.text_model = self._text_model_combo.currentText().strip()
                existing.max_tokens = self._max_tokens_spin.value()
            elif cap == "tts":
                existing.tts_model = self._tts_model_combo.currentText().strip()
                existing.tts_voice = self._tts_voice_combo.currentText().strip()
            elif cap == "image":
                existing.image_model = self._image_model_combo.currentText().strip()

            self._config.set_provider_config(ptype, existing)

    def _fetch_models(self, capability: str) -> None:
        combo_map = {
            "text": self._active_text_combo,
            "tts": self._active_tts_combo,
            "image": self._active_image_combo,
        }
        ptype = combo_map[capability].currentData()
        if not ptype or ptype == "disabled":
            return

        cfg = self._config.get_provider_config(ptype)
        if not cfg.api_key:
            showInfo(
                f"Please configure an API key for {PROVIDER_LABELS.get(ptype, ptype)} in the General tab first.",
                title="AI Filler",
            )
            return

        ui_combo_map = {
            "text": self._text_model_combo,
            "tts": self._tts_model_combo,
            "image": self._image_model_combo,
        }
        target = ui_combo_map.get(capability)
        if not target:
            return

        target.setRefreshing(True)

        def do_fetch() -> None:
            try:
                models = fetch_available_models(cfg, capability)
                mw.taskman.run_on_main(
                    lambda: self._on_models_fetched(
                        ptype, capability, target, models, None
                    )
                )
            except Exception as e:
                err_msg = str(e)
                mw.taskman.run_on_main(
                    lambda: self._on_models_fetched(
                        ptype, capability, target, [], err_msg
                    )
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
            self._config.set_cached_models(ptype, capability, models)
            combo.setModels(models)
            tooltip(f"Loaded {len(models)} model(s).", parent=self)
        else:
            tooltip("No models found.", parent=self)

    def load(self) -> None:
        """Load active provider choices and their settings."""
        # Block signals briefly to avoid multiple redundant loads
        self._active_text_combo.blockSignals(True)
        self._active_tts_combo.blockSignals(True)
        self._active_image_combo.blockSignals(True)

        for combo, cap in [
            (self._active_text_combo, "text"),
            (self._active_tts_combo, "tts"),
            (self._active_image_combo, "image"),
        ]:
            active = self._config.get_active_provider_type(cap)
            idx = combo.findData(active)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                # Default to index 0 or disabled
                if cap in ("tts", "image"):
                    d_idx = combo.findData("disabled")
                    if d_idx >= 0:
                        combo.setCurrentIndex(d_idx)
                else:
                    combo.setCurrentIndex(0)

        self._active_text_combo.blockSignals(False)
        self._active_tts_combo.blockSignals(False)
        self._active_image_combo.blockSignals(False)

        # Initial load of all capability settings
        self._load_capability_settings("text")
        self._load_capability_settings("tts")
        self._load_capability_settings("image")

    def save(self) -> None:
        """Save both specific model settings and active provider choices."""
        self._save_all_configs()
        self._config.set_active_provider_type(
            "text", self._active_text_combo.currentData()
        )
        self._config.set_active_provider_type(
            "tts", self._active_tts_combo.currentData()
        )
        self._config.set_active_provider_type(
            "image", self._active_image_combo.currentData()
        )
