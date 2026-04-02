"""Lightweight prompt dialog for single-field fill.

Shows just the field name and an optional prompt text area -- no field
selection checkboxes. Used when the user explicitly targets one field.
"""

from __future__ import annotations

from typing import Optional

from aqt.qt import *

from ..common.theme import GLOBAL_STYLE, HEADER_STYLE


class QuickPromptDialog(QDialog):
    """Minimal dialog: field name header + optional prompt + Fill/Cancel."""

    def __init__(
        self,
        field_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._field_name = field_name
        self._user_prompt: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("AI Filler")
        self.setMinimumWidth(400)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setStyleSheet(GLOBAL_STYLE)

        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        header = QLabel(f"\U0001f9e0  Fill <b>{self._field_name}</b> with AI")
        header.setStyleSheet(HEADER_STYLE)
        layout.addWidget(header)

        layout.addWidget(QLabel("Additional instructions (optional):"))
        self._prompt_edit = QPlainTextEdit()
        self._prompt_edit.setPlaceholderText(
            "Add any extra context to guide the AI for this field..."
        )
        self._prompt_edit.setMaximumHeight(80)
        layout.addWidget(self._prompt_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        qconnect(cancel_btn.clicked, self.reject)
        btn_layout.addWidget(cancel_btn)

        fill_btn = QPushButton("  \u2728  Fill  ")
        fill_btn.setDefault(True)
        qconnect(fill_btn.clicked, self._on_fill)
        btn_layout.addWidget(fill_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self._prompt_edit.setFocus()

    def _on_fill(self) -> None:
        self._user_prompt = self._prompt_edit.toPlainText().strip()
        self.accept()

    def get_user_prompt(self) -> Optional[str]:
        """Return the entered prompt, or None if cancelled."""
        return self._user_prompt
