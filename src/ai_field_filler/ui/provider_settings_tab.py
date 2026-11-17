"""Provider settings tab for the settings dialog."""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Tuple

from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, tooltip

from ..config.config_manager import ConfigManager, ProviderConfig
from ..providers import (
    fetch_available_models,
    test_image_connection,
    test_provider_connection,
    test_tts_connection,
)
from .error_dialog import show_error
from .provider_icons import provider_icon

PROVIDER_CAPABILITIES = {
    "openai": {"text": True, "tts": True, "image": True},
    "anthropic": {"text": True, "tts": False, "image": False},
    "google": {"text": True, "tts": True, "image": True},
    "openrouter": {"text": True, "tts": True, "image": True},
}

PROVIDER_LABELS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google (Gemini)",
    "openrouter": "OpenRouter (all vendors)",
}

KNOWN_TTS_VOICES = {
    # OpenRouter serves speech through OpenAI's gpt-audio models, which
    # reject an unknown or empty voice, so the list must be exact.
    "openrouter": [
        "alloy",
        "ash",
        "ballad",
        "cedar",
        "coral",
        "echo",
        "fable",
        "marin",
        "nova",
        "onyx",
        "sage",
        "shimmer",
        "verse",
    ],
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


class _AutoFetchCombo(QComboBox):
    """``QComboBox`` that emits *popupAboutToShow* before showing the list.

    If a signal handler sets :attr:`_suppress_popup` to ``True``, the
    popup is *not* opened — the caller is expected to open it later
    (e.g. after an async model fetch completes).
    """

    popupAboutToShow = pyqtSignal()  # noqa: N815 — Qt signal, camelCase by convention

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._suppress_popup = False

    def showPopup(self) -> None:
        self._suppress_popup = False
        self.popupAboutToShow.emit()
        if not self._suppress_popup:
            super().showPopup()


class ModelComboWithRefresh(QWidget):
    """Editable combo box paired with a compact refresh icon button.

    Emits :pyqt:`modelsRequested` the first time the user opens the
    dropdown when it contains no items, so the parent can trigger an
    auto-fetch.
    """

    modelsRequested = pyqtSignal()  # noqa: N815 — Qt signal, camelCase by convention

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
        self._refresh_btn.setIconSize(QSize(16, 16))
        self._refresh_btn.setFixedSize(26, 26)
        lay.addWidget(self._refresh_btn)

        self.setLayout(lay)
        self._fetching = False
        self._pending_popup = False

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
        if self._pending_popup:
            self._pending_popup = False
            if self._combo.count() > 0:
                self._combo.showPopup()

    def refreshButton(self) -> QToolButton:
        return self._refresh_btn

    def setRefreshing(self, busy: bool) -> None:
        self._fetching = busy
        self._refresh_btn.setEnabled(not busy)

    # -- auto-fetch on empty popup --

    def _on_popup(self) -> None:
        if self._combo.count() == 0 and not self._fetching:
            self._combo._suppress_popup = True
            self._pending_popup = True
            self.modelsRequested.emit()


# -----------------------------------------------------------------------


class ProviderSettingsTab(QWidget):
    """Tab for configuring AI provider credentials and model settings."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._current_provider = "openai"
        # capability -> (url edit, key edit, show-key check, test button, test label)
        self._server_widgets: Dict[
            str, Tuple[QLineEdit, QLineEdit, QCheckBox, QPushButton, str]
        ] = {}
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
        icon_color = self._provider_combo.palette().color(QPalette.ColorRole.Text)
        for ptype in self._config.get_all_provider_types():
            self._provider_combo.addItem(
                provider_icon(ptype, icon_color), PROVIDER_LABELS.get(ptype, ptype), ptype
            )
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

        # Opt-in dedicated servers (issue #18). Ticking one moves that
        # capability's model rows out of "Models" into its own server box.
        split_box = QVBoxLayout()
        split_box.setSpacing(4)
        self._split_tts_check = QCheckBox("Use a different server for speech")
        self._split_tts_check.setToolTip(
            "Send text-to-speech requests to their own server, e.g. a local\n"
            "OpenAI-compatible speech server. Text keeps using the API URL."
        )
        self._split_image_check = QCheckBox("Use a different server for images")
        self._split_image_check.setToolTip(
            "Send image requests to their own server, e.g. a local image\n"
            "generator. Text keeps using the API URL."
        )
        self._split_hint = QLabel("Leave these off to send everything to the API URL above.")
        for w in (self._split_tts_check, self._split_image_check, self._split_hint):
            split_box.addWidget(w)
        qconnect(self._split_tts_check.toggled, lambda on: self._on_split_toggled("tts", on))
        qconnect(self._split_image_check.toggled, lambda on: self._on_split_toggled("image", on))
        cf.addRow("", split_box)

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
        self._models_form = mf
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
        qconnect(
            self._text_model_combo.modelsRequested,
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
        qconnect(
            self._tts_model_combo.modelsRequested,
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
        qconnect(
            self._image_model_combo.modelsRequested,
            lambda: self._fetch_models("image"),
        )
        mf.addRow(self._image_model_label, self._image_model_combo)

        models.setLayout(mf)
        layout.addWidget(models)

        self._tts_server_group, self._tts_server_form = self._build_server_group(
            capability="tts",
            title="Speech Server",
            noun="Speech",
            url_placeholder="e.g. http://localhost:8880/v1",
            test_label="Test Speech",
            test_tip="Synthesize a short phrase to check the speech server and TTS model.",
        )
        layout.addWidget(self._tts_server_group)

        self._image_server_group, self._image_server_form = self._build_server_group(
            capability="image",
            title="Image Server",
            noun="Image",
            url_placeholder="e.g. http://localhost:7860/v1",
            test_label="Test Images",
            test_tip="Generate one small test image to check the image server and image\n"
            "model. Your provider may bill for it.",
        )
        layout.addWidget(self._image_server_group)

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

    def _build_server_group(
        self,
        capability: str,
        title: str,
        noun: str,
        url_placeholder: str,
        test_label: str,
        test_tip: str,
    ) -> Tuple[QGroupBox, QFormLayout]:
        """Build the box for a dedicated speech or image server.

        It starts with URL, key and a test button; :meth:`_apply_split` moves
        the capability's model rows in between key and button.
        """
        group = QGroupBox(title)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        url_edit = QLineEdit()
        url_edit.setPlaceholderText(url_placeholder)
        url_edit.setToolTip(f"Base URL of the server that handles {noun.lower()} requests.")
        form.addRow(f"{noun} URL:", url_edit)

        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        key_edit = QLineEdit()
        key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_edit.setPlaceholderText("Leave empty to use the API key above")
        key_row.addWidget(key_edit)
        show_check = QCheckBox("Show")
        show_check.setToolTip("Toggle API key visibility")
        qconnect(
            show_check.toggled,
            lambda visible: key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
            ),
        )
        key_row.addWidget(show_check)
        form.addRow(f"{noun} API Key:", key_row)

        test_btn = QPushButton(f"  {test_label}  ")
        test_btn.setToolTip(test_tip)
        qconnect(test_btn.clicked, lambda: self._test_media(capability))
        test_row = QHBoxLayout()
        test_row.addStretch()
        test_row.addWidget(test_btn)
        form.addRow("", test_row)

        group.setLayout(form)
        group.setVisible(False)
        self._server_widgets[capability] = (url_edit, key_edit, show_check, test_btn, test_label)
        return group, form

    def _on_split_toggled(self, capability: str, on: bool) -> None:
        self._apply_split()
        if on:
            self._server_widgets[capability][0].setFocus()

    def _apply_split(self) -> None:
        """Place each capability's model rows in "Models" or its server box."""
        caps = PROVIDER_CAPABILITIES.get(self._current_provider, {})
        has_tts = bool(caps.get("tts"))
        has_image = bool(caps.get("image"))
        self._split_tts_check.setVisible(has_tts)
        self._split_image_check.setVisible(has_image)
        self._split_hint.setVisible(has_tts or has_image)

        tts_split = has_tts and self._split_tts_check.isChecked()
        image_split = has_image and self._split_image_check.isChecked()
        tts_rows = [
            (self._tts_model_label, self._tts_model_combo),
            (self._tts_voice_label, self._tts_voice_combo),
        ]
        image_rows = [(self._image_model_label, self._image_model_combo)]

        # In a server box the rows go between its key row and test button
        # (index 2); in "Models" right after Max Tokens (index 2), speech
        # before image.
        if tts_split:
            _move_form_rows(tts_rows, self._models_form, self._tts_server_form, 2)
        else:
            _move_form_rows(tts_rows, self._tts_server_form, self._models_form, 2)
        if image_split:
            _move_form_rows(image_rows, self._models_form, self._image_server_form, 2)
        else:
            end = self._models_form.rowCount()
            _move_form_rows(image_rows, self._image_server_form, self._models_form, end)
        self._tts_server_group.setVisible(tts_split)
        self._image_server_group.setVisible(image_split)

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
        for capability, check, url, key in (
            ("tts", self._split_tts_check, cfg.tts_api_url, cfg.tts_api_key),
            ("image", self._split_image_check, cfg.image_api_url, cfg.image_api_key),
        ):
            url_edit, key_edit, show_check, _btn, _label = self._server_widgets[capability]
            url_edit.setText(url)
            key_edit.setText(key)
            show_check.setChecked(False)
            check.blockSignals(True)
            check.setChecked(cfg.has_dedicated_server(capability))
            check.blockSignals(False)
        self._max_tokens_spin.setValue(cfg.max_tokens)

        # Restore cached model lists (persistent across sessions)
        cached = self._config.get_all_cached_models(ptype)
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
        self._apply_split()

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
            # An unticked box drops its server, so on reload the URL decides.
            tts_api_url=self._server_field("tts", self._split_tts_check, 0),
            tts_api_key=self._server_field("tts", self._split_tts_check, 1),
            image_api_url=self._server_field("image", self._split_image_check, 0),
            image_api_key=self._server_field("image", self._split_image_check, 1),
        )
        self._config.set_provider_config(ptype, cfg)

    def _server_field(self, capability: str, check: QCheckBox, index: int) -> str:
        """Text of a server box's URL (0) or key (1) field, or "" when its box is off."""
        if not check.isChecked():
            return ""
        return self._server_widgets[capability][index].text().strip()

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
        cfg = self._config.get_provider_config(ptype).for_capability(capability)
        # A self-hosted speech/image server often needs no key at all.
        if not cfg.api_key and not cfg.has_dedicated_server(capability):
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
                err_detail = getattr(e, "detail", None)
                mw.taskman.run_on_main(
                    lambda: self._on_models_fetched(
                        ptype, capability, target, [], err_msg, err_detail
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
        detail: Optional[str] = None,
    ) -> None:
        combo.setRefreshing(False)
        if error:
            show_error(
                f"Failed to fetch models:\n\n{error}",
                detail,
                parent=self,
            )
        elif models:
            # Persist the results for this provider + capability
            self._config.set_cached_models(ptype, capability, models)
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
            success, message, detail = test_provider_connection(cfg)
            mw.taskman.run_on_main(lambda: self._show_test_result(success, message, detail))

        threading.Thread(target=test, daemon=True).start()

    def _show_test_result(self, success: bool, message: str, detail: Optional[str] = None) -> None:
        self._test_btn.setEnabled(True)
        self._test_btn.setText("  Test Connection  ")
        if success:
            tooltip("Connection successful!", parent=self)
        else:
            show_error(f"Connection failed:\n\n{message}", detail, parent=self)

    def _test_media(self, capability: str) -> None:
        """Check the speech or image server, using its own model."""
        self._save_current_provider()
        cfg = self._config.get_provider_config(self._current_provider).for_capability(capability)
        model = cfg.tts_model if capability == "tts" else cfg.image_model
        if not model:
            kind = "TTS" if capability == "tts" else "image"
            showInfo(f"Please choose a {kind} model first.", title="AI Field Filler")
            return
        test_btn = self._server_widgets[capability][3]
        test_btn.setEnabled(False)
        test_btn.setText("  Testing...  ")
        test_fn = test_tts_connection if capability == "tts" else test_image_connection

        def test() -> None:
            success, message, detail = test_fn(cfg)
            mw.taskman.run_on_main(
                lambda: self._show_media_test_result(capability, success, message, detail)
            )

        threading.Thread(target=test, daemon=True).start()

    def _show_media_test_result(
        self, capability: str, success: bool, message: str, detail: Optional[str]
    ) -> None:
        _url, _key, _show, test_btn, test_label = self._server_widgets[capability]
        test_btn.setEnabled(True)
        test_btn.setText(f"  {test_label}  ")
        if success:
            tooltip(message, parent=self)
        else:
            show_error(f"{test_label} failed:\n\n{message}", detail, parent=self)

    # ---- save ----------------------------------------------------------

    def save(self) -> None:
        self._save_current_provider()
        self._config.set_active_provider_type("text", self._active_text_combo.currentData())
        self._config.set_active_provider_type("tts", self._active_tts_combo.currentData())
        self._config.set_active_provider_type("image", self._active_image_combo.currentData())


def _move_form_rows(
    rows: List[Tuple[QWidget, QWidget]], src: QFormLayout, dst: QFormLayout, index: int
) -> None:
    """Move ``(label, field)`` rows from *src* to *dst*, starting at row *index*.

    Rows already in *dst* stay put, so this is safe to call repeatedly.
    ``takeRow`` detaches a row without deleting its widgets.
    """
    for offset, (label, field) in enumerate(rows):
        if dst.getWidgetPosition(field)[0] >= 0:
            continue
        row = src.getWidgetPosition(field)[0]
        if row >= 0:
            src.takeRow(row)
        dst.insertRow(index + offset, label, field)
