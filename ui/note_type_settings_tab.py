"""Note type field instructions settings tab."""

from __future__ import annotations

from typing import Optional

from aqt import mw
from aqt.qt import *

from ..config_manager import ConfigManager, FieldInstruction
from . import create_auto_fill_checkbox, create_field_type_combo
from .styles import palette


class _ResizeHandle(QWidget):
    """Thin draggable bar below a text edit for vertical resizing.

    Draws three short horizontal grip lines as a visual indicator.
    """

    def __init__(self, target: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target = target
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_h = 0
        self.setFixedHeight(14)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Drag to resize")

    def paintEvent(self, event: object) -> None:
        """Draw three short horizontal lines as a grip indicator."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(palette()["resize_handle"]))
        pen.setWidth(1)
        p.setPen(pen)
        cx = self.width() // 2
        half_w = 16
        for dy in (-3, 0, 3):
            y = self.height() // 2 + dy
            p.drawLine(cx - half_w, y, cx + half_w, y)
        p.end()

    def mousePressEvent(self, event: object) -> None:
        e = event  # type: ignore[assignment]
        self._dragging = True
        self._drag_start_y = int(e.globalPosition().y())
        self._drag_start_h = self._target.height()
        e.accept()

    def mouseMoveEvent(self, event: object) -> None:
        e = event  # type: ignore[assignment]
        if self._dragging:
            delta = int(e.globalPosition().y()) - self._drag_start_y
            new_h = max(48, self._drag_start_h + delta)
            self._target.setFixedHeight(new_h)
            e.accept()

    def mouseReleaseEvent(self, event: object) -> None:
        if self._dragging:
            self._dragging = False
            self._target.setMinimumHeight(self._target.height())
            self._target.setMaximumHeight(16777215)
            event.accept()  # type: ignore[union-attr]


class NoteTypeSettingsTab(QWidget):
    """Tab for configuring per-note-type, per-field AI instructions."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._current_note_type: str | None = None
        # The deck scope that was active when fields were last loaded.
        # None = global, otherwise a deck name.
        self._loaded_deck: str | None = None
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

        # Deck scope selector (single-select)
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Scope:"))
        self._deck_combo = QComboBox()
        self._deck_combo.setMinimumWidth(220)
        self._deck_combo.setToolTip(
            "Select 'All Decks (Global)' to edit base instructions,\n"
            "or pick a specific deck to set overrides for that deck.\n"
            "Deck overrides are merged on top of global at fill time."
        )
        self._load_deck_combo()
        qconnect(self._deck_combo.currentIndexChanged, self._on_deck_changed)
        scope_row.addWidget(self._deck_combo)
        scope_row.addStretch()
        right_panel.addLayout(scope_row)

        info_label = QLabel(
            "Describe what each field should contain. The AI uses these "
            "instructions along with already-filled fields to generate "
            "appropriate content."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"color: {palette()['text_muted']}; margin-bottom: 6px;")
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

    def _load_deck_combo(self) -> None:
        self._deck_combo.blockSignals(True)
        self._deck_combo.clear()
        self._deck_combo.addItem("All Decks (Global)", "")
        if mw.col:
            for deck in sorted(mw.col.decks.all_names_and_ids(), key=lambda d: d.name):
                self._deck_combo.addItem(f"\u2514 {deck.name}", deck.name)
        self._deck_combo.blockSignals(False)

    def _selected_deck(self) -> Optional[str]:
        """Return the selected deck name, or None for global."""
        return self._deck_combo.currentData() or None

    def _on_deck_changed(self, _index: int) -> None:
        # Save under the previously loaded scope before switching
        self._save_current_note_type()
        if self._current_note_type:
            self._load_fields(self._current_note_type)

    def _load_note_types(self) -> None:
        if not mw.col:
            return
        self._note_type_list.clear()
        for model in mw.col.models.all_names_and_ids():
            item = QListWidgetItem(model.name)
            item.setData(Qt.ItemDataRole.UserRole, model.name)
            self._note_type_list.addItem(item)

    def _on_note_type_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        if previous and self._current_note_type:
            self._save_current_note_type()

        if not current:
            return

        nt_name = current.data(Qt.ItemDataRole.UserRole)
        self._current_note_type = nt_name
        self._load_fields(nt_name)

    def _load_fields(self, note_type_name: str) -> None:
        # Snapshot the scope we're loading for
        self._loaded_deck = self._selected_deck()

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
        deck = self._loaded_deck
        if deck:
            # Deck scope: show merged (global + deck overrides)
            instructions = self._config.get_field_instructions(note_type_name, deck_name=deck)
        else:
            instructions = self._config.get_global_field_instructions(note_type_name)

        for fname in field_names:
            instr = instructions.get(fname, FieldInstruction())

            group = QGroupBox(fname)
            group_layout = QVBoxLayout()
            group_layout.setSpacing(4)
            group_layout.setContentsMargins(10, 14, 10, 10)

            instruction_edit = QPlainTextEdit()
            instruction_edit.setPlaceholderText(
                f"Describe what '{fname}' should contain.\n"
                "Example: 'English definition of the word' or "
                "'Native pronunciation of the expression'"
            )
            instruction_edit.setMinimumHeight(48)
            instruction_edit.setPlainText(instr.instruction)
            group_layout.addWidget(instruction_edit)

            handle = _ResizeHandle(instruction_edit)
            group_layout.addWidget(handle)

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
        if not self._current_note_type or not self._field_widgets:
            return

        deck = self._loaded_deck
        for fname, instr_edit, type_combo, auto_check in self._field_widgets:
            instruction = FieldInstruction(
                instruction=instr_edit.toPlainText().strip(),
                field_type=type_combo.currentData(),
                auto_fill=auto_check.isChecked(),
            )
            self._config.set_field_instruction(
                self._current_note_type,
                fname,
                instruction,
                deck_name=deck,
            )

    def save(self) -> None:
        """Save current note type's field instructions."""
        self._save_current_note_type()
