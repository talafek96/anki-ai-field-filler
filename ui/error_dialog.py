"""Error dialog with an expandable, scrollable details pane.

``showWarning()`` renders everything as one non-scrollable label, so a raw
API error body produces a dialog taller than the screen with no way to
scroll or copy it.  :class:`ErrorDialog` shows the one-line summary up top
and hides the payload behind a "Show details" toggle, pretty-printed in a
monospace, selectable, scrollable box.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from aqt.qt import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFont,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    qconnect,
)

from .styles import GLOBAL_STYLE, palette

# Matches the first {...} or [...] block in a string, so a JSON body that
# was concatenated into a message can still be pretty-printed.
_JSON_BLOCK = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


def _prettify(text: str) -> str:
    """Pretty-print *text* if it is (or contains) a JSON document."""
    stripped = text.strip()
    if not stripped:
        return text
    try:
        return json.dumps(json.loads(stripped), indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        pass

    match = _JSON_BLOCK.search(stripped)
    if match:
        try:
            parsed = json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            return text
        pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
        return (stripped[: match.start()] + pretty + stripped[match.end() :]).strip()
    return text


def _monospace_font() -> QFont:
    font = QFont("Consolas")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSize(9)
    return font


class ErrorDialog(QDialog):
    """Modal error dialog with a collapsible details pane."""

    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        *,
        title: str = "AI Field Filler",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet(GLOBAL_STYLE())
        self.setMinimumWidth(480)

        p = palette()
        layout = QVBoxLayout()
        layout.setSpacing(12)

        heading = QLabel(message)
        heading.setWordWrap(True)
        heading.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        heading.setStyleSheet(f"color: {p['text_primary']}; font-size: 13px;")
        layout.addWidget(heading)

        self._detail_text = _prettify(detail) if detail else ""

        if self._detail_text:
            self._detail_box = QPlainTextEdit(self._detail_text)
            self._detail_box.setReadOnly(True)
            self._detail_box.setFont(_monospace_font())
            self._detail_box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self._detail_box.setMinimumHeight(240)
            self._detail_box.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self._detail_box.setVisible(False)
            layout.addWidget(self._detail_box)

            self._toggle_btn = QPushButton("Show details")
            self._toggle_btn.setCheckable(True)
            qconnect(self._toggle_btn.toggled, self._on_toggle)

            self._copy_btn = QPushButton("Copy")
            self._copy_btn.setVisible(False)
            qconnect(self._copy_btn.clicked, self._copy_detail)

            row = QHBoxLayout()
            row.addWidget(self._toggle_btn)
            row.addWidget(self._copy_btn)
            row.addStretch()
            layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        qconnect(buttons.accepted, self.accept)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def _on_toggle(self, checked: bool) -> None:
        self._detail_box.setVisible(checked)
        self._copy_btn.setVisible(checked)
        self._toggle_btn.setText("Hide details" if checked else "Show details")
        if checked:
            self.resize(max(self.width(), 720), 520)
        else:
            # Let the dialog shrink back around the summary.
            self.adjustSize()

    def _copy_detail(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._detail_text)
        self._copy_btn.setText("Copied")

    @property
    def detail_text(self) -> str:
        """The prettified detail payload (empty when there is none)."""
        return self._detail_text


def show_error(
    message: str,
    detail: Optional[str] = None,
    *,
    title: str = "AI Field Filler",
    parent=None,
) -> None:
    """Show :class:`ErrorDialog` modally."""
    ErrorDialog(message, detail, title=title, parent=parent).exec()


def show_exception(
    exc: BaseException,
    *,
    prefix: str = "",
    title: str = "AI Field Filler",
    parent=None,
) -> None:
    """Show an exception, using its ``detail`` payload when it has one."""
    message = f"{prefix}{exc}" if prefix else str(exc)
    show_error(message, getattr(exc, "detail", None), title=title, parent=parent)
