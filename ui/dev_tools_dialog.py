"""Hidden developer tools for exercising provider behaviour by hand.

Opened with Ctrl+Shift+Alt+D from the main window, or from
Tools -> AI Field Filler -> Developer Tools when ``general.dev_mode`` is
enabled in the config.

Every run uses the Parameters panel — provider, models, prompts and token
budget — so a behaviour can be tried against different setups without
touching the real settings.  Runs stream into the log as they go and can
be stopped part-way.  This is the manual counterpart to the unit tests:
it proves the runtime behaviour that mocks cannot.
"""

from __future__ import annotations

import threading
import time
import traceback
from typing import Callable, List, Optional, Tuple

from aqt import mw
from aqt.qt import *
from aqt.utils import tooltip

from ..config_manager import ConfigManager, ProviderConfig
from ..providers import (
    create_image_provider,
    create_text_provider,
    create_tts_provider,
    fetch_available_models,
    test_provider_connection,
)
from ..providers.http import http_get_json
from .error_dialog import show_error
from .provider_settings_tab import (
    KNOWN_TTS_VOICES,
    PROVIDER_CAPABILITIES,
    PROVIDER_LABELS,
    ModelComboWithRefresh,
)
from .styles import GLOBAL_STYLE, HEADER_STYLE, MUTED_LABEL_STYLE

_SHORTCUT = "Ctrl+Shift+Alt+D"

# Buttons must keep their natural height rather than being squeezed by the
# layout; their width is measured from the longest label at runtime, since
# hard-coding it clips labels under a different font or UI scale.
_BUTTON_HEIGHT = 34

_ACTIVE = "⟨use active providers⟩"

# Models that failed before the compatibility work, kept as a regression
# probe: each one exercises a different quirk.
_PROBE_MODELS = {
    "openai": [
        ("gpt-5.5", "rejects temperature"),
        ("gpt-6-astra", "rejects temperature"),
        ("o3", "rejects temperature"),
        ("gpt-5.4-pro", "needs /v1/responses"),
        ("o1-pro", "needs /v1/responses"),
        ("gpt-4o-mini", "plain chat model (control)"),
    ],
    "anthropic": [
        ("claude-fable-5", "thinking block precedes text"),
        ("claude-opus-5", "control"),
    ],
    "google": [
        ("gemma-4-31b-it", "rejects system_instruction"),
        ("gemini-3.1-pro-preview", "thinking parts"),
        ("gemini-2.5-pro", "retired upstream (expected clean error)"),
    ],
    "openrouter": [
        ("openai/gpt-6-astra", "normalised by OpenRouter"),
        ("openai/gpt-5.4-pro", "no /responses needed here"),
        ("anthropic/claude-fable-5.1", "thinking block"),
        ("nvidia/nemotron-nano-9b-v2", "no live endpoint (expected clean error)"),
    ],
}

_DEFAULT_SYSTEM_PROMPT = "Reply with exactly the word OK and nothing else."
_DEFAULT_USER_PROMPT = "Test connection."
_DEFAULT_IMAGE_PROMPT = "A small red circle on a white background."
_DEFAULT_TTS_TEXT = "This is a test of the speech synthesis pipeline."

_SAMPLE_ERROR_BODY = (
    '{"error": {"message": "Unsupported value: \'temperature\' does not support '
    '0.7 with this model. Only the default (1) value is supported.", '
    '"type": "invalid_request_error", "param": "temperature", '
    '"code": "unsupported_value"}}'
)


class _Aborted(Exception):
    """Raised inside a run when the user presses Stop."""


class _RunContext:
    """Handed to each run: streams log lines and reports aborts."""

    def __init__(self, dialog: DevToolsDialog, abort: threading.Event) -> None:
        self._dialog = dialog
        self._abort = abort

    @property
    def aborted(self) -> bool:
        return self._abort.is_set()

    def check(self) -> None:
        """Raise :class:`_Aborted` if Stop was pressed."""
        if self._abort.is_set():
            raise _Aborted()

    def log(self, line: str = "") -> None:
        """Append a line to the log from a worker thread."""
        mw.taskman.run_on_main(lambda text=line: self._dialog._safe_log(text))


def _raw_model_ids(cfg: ProviderConfig) -> List[str]:
    """Every model id the provider's API returns, before classification."""
    if cfg.provider_type in ("openai", "openrouter"):
        label = "OpenAI" if cfg.provider_type == "openai" else "OpenRouter"
        data = http_get_json(
            f"{cfg.base_url}/models",
            {"Authorization": f"Bearer {cfg.api_key}"},
            label=label,
        )
        return [m["id"] for m in data.get("data", []) if m.get("id")]
    if cfg.provider_type == "anthropic":
        data = http_get_json(
            f"{cfg.base_url}/models?limit=100",
            {"x-api-key": cfg.api_key, "anthropic-version": "2023-06-01"},
            label="Anthropic",
        )
        return [m["id"] for m in data.get("data", []) if m.get("id")]
    if cfg.provider_type == "google":
        data = http_get_json(
            f"{cfg.base_url}/models?key={cfg.api_key}&pageSize=1000", label="Google"
        )
        return [
            m.get("name", "").split("/", 1)[-1] for m in data.get("models", []) if m.get("name")
        ]
    return []


def _describe_bytes(data: bytes) -> str:
    """Identify a media payload from its magic bytes."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if data[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if data[:4] == b"RIFF":
        return "RIFF/WAV"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xe2"):
        return "MP3"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    return "raw/unknown (PCM?)"


class DevToolsDialog(QDialog):
    """Buttons that exercise each provider behaviour, with a log pane."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent or mw)
        self._config = ConfigManager()
        self._busy = False
        self._closed = False
        self._widths_normalized = False
        self._abort = threading.Event()
        self._buttons: List[QPushButton] = []
        self._setup_ui()

    # ---- sizing ---------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802 — Qt naming
        super().showEvent(event)
        if not self._widths_normalized:
            self._widths_normalized = True
            self._normalize_button_widths()

    def _normalize_button_widths(self) -> None:
        """Size every button to the longest label, and the column to match.

        Must run after the first show: a button's sizeHint only accounts for
        the dialog stylesheet's padding once Qt has applied it, so measuring
        during construction clips the longest label.
        """
        width = max(b.sizeHint().width() for b in self._buttons)
        for btn in self._buttons:
            btn.setFixedWidth(width)
        self._params_box.setFixedWidth(width)
        # Leave room for the column's vertical scrollbar.
        self._left_scroll.setFixedWidth(width + 44)

    # ---- closing --------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt naming
        self._mark_closed()
        super().closeEvent(event)

    def reject(self) -> None:
        self._mark_closed()
        super().reject()

    def _mark_closed(self) -> None:
        """Stop pending results from touching widgets that are going away.

        The request already in flight cannot be cancelled, so it still
        finishes in the background — its result is simply discarded.
        """
        if self._busy and not self._closed:
            self._abort.set()
            tooltip(
                "A developer-tools run is still in flight; its result will be discarded.",
                parent=self.parentWidget() or mw,
            )
        self._closed = True

    # ---- layout ---------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("AI Field Filler — Developer Tools")
        self.setMinimumSize(980, 640)
        self.setStyleSheet(GLOBAL_STYLE())

        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("\U0001f9ea Developer Tools")
        title.setStyleSheet(HEADER_STYLE())
        root.addWidget(title)

        subtitle = QLabel(
            "Runs use the parameters below, not your saved settings. Calls cost real API credits."
        )
        subtitle.setStyleSheet(MUTED_LABEL_STYLE())
        root.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(14)

        # -- left: parameters + action buttons --
        # Held in a scroll area so that a window shorter than the column
        # scrolls instead of compressing the buttons until their labels clip.
        left_panel = QWidget()
        left = QVBoxLayout()
        left.setSpacing(10)
        left.setContentsMargins(0, 0, 0, 0)

        self._params_box = self._build_params()
        left.addWidget(self._params_box)

        left.addWidget(
            self._group(
                "1 · Error dialog",
                [
                    ("Plain message (no details)", self._err_plain),
                    ("API error + JSON details", self._err_json),
                    ("Oversized payload (scroll test)", self._err_huge),
                ],
            )
        )
        left.addWidget(
            self._group(
                "2 · Model lists",
                [
                    ("List models (all providers)", self._list_models),
                    ("Show models filtered OUT", self._show_filtered),
                ],
            )
        )
        left.addWidget(
            self._group(
                "3 · Live calls",
                [
                    ("Test connection", self._test_connection),
                    ("Generate text", self._gen_text),
                    ("Generate image (report format)", self._gen_image),
                    ("Synthesize speech (report format)", self._gen_tts),
                ],
            )
        )
        left.addWidget(
            self._group(
                "4 · Compatibility probe",
                [
                    ("Probe: selected provider", self._probe_selected),
                    ("Probe: all providers", self._probe_all),
                ],
            )
        )
        left.addWidget(
            self._group(
                "5 · Everything",
                [("▶ Run all tests", self._run_all)],
            )
        )
        left.addStretch()
        left_panel.setLayout(left)

        left_scroll = QScrollArea()
        left_scroll.setWidget(left_panel)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        # Widths are normalised in showEvent, not here: the dialog's
        # stylesheet padding only reaches the buttons once Qt shows them, so
        # measuring sizeHint now under-reports and the longest label elides.
        self._left_scroll = left_scroll
        body.addWidget(left_scroll, 0)

        # -- right: log --
        right = QVBoxLayout()
        right.setSpacing(6)
        log_label = QLabel("Log")
        log_label.setStyleSheet(MUTED_LABEL_STYLE())
        right.addWidget(log_label)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        self._log.setFont(font)
        self._log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        right.addWidget(self._log, 1)

        log_bar = QHBoxLayout()
        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setToolTip(
            "Stop after the request in flight returns — an HTTP call already "
            "sent cannot be cancelled."
        )
        qconnect(self._stop_btn.clicked, self._request_abort)
        copy_btn = QPushButton("Copy log")
        qconnect(copy_btn.clicked, self._copy_log)
        clear_btn = QPushButton("Clear")
        qconnect(clear_btn.clicked, lambda: self._log.clear())
        log_bar.addWidget(self._stop_btn)
        log_bar.addWidget(copy_btn)
        log_bar.addWidget(clear_btn)
        log_bar.addStretch()
        self._status = QLabel("")
        self._status.setStyleSheet(MUTED_LABEL_STYLE())
        log_bar.addWidget(self._status)
        right.addLayout(log_bar)
        body.addLayout(right, 1)

        root.addLayout(body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        qconnect(buttons.rejected, self.reject)
        root.addWidget(buttons)
        self.setLayout(root)

        self._on_provider_changed()
        self._log_line("Ready. Active providers: " + self._active_summary())

    def _build_params(self) -> QGroupBox:
        """Provider / model / prompt overrides applied to every run."""
        box = QGroupBox("Parameters")
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(7)

        self._provider_combo = QComboBox()
        self._provider_combo.addItem(_ACTIVE, None)
        for ptype in self._config.get_all_provider_types():
            self._provider_combo.addItem(PROVIDER_LABELS.get(ptype, ptype), ptype)
        qconnect(self._provider_combo.currentIndexChanged, self._on_provider_changed)
        form.addRow("Provider:", self._provider_combo)

        self._text_model = ModelComboWithRefresh("(provider default)", "Text model override")
        qconnect(self._text_model.refreshButton().clicked, lambda: self._fetch_models("text"))
        self._text_model.modelsRequested.connect(lambda: self._fetch_models("text"))
        form.addRow("Text model:", self._text_model)

        self._image_model = ModelComboWithRefresh("(provider default)", "Image model override")
        qconnect(self._image_model.refreshButton().clicked, lambda: self._fetch_models("image"))
        self._image_model.modelsRequested.connect(lambda: self._fetch_models("image"))
        form.addRow("Image model:", self._image_model)

        self._tts_model = ModelComboWithRefresh("(provider default)", "TTS model override")
        qconnect(self._tts_model.refreshButton().clicked, lambda: self._fetch_models("tts"))
        self._tts_model.modelsRequested.connect(lambda: self._fetch_models("tts"))
        form.addRow("TTS model:", self._tts_model)

        self._tts_voice = QComboBox()
        self._tts_voice.setEditable(True)
        form.addRow("TTS voice:", self._tts_voice)

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(1, 200000)
        self._max_tokens.setSingleStep(256)
        self._max_tokens.setToolTip(
            "Lower this to see a reasoning model spend its whole budget on "
            "thinking and return no text."
        )
        form.addRow("Max tokens:", self._max_tokens)

        self._system_prompt = QLineEdit(_DEFAULT_SYSTEM_PROMPT)
        form.addRow("System prompt:", self._system_prompt)

        self._user_prompt = QLineEdit(_DEFAULT_USER_PROMPT)
        form.addRow("User prompt:", self._user_prompt)

        self._image_prompt = QLineEdit(_DEFAULT_IMAGE_PROMPT)
        form.addRow("Image prompt:", self._image_prompt)

        self._tts_text = QLineEdit(_DEFAULT_TTS_TEXT)
        form.addRow("TTS text:", self._tts_text)

        reset = QPushButton("Reset parameters")
        qconnect(reset.clicked, self._reset_params)
        form.addRow("", reset)

        box.setLayout(form)
        box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return box

    def _group(self, title: str, actions: List[Tuple[str, Callable[[], None]]]) -> QGroupBox:
        box = QGroupBox(title)
        lay = QVBoxLayout()
        lay.setSpacing(6)
        for label, handler in actions:
            btn = QPushButton(label)
            # Vertically Fixed, or Qt shrinks the buttons below their
            # sizeHint when the column is taller than the window and the
            # labels get clipped.
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setMinimumHeight(_BUTTON_HEIGHT)
            qconnect(btn.clicked, handler)
            self._buttons.append(btn)
            lay.addWidget(btn)
        box.setLayout(lay)
        box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return box

    # ---- parameters -----------------------------------------------------

    def _selected_provider(self, capability: str) -> str:
        """The provider these runs should use for *capability*."""
        chosen = self._provider_combo.currentData()
        return chosen or self._config.get_active_provider_type(capability)

    def _on_provider_changed(self) -> None:
        """Reset model lists and defaults when the provider selection changes."""
        ptype = self._selected_provider("text")
        cfg = self._config.get_provider_config(ptype)
        for combo in (self._text_model, self._image_model, self._tts_model):
            combo.setModels([])
            combo.setCurrentText("")
        self._max_tokens.setValue(cfg.max_tokens or 4096)

        self._tts_voice.clear()
        self._tts_voice.addItems(KNOWN_TTS_VOICES.get(ptype, []))
        self._tts_voice.setCurrentText(cfg.tts_voice)

        caps = PROVIDER_CAPABILITIES.get(ptype, {})
        self._image_model.setEnabled(caps.get("image", True))
        self._tts_model.setEnabled(caps.get("tts", True))
        self._tts_voice.setEnabled(caps.get("tts", True))

    def _reset_params(self) -> None:
        self._provider_combo.setCurrentIndex(0)
        self._system_prompt.setText(_DEFAULT_SYSTEM_PROMPT)
        self._user_prompt.setText(_DEFAULT_USER_PROMPT)
        self._image_prompt.setText(_DEFAULT_IMAGE_PROMPT)
        self._tts_text.setText(_DEFAULT_TTS_TEXT)
        self._on_provider_changed()
        self._status.setText("Parameters reset.")

    def _fetch_models(self, capability: str) -> None:
        """Populate a model dropdown from the selected provider."""
        combo = {
            "text": self._text_model,
            "image": self._image_model,
            "tts": self._tts_model,
        }[capability]
        ptype = self._selected_provider(capability)
        cfg = self._config.get_provider_config(ptype)
        if not cfg.api_key:
            self._log_line(f"No API key configured for {ptype}; cannot fetch models.")
            return
        combo.setRefreshing(True)

        def task() -> None:
            try:
                models = fetch_available_models(cfg, capability)
                error = None
            except Exception as e:
                models, error = [], str(e)

            def done() -> None:
                if self._closed:
                    return
                try:
                    combo.setRefreshing(False)
                    combo.setModels(models)
                    if error:
                        self._log_line(f"Model fetch failed for {ptype}/{capability}: {error}")
                    else:
                        self._log_line(f"{ptype}/{capability}: loaded {len(models)} model(s).")
                except RuntimeError:
                    pass

            mw.taskman.run_on_main(done)

        mw.taskman.run_in_background(task)

    def _cfg_for(self, capability: str) -> ProviderConfig:
        """Build a config from the saved provider plus panel overrides."""
        ptype = self._selected_provider(capability)
        base = self._config.get_provider_config(ptype)
        return ProviderConfig(
            provider_type=ptype,
            api_url=base.api_url,
            api_key=base.api_key,
            text_model=self._text_model.currentText().strip() or base.text_model,
            max_tokens=self._max_tokens.value(),
            tts_model=self._tts_model.currentText().strip() or base.tts_model,
            tts_voice=self._tts_voice.currentText().strip() or base.tts_voice,
            image_model=self._image_model.currentText().strip() or base.image_model,
        )

    # ---- logging --------------------------------------------------------

    def _log_line(self, text: str = "") -> None:
        self._log.appendPlainText(text)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _safe_log(self, text: str) -> None:
        """Log from a worker thread, ignoring a dialog that has gone away."""
        if self._closed:
            return
        try:
            self._log_line(text)
        except RuntimeError:
            pass

    def _header(self, text: str) -> None:
        self._log_line("")
        self._log_line("=" * 68)
        self._log_line(text)
        self._log_line("=" * 68)

    def _copy_log(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._log.toPlainText())
        self._status.setText("Log copied.")

    def _active_summary(self) -> str:
        return ", ".join(
            f"{cap}={self._config.get_active_provider_type(cap)}"
            for cap in ("text", "tts", "image")
        )

    # ---- async plumbing -------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for btn in self._buttons:
            btn.setEnabled(not busy)
        self._params_box.setEnabled(not busy)
        self._stop_btn.setEnabled(busy)
        self._status.setText("Working…" if busy else "")

    def _request_abort(self) -> None:
        self._abort.set()
        self._stop_btn.setEnabled(False)
        self._status.setText("Stopping…")
        self._log_line("\n** Stop requested — finishing the call in flight. **")

    def _run_async(self, label: str, work: Callable[[_RunContext], None]) -> None:
        """Run *work* off the UI thread, streaming its output to the log."""
        if self._busy:
            return
        self._header(label)
        self._abort.clear()
        self._set_busy(True)
        ctx = _RunContext(self, self._abort)
        started = time.time()

        def task() -> None:
            outcome = "finished"
            try:
                work(ctx)
            except _Aborted:
                outcome = "ABORTED"
            except Exception:
                outcome = "FAILED"
                ctx.log("FAILED\n" + traceback.format_exc(limit=4))
            elapsed = time.time() - started

            def done() -> None:
                if self._closed:
                    return
                try:
                    self._log_line(f"-- {outcome} in {elapsed:.1f}s --")
                    self._set_busy(False)
                except RuntimeError:
                    pass

            mw.taskman.run_on_main(done)

        mw.taskman.run_in_background(task)

    # ---- 1. error dialog ------------------------------------------------

    def _err_plain(self) -> None:
        self._header("Error dialog · plain message")
        self._log_line("Expect: compact dialog, no 'Show details' button.")
        show_error(
            "AI Field Filler error:\n\nConnection error: timed out after 120s.",
            parent=self,
        )

    def _err_json(self) -> None:
        from ..providers.http import _http_error

        self._header("Error dialog · API error with JSON details")
        err = _http_error("OpenAI API", 400, _SAMPLE_ERROR_BODY)
        self._log_line(f"Summary line shown to the user:\n  {err}")
        self._log_line("Expect: 'Show details' reveals pretty-printed JSON + Copy.")
        show_error(f"AI Field Filler error:\n\n{err}", err.detail, parent=self)

    def _err_huge(self) -> None:
        self._header("Error dialog · oversized payload")
        rows = ",\n    ".join(f'"model_{i}": "value that is quite long {i}"' for i in range(200))
        detail = '{\n  "data": {\n    ' + rows + "\n  }\n}"
        self._log_line(f"Payload is {len(detail)} chars / {detail.count(chr(10)) + 1} lines.")
        self._log_line("Expect: dialog stays a fixed size; details pane scrolls.")
        show_error(
            "AI Field Filler error:\n\nThe provider returned an unexpected payload.",
            detail,
            parent=self,
        )

    # ---- 2. model lists -------------------------------------------------

    # Each button and the matching "Run all" step share one implementation,
    # defined under "step bodies" below.

    def _list_models(self) -> None:
        self._run_async("Model lists · all providers × capabilities", self._list_models_work)

    def _show_filtered(self) -> None:
        self._run_async("Models hidden from the dropdowns", self._filtered_work)

    # ---- 3. live calls --------------------------------------------------

    def _test_connection(self) -> None:
        self._run_async("Connection test", self._connection_work)

    def _gen_text(self) -> None:
        self._run_async("Generate text", self._text_work)

    def _gen_image(self) -> None:
        self._run_async("Generate image · report detected format", self._image_work)

    def _gen_tts(self) -> None:
        self._run_async("Synthesize speech · report detected format", self._tts_work)

    # ---- 4. compatibility probe ----------------------------------------

    def _probe_work(self, ptypes: List[str]) -> Callable[[_RunContext], None]:
        def work(ctx: _RunContext) -> None:
            for ptype in ptypes:
                ctx.check()
                cfg = self._config.get_provider_config(ptype)
                if not cfg.api_key:
                    ctx.log(f"--- {ptype}: no API key configured, skipped ---")
                    continue
                ctx.log(f"--- {ptype} ---")
                for model, why in _PROBE_MODELS.get(ptype, []):
                    ctx.check()
                    probe_cfg = ProviderConfig(
                        provider_type=ptype,
                        api_url=cfg.api_url,
                        api_key=cfg.api_key,
                        text_model=model,
                        max_tokens=self._max_tokens.value(),
                    )
                    started = time.time()
                    try:
                        reply = create_text_provider(probe_cfg).generate(
                            self._system_prompt.text(), self._user_prompt.text()
                        )
                        status = "OK   " if reply.strip() else "EMPTY"
                        note = repr(reply.strip()[:40])
                    except Exception as e:
                        status = "FAIL "
                        note = f"{e}"[:90]
                    ctx.log(
                        f"  [{status}] {model:34} {time.time() - started:5.1f}s  ({why})"
                        f"\n           {note}"
                    )
                ctx.log("")
            ctx.log("Entries marked 'expected clean error' should FAIL with a")
            ctx.log("readable sentence, not a raw JSON body.")

        return work

    def _probe_selected(self) -> None:
        ptype = self._selected_provider("text")
        self._run_async(f"Compatibility probe · {ptype}", self._probe_work([ptype]))

    def _probe_all(self) -> None:
        self._run_async(
            "Compatibility probe · all providers",
            self._probe_work(list(_PROBE_MODELS.keys())),
        )

    # ---- 5. run everything ----------------------------------------------

    def _run_all(self) -> None:
        """Every non-interactive check, in order, abortable between steps."""

        def work(ctx: _RunContext) -> None:
            steps: List[Tuple[str, Callable[[_RunContext], None]]] = [
                ("Model lists", self._list_models_work),
                ("Models filtered out", self._filtered_work),
                ("Connection test", self._connection_work),
                ("Generate text", self._text_work),
                ("Generate image", self._image_work),
                ("Synthesize speech", self._tts_work),
                ("Compatibility probe (all)", self._probe_work(list(_PROBE_MODELS.keys()))),
            ]
            for index, (name, step) in enumerate(steps, 1):
                ctx.check()
                ctx.log("")
                ctx.log(f"########## {index}/{len(steps)} · {name} ##########")
                try:
                    step(ctx)
                except _Aborted:
                    raise
                except Exception as e:
                    ctx.log(f"  step failed: {type(e).__name__}: {e}")
            ctx.log("")
            ctx.log("The three error-dialog buttons are interactive and are not")
            ctx.log("included here — run them by hand.")

        self._run_async("Run all tests", work)

    # ---- step bodies ----------------------------------------------------
    # Each is used both by its own button and by "Run all tests", so the two
    # paths cannot drift apart.

    def _list_models_work(self, ctx: _RunContext) -> None:
        for ptype in self._config.get_all_provider_types():
            ctx.check()
            cfg = self._config.get_provider_config(ptype)
            if not cfg.api_key:
                ctx.log(f"{ptype:12} -- no API key configured, skipped")
                continue
            for cap in ("text", "tts", "image"):
                ctx.check()
                try:
                    models = fetch_available_models(cfg, cap)
                    preview = ", ".join(models[:3])
                    ctx.log(f"{ptype:12} {cap:6} {len(models):>4} models   {preview}")
                except Exception as e:
                    ctx.log(f"{ptype:12} {cap:6}  ERROR  {e}")
        ctx.log("")
        ctx.log("Anthropic tts/image and OpenRouter tts should report 0 models.")

    def _filtered_work(self, ctx: _RunContext) -> None:
        for ptype in self._config.get_all_provider_types():
            ctx.check()
            cfg = self._config.get_provider_config(ptype)
            if not cfg.api_key:
                ctx.log(f"{ptype:12} -- no API key configured, skipped")
                continue
            try:
                raw = set(_raw_model_ids(cfg))
                offered: set = set()
                for cap in ("text", "tts", "image"):
                    ctx.check()
                    offered |= set(fetch_available_models(cfg, cap))
                hidden = sorted(raw - offered)
                ctx.log(f"--- {ptype}: {len(raw)} returned, {len(hidden)} hidden ---")
                for m in hidden:
                    ctx.log(f"      {m}")
            except Exception as e:
                ctx.log(f"{ptype:12} ERROR  {e}")
            ctx.log("")
        ctx.log("These are hidden because calling them cannot work: completions-only,")
        ctx.log("deep-research, music, robotics, speech-to-text, batch-only.")

    def _connection_work(self, ctx: _RunContext) -> None:
        cfg = self._cfg_for("text")
        ok, message, detail = test_provider_connection(cfg)
        ctx.log(f"provider : {cfg.provider_type}")
        ctx.log(f"model    : {cfg.text_model}")
        ctx.log(f"result   : {'OK' if ok else 'FAILED'}")
        ctx.log(f"message  : {message}")
        ctx.log(f"detail   : {'present' if detail else 'none'}")

    def _text_work(self, ctx: _RunContext) -> None:
        cfg = self._cfg_for("text")
        ctx.log(f"provider   : {cfg.provider_type}")
        ctx.log(f"model      : {cfg.text_model}")
        ctx.log(f"max_tokens : {cfg.max_tokens}")
        ctx.check()
        reply = create_text_provider(cfg).generate(
            self._system_prompt.text(), self._user_prompt.text()
        )
        ctx.log(f"reply      : {reply.strip()!r}")

    def _image_work(self, ctx: _RunContext) -> None:
        from ..media_handler import MediaHandler

        cfg = self._cfg_for("image")
        ctx.log(f"provider : {cfg.provider_type}")
        ctx.log(f"model    : {cfg.image_model}")
        ctx.check()
        data = create_image_provider(cfg).generate_image(self._image_prompt.text())
        ctx.log(f"bytes    : {len(data)}")
        ctx.log(f"magic    : {data[:8].hex()} -> {_describe_bytes(data)}")
        ctx.log(f"saved as : .{MediaHandler._sniff_image_ext(data)}")
        ctx.log("")
        ctx.log("Gemini 3.x returns JPEG; it must save as .jpg, not .png.")

    def _tts_work(self, ctx: _RunContext) -> None:
        cfg = self._cfg_for("tts")
        ctx.log(f"provider : {cfg.provider_type}")
        ctx.log(f"model    : {cfg.tts_model}")
        ctx.log(f"voice    : {cfg.tts_voice}")
        ctx.check()
        data = create_tts_provider(cfg).synthesize(
            self._tts_text.text(), language="en", voice=cfg.tts_voice, context=""
        )
        ctx.log(f"bytes    : {len(data)}")
        ctx.log(f"magic    : {data[:8].hex()} -> {_describe_bytes(data)}")
        ctx.log("")
        ctx.log("Google returns raw PCM; MediaHandler wraps it in a WAV header.")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

_shortcut: Optional[QShortcut] = None


def open_dev_tools(parent: QWidget | None = None) -> None:
    """Open the developer tools dialog."""
    DevToolsDialog(parent).exec()


def register_dev_shortcut() -> None:
    """Bind the hidden Ctrl+Shift+Alt+D shortcut on the main window."""
    global _shortcut
    if _shortcut is not None:
        return
    _shortcut = QShortcut(QKeySequence(_SHORTCUT), mw)
    _shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
    qconnect(_shortcut.activated, lambda: open_dev_tools(mw))
