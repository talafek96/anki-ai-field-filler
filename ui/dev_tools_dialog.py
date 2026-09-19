"""Hidden developer tools for exercising provider behaviour by hand.

Opened with Ctrl+Shift+Alt+D from the main window, or from
Tools -> AI Field Filler -> Developer Tools when ``general.dev_mode`` is
enabled in the config.

Every button runs against the *live* configured providers and writes to
the log pane, so this is the manual counterpart to the unit tests: it
proves the runtime behaviour that mocks cannot.
"""

from __future__ import annotations

import time
import traceback
from typing import Callable, List, Optional, Tuple

from aqt import mw
from aqt.qt import *

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
from .styles import GLOBAL_STYLE, HEADER_STYLE, MUTED_LABEL_STYLE

_SHORTCUT = "Ctrl+Shift+Alt+D"

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

_SAMPLE_ERROR_BODY = (
    '{"error": {"message": "Unsupported value: \'temperature\' does not support '
    '0.7 with this model. Only the default (1) value is supported.", '
    '"type": "invalid_request_error", "param": "temperature", '
    '"code": "unsupported_value"}}'
)


def _raw_model_ids(cfg: ProviderConfig) -> List[str]:
    """Every model id the provider's API returns, before classification."""
    if cfg.provider_type == "openai":
        data = http_get_json(
            f"{cfg.base_url}/models",
            {"Authorization": f"Bearer {cfg.api_key}"},
            label="OpenAI",
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
    if cfg.provider_type == "openrouter":
        data = http_get_json(
            f"{cfg.base_url}/models",
            {"Authorization": f"Bearer {cfg.api_key}"},
            label="OpenRouter",
        )
        return [m["id"] for m in data.get("data", []) if m.get("id")]
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

    _GEOM_KEY = "ai_field_filler_dev_tools"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent or mw)
        self._config = ConfigManager()
        self._busy = False
        self._buttons: List[QPushButton] = []
        self._setup_ui()

    # ---- layout ---------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("AI Field Filler — Developer Tools")
        self.setMinimumSize(940, 620)
        self.setStyleSheet(GLOBAL_STYLE())

        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("\U0001f9ea Developer Tools")
        title.setStyleSheet(HEADER_STYLE())
        root.addWidget(title)

        subtitle = QLabel(
            "Each button runs against your live configured providers. Calls cost real API credits."
        )
        subtitle.setStyleSheet(MUTED_LABEL_STYLE())
        root.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(14)

        # -- left: action buttons --
        left = QVBoxLayout()
        left.setSpacing(10)

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
                "3 · Live calls (active providers)",
                [
                    ("Test connection", self._test_connection),
                    ("Generate text", self._gen_text),
                    ("Generate image → report format", self._gen_image),
                    ("Synthesize speech → report format", self._gen_tts),
                ],
            )
        )
        left.addWidget(
            self._group(
                "4 · Compatibility probe",
                [
                    ("Probe tricky models (active text provider)", self._probe_active),
                    ("Probe tricky models (ALL providers)", self._probe_all),
                ],
            )
        )
        left.addStretch()
        body.addLayout(left, 0)

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
        copy_btn = QPushButton("Copy log")
        qconnect(copy_btn.clicked, self._copy_log)
        clear_btn = QPushButton("Clear")
        qconnect(clear_btn.clicked, lambda: self._log.clear())
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

        self._log_line("Ready. Active providers: " + self._active_summary())

    def _group(self, title: str, actions: List[Tuple[str, Callable[[], None]]]) -> QGroupBox:
        box = QGroupBox(title)
        lay = QVBoxLayout()
        lay.setSpacing(6)
        for label, handler in actions:
            btn = QPushButton(label)
            btn.setMinimumWidth(300)
            qconnect(btn.clicked, handler)
            self._buttons.append(btn)
            lay.addWidget(btn)
        box.setLayout(lay)
        return box

    # ---- logging --------------------------------------------------------

    def _log_line(self, text: str = "") -> None:
        self._log.appendPlainText(text)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _header(self, text: str) -> None:
        self._log_line("")
        self._log_line("=" * 64)
        self._log_line(text)
        self._log_line("=" * 64)

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
        self._status.setText("Working…" if busy else "")

    def _run_async(self, label: str, work: Callable[[], str]) -> None:
        """Run *work* off the UI thread and append its output to the log."""
        if self._busy:
            return
        self._header(label)
        self._set_busy(True)
        started = time.time()

        def task() -> None:
            try:
                output = work()
            except Exception:
                output = "FAILED\n" + traceback.format_exc(limit=4)
            elapsed = time.time() - started

            def done() -> None:
                self._log_line(output)
                self._log_line(f"-- finished in {elapsed:.1f}s --")
                self._set_busy(False)

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

    def _list_models(self) -> None:
        def work() -> str:
            lines = []
            for ptype in self._config.get_all_provider_types():
                cfg = self._config.get_provider_config(ptype)
                if not cfg.api_key:
                    lines.append(f"{ptype:12} -- no API key configured, skipped")
                    continue
                for cap in ("text", "tts", "image"):
                    try:
                        models = fetch_available_models(cfg, cap)
                        preview = ", ".join(models[:3])
                        lines.append(f"{ptype:12} {cap:6} {len(models):>4} models   {preview}")
                    except Exception as e:
                        lines.append(f"{ptype:12} {cap:6}  ERROR  {e}")
            lines.append("")
            lines.append("Anthropic tts/image and OpenRouter tts should report 0 models.")
            return "\n".join(lines)

        self._run_async("Model lists · all providers × capabilities", work)

    def _show_filtered(self) -> None:
        def work() -> str:
            lines = []
            for ptype in self._config.get_all_provider_types():
                cfg = self._config.get_provider_config(ptype)
                if not cfg.api_key:
                    lines.append(f"{ptype:12} -- no API key configured, skipped")
                    continue
                try:
                    raw = set(_raw_model_ids(cfg))
                    offered = set()
                    for cap in ("text", "tts", "image"):
                        offered |= set(fetch_available_models(cfg, cap))
                    hidden = sorted(raw - offered)
                    lines.append(f"--- {ptype}: {len(raw)} returned, {len(hidden)} hidden ---")
                    for m in hidden:
                        lines.append(f"      {m}")
                except Exception as e:
                    lines.append(f"{ptype:12} ERROR  {e}")
                lines.append("")
            lines.append("These are hidden because calling them cannot work:")
            lines.append("  completions-only, deep-research, music, robotics, STT, computer-use.")
            return "\n".join(lines)

        self._run_async("Models hidden from the dropdowns", work)

    # ---- 3. live calls --------------------------------------------------

    def _active_cfg(self, capability: str) -> ProviderConfig:
        ptype = self._config.get_active_provider_type(capability)
        return self._config.get_provider_config(ptype)

    def _test_connection(self) -> None:
        def work() -> str:
            cfg = self._active_cfg("text")
            ok, message, detail = test_provider_connection(cfg)
            out = [f"provider : {cfg.provider_type}", f"model    : {cfg.text_model}"]
            out.append(f"result   : {'OK' if ok else 'FAILED'}")
            out.append(f"message  : {message}")
            out.append(f"detail   : {'present' if detail else 'none'}")
            return "\n".join(out)

        self._run_async("Connection test · active text provider", work)

    def _gen_text(self) -> None:
        def work() -> str:
            cfg = self._active_cfg("text")
            reply = create_text_provider(cfg).generate(
                "Reply with exactly the word OK and nothing else.", "Test connection."
            )
            return (
                f"provider : {cfg.provider_type}\n"
                f"model    : {cfg.text_model}\n"
                f"reply    : {reply.strip()!r}"
            )

        self._run_async("Generate text · active text provider", work)

    def _gen_image(self) -> None:
        def work() -> str:
            cfg = self._active_cfg("image")
            data = create_image_provider(cfg).generate_image(
                "A small red circle on a white background."
            )
            from ..media_handler import MediaHandler

            ext = MediaHandler._sniff_image_ext(data)
            return (
                f"provider : {cfg.provider_type}\n"
                f"model    : {cfg.image_model}\n"
                f"bytes    : {len(data)}\n"
                f"magic    : {data[:8].hex()} -> {_describe_bytes(data)}\n"
                f"saved as : .{ext}\n\n"
                "Gemini 3.x returns JPEG; it must save as .jpg, not .png."
            )

        self._run_async("Generate image · report detected format", work)

    def _gen_tts(self) -> None:
        def work() -> str:
            cfg = self._active_cfg("tts")
            data = create_tts_provider(cfg).synthesize(
                "This is a test of the speech synthesis pipeline.",
                language="en",
                voice=cfg.tts_voice,
                context="",
            )
            return (
                f"provider : {cfg.provider_type}\n"
                f"model    : {cfg.tts_model}\n"
                f"voice    : {cfg.tts_voice}\n"
                f"bytes    : {len(data)}\n"
                f"magic    : {data[:8].hex()} -> {_describe_bytes(data)}\n\n"
                "Google returns raw PCM; MediaHandler wraps it in a WAV header."
            )

        self._run_async("Synthesize speech · report detected format", work)

    # ---- 4. compatibility probe ----------------------------------------

    def _probe(self, ptypes: List[str]) -> Callable[[], str]:
        def work() -> str:
            lines = []
            for ptype in ptypes:
                cfg = self._config.get_provider_config(ptype)
                if not cfg.api_key:
                    lines.append(f"--- {ptype}: no API key configured, skipped ---")
                    continue
                lines.append(f"--- {ptype} ---")
                for model, why in _PROBE_MODELS.get(ptype, []):
                    probe_cfg = ProviderConfig(
                        provider_type=ptype,
                        api_url=cfg.api_url,
                        api_key=cfg.api_key,
                        text_model=model,
                        max_tokens=cfg.max_tokens,
                    )
                    started = time.time()
                    try:
                        reply = create_text_provider(probe_cfg).generate(
                            "Reply with exactly the word OK and nothing else.",
                            "Test connection.",
                        )
                        status = "OK   " if reply.strip() else "EMPTY"
                        note = repr(reply.strip()[:40])
                    except Exception as e:
                        status = "FAIL "
                        note = f"{e}"[:90]
                    lines.append(
                        f"  [{status}] {model:34} {time.time() - started:5.1f}s  "
                        f"({why})\n           {note}"
                    )
                lines.append("")
            lines.append("Entries marked 'expected clean error' should FAIL with a")
            lines.append("readable sentence, not a raw JSON body.")
            return "\n".join(lines)

        return work

    def _probe_active(self) -> None:
        ptype = self._config.get_active_provider_type("text")
        self._run_async(f"Compatibility probe · {ptype}", self._probe([ptype]))

    def _probe_all(self) -> None:
        self._run_async(
            "Compatibility probe · all providers",
            self._probe(list(_PROBE_MODELS.keys())),
        )


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
