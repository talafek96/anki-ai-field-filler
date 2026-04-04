"""Quick dialog for editing a single field's AI instruction.

Opened from the editor's right-click context menu for inline configuration.
"""

from __future__ import annotations

from typing import Optional

from aqt.qt import *

from ...core.config import Config, FieldInstruction
from ..common.theme import GLOBAL_STYLE, HEADER_STYLE
from ..common.widgets import create_auto_fill_checkbox, create_field_type_combo


class FieldInstructionDialog(QDialog):
    """Small dialog for editing the AI instruction for a single field."""

    def __init__(
        self,
        note_type_name: str,
        field_name: str,
        deck_name: Optional[str] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = Config()
        self._note_type_name = note_type_name
        self._field_name = field_name
        self._deck_name = deck_name
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        self.setWindowTitle(f"AI Instructions \u2014 {self._field_name}")
        self.setMinimumWidth(440)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setStyleSheet(GLOBAL_STYLE)

        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header with optional deck scope indicator
        scope = f" [{self._deck_name}]" if self._deck_name else ""
        header = QLabel(
            f"\U0001f4dd  <b>{self._field_name}</b>"
            f"<span style='color: #6B7280;'>"
            f" \u2014 {self._note_type_name}{scope}</span>"
        )
        header.setStyleSheet(HEADER_STYLE)
        layout.addWidget(header)

        # Scope selector
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Scope:"))
        self._scope_combo = QComboBox()
        self._scope_combo.addItem("All Decks (Global)", "")
        if self._deck_name:
            self._scope_combo.addItem(f"Deck: {self._deck_name}", self._deck_name)
            self._scope_combo.setCurrentIndex(1)
        scope_row.addWidget(self._scope_combo)
        scope_row.addStretch()
        layout.addLayout(scope_row)

        layout.addWidget(QLabel("Instruction for AI:"))
        self._instruction_edit = QPlainTextEdit()
        self._instruction_edit.setPlaceholderText(
            f"Describe what '{self._field_name}' should contain.\n"
            "This helps the AI generate appropriate content for this field.\n\n"
            "Examples:\n"
            '  "English definition of the word"\n'
            '  "Example sentence using this grammar point"\n'
            '  "Native pronunciation of the expression"'
        )
        self._instruction_edit.setMaximumHeight(120)
        layout.addWidget(self._instruction_edit)

        row = QHBoxLayout()
        row.addWidget(QLabel("Content Type:"))

        self._type_combo = create_field_type_combo()
        row.addWidget(self._type_combo)

        row.addSpacing(20)

        self._auto_fill_check = create_auto_fill_checkbox()
        row.addWidget(self._auto_fill_check)
        row.addStretch()

        layout.addLayout(row)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(button_box.accepted, self._save_and_close)
        qconnect(button_box.rejected, self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

        qconnect(self._scope_combo.currentIndexChanged, self._on_scope_changed)

    def _selected_deck(self) -> Optional[str]:
        """Return the deck name for the selected scope, or None for global."""
        return self._scope_combo.currentData() or None

    def _on_scope_changed(self, _index: int) -> None:
        self._load()

    def _load(self) -> None:
        deck = self._selected_deck()
        instructions = self._config.get_field_instructions(
            self._note_type_name, deck_name=deck
        )
        instr = instructions.get(self._field_name, FieldInstruction())
        self._instruction_edit.setPlainText(instr.instruction)
        idx = self._type_combo.findData(instr.field_type)
        if idx >= 0:
            self._type_combo.setCurrentIndex(idx)
        self._auto_fill_check.setChecked(instr.auto_fill)

    def _save_and_close(self) -> None:
        instruction = FieldInstruction(
            instruction=self._instruction_edit.toPlainText().strip(),
            field_type=self._type_combo.currentData(),
            auto_fill=self._auto_fill_check.isChecked(),
        )
        deck = self._selected_deck()
        self._config.set_field_instruction(
            self._note_type_name, self._field_name, instruction, deck_name=deck
        )
        self._config.write()
        self.accept()
