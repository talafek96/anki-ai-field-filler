"""Quick dialog for editing a single field's AI instruction.

Opened from the editor's right-click context menu for inline configuration.
"""

from __future__ import annotations

from aqt.qt import *

from ..config_manager import ConfigManager, FieldInstruction

FIELD_TYPES = ["auto", "text", "audio", "image"]


class FieldInstructionDialog(QDialog):
    """Small dialog for editing the AI instruction for a single field."""

    def __init__(
        self,
        note_type_name: str,
        field_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = ConfigManager()
        self._note_type_name = note_type_name
        self._field_name = field_name
        self._setup_ui()
        self._load()

    def _setup_ui(self) -> None:
        self.setWindowTitle(f"AI Instructions — {self._field_name}")
        self.setMinimumWidth(420)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        layout = QVBoxLayout()
        layout.setSpacing(10)

        header = QLabel(
            f"<b>{self._field_name}</b>"
            f"<span style='color: gray;'> — {self._note_type_name}</span>"
        )
        layout.addWidget(header)

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

        self._type_combo = QComboBox()
        self._type_combo.setToolTip(
            "auto: let the AI decide the best type\n"
            "text: plain text or HTML content\n"
            "audio: generate TTS audio file\n"
            "image: generate an image"
        )
        for ft in FIELD_TYPES:
            self._type_combo.addItem(ft.capitalize(), ft)
        row.addWidget(self._type_combo)

        row.addSpacing(20)

        self._auto_fill_check = QCheckBox("Include in auto-fill")
        self._auto_fill_check.setToolTip(
            "When checked, this field will be included when using "
            "'Fill All Blank Fields'."
        )
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

    def _load(self) -> None:
        instructions = self._config.get_field_instructions(
            self._note_type_name
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
        self._config.set_field_instruction(
            self._note_type_name, self._field_name, instruction
        )
        self._config.write()
        self.accept()
