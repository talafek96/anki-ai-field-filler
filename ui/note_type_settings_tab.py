"""Note type field instructions settings tab."""

from __future__ import annotations

from aqt import mw
from aqt.qt import *

from ..config_manager import ConfigManager, FieldInstruction
from . import create_auto_fill_checkbox, create_field_type_combo


class NoteTypeSettingsTab(QWidget):
    """Tab for configuring per-note-type, per-field AI instructions."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._current_note_type: str | None = None
        self._field_widgets: list[tuple[str, QPlainTextEdit, QComboBox, QCheckBox]] = []
        self._setup_ui()
        self._load_note_types()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        # --- Left panel: note type list ---
        left_panel = QVBoxLayout()
        left_label = QLabel("Note Types:")
        left_label.setStyleSheet("font-weight: bold;")
        left_panel.addWidget(left_label)

        self._note_type_list = QListWidget()
        self._note_type_list.setMaximumWidth(220)
        self._note_type_list.setMinimumWidth(160)
        qconnect(
            self._note_type_list.currentItemChanged,
            self._on_note_type_changed,
        )
        left_panel.addWidget(self._note_type_list)
        layout.addLayout(left_panel)

        # --- Right panel: field instructions ---
        right_panel = QVBoxLayout()
        right_label = QLabel("Field Instructions:")
        right_label.setStyleSheet("font-weight: bold;")
        right_panel.addWidget(right_label)

        info_label = QLabel(
            "Describe what each field should contain. The AI uses these "
            "instructions along with already-filled fields to generate "
            "appropriate content."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; margin-bottom: 6px;")
        right_panel.addWidget(info_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._fields_container = QWidget()
        self._fields_layout = QVBoxLayout()
        self._fields_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._fields_layout.setSpacing(8)
        self._fields_container.setLayout(self._fields_layout)
        scroll.setWidget(self._fields_container)
        right_panel.addWidget(scroll)

        layout.addLayout(right_panel, stretch=1)
        self.setLayout(layout)

    def _load_note_types(self) -> None:
        if not mw.col:
            return
        self._note_type_list.clear()
        for model in mw.col.models.all_names_and_ids():
            item = QListWidgetItem(model.name)
            item.setData(Qt.ItemDataRole.UserRole, model.name)
            self._note_type_list.addItem(item)

    def _on_note_type_changed(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        if previous and self._current_note_type:
            self._save_current_note_type()

        if not current:
            return

        nt_name = current.data(Qt.ItemDataRole.UserRole)
        self._current_note_type = nt_name
        self._load_fields(nt_name)

    def _load_fields(self, note_type_name: str) -> None:
        self._field_widgets.clear()
        while self._fields_layout.count():
            item = self._fields_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not mw.col:
            return

        note_type = None
        for model in mw.col.models.all_names_and_ids():
            if model.name == note_type_name:
                note_type = mw.col.models.get(model.id)
                break
        if not note_type:
            return

        field_names = [f["name"] for f in note_type["flds"]]
        instructions = self._config.get_field_instructions(note_type_name)

        for fname in field_names:
            instr = instructions.get(fname, FieldInstruction())

            group = QGroupBox(fname)
            group_layout = QVBoxLayout()
            group_layout.setSpacing(6)
            group_layout.setContentsMargins(10, 14, 10, 10)

            instruction_edit = QPlainTextEdit()
            instruction_edit.setPlaceholderText(
                f"Describe what '{fname}' should contain.\n"
                "Example: 'English definition of the word' or "
                "'Native pronunciation of the expression'"
            )
            instruction_edit.setMaximumHeight(56)
            instruction_edit.setPlainText(instr.instruction)
            group_layout.addWidget(instruction_edit)

            row = QHBoxLayout()
            row.addWidget(QLabel("Content Type:"))

            type_combo = create_field_type_combo()
            idx = type_combo.findData(instr.field_type)
            if idx >= 0:
                type_combo.setCurrentIndex(idx)
            row.addWidget(type_combo)

            row.addSpacing(20)

            auto_fill_check = create_auto_fill_checkbox()
            auto_fill_check.setChecked(instr.auto_fill)
            row.addWidget(auto_fill_check)
            row.addStretch()

            group_layout.addLayout(row)
            group.setLayout(group_layout)
            self._fields_layout.addWidget(group)

            self._field_widgets.append((fname, instruction_edit, type_combo, auto_fill_check))

    def _save_current_note_type(self) -> None:
        if not self._current_note_type:
            return
        for fname, instr_edit, type_combo, auto_check in self._field_widgets:
            instruction = FieldInstruction(
                instruction=instr_edit.toPlainText().strip(),
                field_type=type_combo.currentData(),
                auto_fill=auto_check.isChecked(),
            )
            self._config.set_field_instruction(self._current_note_type, fname, instruction)

    def save(self) -> None:
        """Save current note type's field instructions."""
        self._save_current_note_type()
