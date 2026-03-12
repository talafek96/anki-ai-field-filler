"""Note type field instructions settings tab."""

from __future__ import annotations

from typing import Optional

from aqt import mw
from aqt.qt import *

from ..config_manager import ConfigManager, FieldInstruction
from . import create_auto_fill_checkbox, create_field_type_combo


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
        pen = QPen(QColor("#B0B7C3"))
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


class _DeckScopeCombo(QComboBox):
    """Compact dropdown with checkable deck items for multi-deck selection.

    First item is always "All Decks (Global)". When it is checked (or no
    specific deck is checked) the scope is global. Otherwise the scope
    consists of every checked deck.
    """

    scope_changed = pyqtSignal()

    _GLOBAL_LABEL = "All Decks (Global)"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(220)
        self.setToolTip(
            "Select which decks these instructions apply to.\n"
            "Leave on 'All Decks' for global instructions, or\n"
            "check specific decks for overrides."
        )

        self._model = QStandardItemModel(self)
        self.setModel(self._model)

        # Global item (always index 0)
        global_item = QStandardItem(self._GLOBAL_LABEL)
        global_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        global_item.setCheckState(Qt.CheckState.Checked)
        self._model.appendRow(global_item)

        # Deck items
        if mw.col:
            for deck in sorted(mw.col.decks.all_names_and_ids(), key=lambda d: d.name):
                item = QStandardItem(deck.name)
                item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                item.setCheckState(Qt.CheckState.Unchecked)
                self._model.appendRow(item)

        self._model.itemChanged.connect(self._on_item_changed)
        self._updating = False
        self._refresh_display_text()

    def _on_item_changed(self, item: QStandardItem) -> None:
        if self._updating:
            return
        self._updating = True

        global_item = self._model.item(0)
        if item is global_item:
            # If global was just checked, uncheck all decks
            if item.checkState() == Qt.CheckState.Checked:
                for i in range(1, self._model.rowCount()):
                    self._model.item(i).setCheckState(Qt.CheckState.Unchecked)
        else:
            # A deck was toggled — uncheck global if any deck is checked
            any_deck = any(
                self._model.item(i).checkState() == Qt.CheckState.Checked
                for i in range(1, self._model.rowCount())
            )
            global_item.setCheckState(
                Qt.CheckState.Unchecked if any_deck else Qt.CheckState.Checked
            )

        self._updating = False
        self._refresh_display_text()
        self.scope_changed.emit()

    def _refresh_display_text(self) -> None:
        decks = self.checked_decks()
        if not decks:
            text = self._GLOBAL_LABEL
        elif len(decks) == 1:
            text = decks[0]
        else:
            text = f"{len(decks)} decks selected"
        # Show summary in the collapsed combo text
        self.setCurrentIndex(-1)
        self.setEditText(text)
        self.lineEdit().setReadOnly(True) if self.lineEdit() else None

    def paintEvent(self, event: object) -> None:
        """Override to show our custom text instead of the current item."""
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        decks = self.checked_decks()
        if not decks:
            opt.currentText = self._GLOBAL_LABEL
        elif len(decks) == 1:
            opt.currentText = decks[0]
        else:
            opt.currentText = f"{len(decks)} decks selected"
        p = QStylePainter(self)
        p.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        p.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opt)

    def is_global(self) -> bool:
        return self._model.item(0).checkState() == Qt.CheckState.Checked

    def checked_decks(self) -> list[str]:
        """Return the list of checked deck names (empty if global)."""
        decks = []
        for i in range(1, self._model.rowCount()):
            item = self._model.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                decks.append(item.text())
        return decks

    def set_scope(self, deck_names: list[str]) -> None:
        """Set the scope — empty list = global, otherwise check those decks."""
        self._updating = True
        names_set = set(deck_names)
        if not deck_names:
            self._model.item(0).setCheckState(Qt.CheckState.Checked)
            for i in range(1, self._model.rowCount()):
                self._model.item(i).setCheckState(Qt.CheckState.Unchecked)
        else:
            self._model.item(0).setCheckState(Qt.CheckState.Unchecked)
            for i in range(1, self._model.rowCount()):
                item = self._model.item(i)
                state = (
                    Qt.CheckState.Checked if item.text() in names_set else Qt.CheckState.Unchecked
                )
                item.setCheckState(state)
        self._updating = False
        self._refresh_display_text()


class NoteTypeSettingsTab(QWidget):
    """Tab for configuring per-note-type, per-field AI instructions."""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self._config = config
        self._current_note_type: str | None = None
        # Track the scope that was active when the fields were loaded,
        # so _save_current_note_type writes to the correct place even
        # after the dropdown has already changed.
        self._loaded_scope_global: bool = True
        self._loaded_scope_decks: list[str] = []
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

        # Deck scope selector
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Scope:"))
        self._scope_widget = _DeckScopeCombo()
        self._scope_widget.scope_changed.connect(self._on_scope_changed)
        scope_row.addWidget(self._scope_widget)
        scope_row.addStretch()
        right_panel.addLayout(scope_row)

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

    def _on_scope_changed(self) -> None:
        # Save under the *previous* scope before reloading
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

    def _effective_deck(self) -> Optional[str]:
        """Return the first checked deck for loading, or None for global."""
        decks = self._scope_widget.checked_decks()
        return decks[0] if decks else None

    def _load_fields(self, note_type_name: str) -> None:
        # Snapshot the current scope so save writes to the right place
        self._loaded_scope_global = self._scope_widget.is_global()
        self._loaded_scope_decks = list(self._scope_widget.checked_decks())

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
        deck = self._effective_deck()
        if deck:
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

        for fname, instr_edit, type_combo, auto_check in self._field_widgets:
            instruction = FieldInstruction(
                instruction=instr_edit.toPlainText().strip(),
                field_type=type_combo.currentData(),
                auto_fill=auto_check.isChecked(),
            )
            if self._loaded_scope_global:
                self._config.set_field_instruction(self._current_note_type, fname, instruction)
            else:
                for deck_name in self._loaded_scope_decks:
                    self._config.set_field_instruction(
                        self._current_note_type,
                        fname,
                        instruction,
                        deck_name=deck_name,
                    )

    def save(self) -> None:
        """Save current note type's field instructions."""
        self._save_current_note_type()
