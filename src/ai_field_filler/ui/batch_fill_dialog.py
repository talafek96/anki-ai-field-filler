"""Batch fill dialog — field selection, prompt, and cost/dry-run controls.

Shown from the browser context menu when multiple cards are selected.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from aqt.qt import *

from ..config.config_manager import FieldInstruction
from . import install_wheel_guard
from .styles import GLOBAL_STYLE, HEADER_STYLE, MUTED_LABEL_STYLE

# Room left for the window frame and title bar, which ``sizeHint`` excludes.
_WINDOW_FRAME_ALLOWANCE = 60
# The field list never shrinks below this, so a few rows always show.
_MIN_FIELD_LIST_HEIGHT = 120
# Up to this many fields stay in one column; more split into two.
_SINGLE_COLUMN_MAX_FIELDS = 8


def field_grid_position(index: int, count: int) -> Tuple[int, int]:
    """Grid ``(row, column)`` for the *index*-th of *count* field checkboxes.

    Long lists split into two columns, filled top-to-bottom first so the
    note's field order still reads down the first column, then the second.
    """
    columns = 1 if count <= _SINGLE_COLUMN_MAX_FIELDS else 2
    rows = -(-count // columns)  # ceiling division
    return index % rows, index // rows


def field_list_height(content: int, chrome: int, available: int) -> int:
    """Height for the scrollable field list so the whole dialog fits on screen.

    *content* is the list's natural height, *chrome* the height of everything
    else in the dialog, *available* the usable screen height. The list shows
    in full when it fits; otherwise it takes the space that is left and
    scrolls, so the action buttons are never pushed off-screen (issue #17).
    """
    room = available - chrome - _WINDOW_FRAME_ALLOWANCE
    return max(min(content, room), min(content, _MIN_FIELD_LIST_HEIGHT))


class BatchFillDialog(QDialog):
    """Dialog for configuring a batch fill operation."""

    def __init__(
        self,
        note_count: int,
        note_type_name: str,
        field_names: List[str],
        field_instructions: Dict[str, FieldInstruction],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._note_count = note_count
        self._note_type_name = note_type_name
        self._field_names = field_names
        self._field_instructions = field_instructions
        self._checkboxes: Dict[str, QCheckBox] = {}
        self._result: Optional[Tuple[List[str], str, bool]] = None
        self._setup_ui()
        install_wheel_guard(self)

    def _setup_ui(self) -> None:
        self.setWindowTitle("AI Field Filler \u2014 Batch Fill")
        self.setMinimumWidth(480)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setStyleSheet(GLOBAL_STYLE())

        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header
        header = QLabel(f"\u2728  Batch Fill \u2014 {self._note_count} notes")
        header.setStyleSheet(HEADER_STYLE())
        layout.addWidget(header)

        sub = QLabel(f"Note type: <b>{self._note_type_name}</b>")
        sub.setStyleSheet(MUTED_LABEL_STYLE())
        layout.addWidget(sub)

        # Field selection
        fields_group = QGroupBox("Fields to Fill")
        fields_layout = QVBoxLayout()

        # Many fields would otherwise grow the dialog past the screen edge and
        # hide the buttons: they split into two columns, and if even that is
        # too tall for the screen the list scrolls.
        self._fields_scroll = QScrollArea()
        self._fields_scroll.setWidgetResizable(True)
        self._fields_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._fields_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Let the group box show through instead of the palette's window
        # colour. Object-name selectors so the rule doesn't cascade to the
        # checkboxes.
        viewport = self._fields_scroll.viewport()
        viewport.setObjectName("fieldsViewport")
        viewport.setStyleSheet("#fieldsViewport { background: transparent; }")
        self._fields_container = QWidget()
        self._fields_container.setObjectName("fieldsContainer")
        self._fields_container.setStyleSheet("#fieldsContainer { background: transparent; }")
        checks_layout = QGridLayout()
        checks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        checks_layout.setContentsMargins(0, 0, 0, 0)
        checks_layout.setVerticalSpacing(6)
        checks_layout.setHorizontalSpacing(24)

        for index, name in enumerate(self._field_names):
            cb = QCheckBox(name)
            instr = self._field_instructions.get(name)
            auto_fill = instr.auto_fill if instr else True
            cb.setChecked(auto_fill)
            if instr and instr.instruction:
                cb.setToolTip(instr.instruction)
            self._checkboxes[name] = cb
            row, column = field_grid_position(index, len(self._field_names))
            checks_layout.addWidget(cb, row, column)

        self._fields_container.setLayout(checks_layout)
        self._fields_scroll.setWidget(self._fields_container)
        fields_layout.addWidget(self._fields_scroll)

        btn_row = QHBoxLayout()
        select_all = QPushButton("Select All")
        qconnect(select_all.clicked, self._select_all)
        btn_row.addWidget(select_all)
        deselect_all = QPushButton("Deselect All")
        qconnect(deselect_all.clicked, self._deselect_all)
        btn_row.addWidget(deselect_all)
        btn_row.addStretch()
        fields_layout.addLayout(btn_row)

        fields_group.setLayout(fields_layout)
        layout.addWidget(fields_group)

        # Prompt
        prompt_group = QGroupBox("Additional Instructions (optional)")
        prompt_layout = QVBoxLayout()
        self._prompt_edit = QPlainTextEdit()
        self._prompt_edit.setPlaceholderText("Instructions applied to every note in the batch...")
        self._prompt_edit.setMaximumHeight(70)
        prompt_layout.addWidget(self._prompt_edit)
        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)

        # Cost warning + dry run
        info_row = QHBoxLayout()
        cost_label = QLabel(
            f"\u26a0\ufe0f  This will make up to <b>{self._note_count}</b> API calls."
        )
        cost_label.setStyleSheet(MUTED_LABEL_STYLE())
        info_row.addWidget(cost_label)
        info_row.addStretch()

        self._dry_run_check = QCheckBox("Dry run (preview only)")
        self._dry_run_check.setToolTip(
            "Simulate the batch without calling the AI.\n"
            "Shows which notes would be processed and how many fields would be targeted."
        )
        info_row.addWidget(self._dry_run_check)
        layout.addLayout(info_row)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        qconnect(cancel_btn.clicked, self.reject)
        btn_layout.addWidget(cancel_btn)
        self._fill_btn = QPushButton("  \u2728  Start Batch  ")
        self._fill_btn.setDefault(True)
        qconnect(self._fill_btn.clicked, self._on_fill)
        btn_layout.addWidget(self._fill_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        """Size the field list so the dialog, buttons included, fits the screen."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        content = self._fields_container.sizeHint().height()
        chrome = self.sizeHint().height() - self._fields_scroll.sizeHint().height()
        height = field_list_height(content, chrome, screen.availableGeometry().height())
        self._fields_scroll.setMinimumHeight(height)
        # Never taller than its content, so short lists leave no blank gap.
        self._fields_scroll.setMaximumHeight(content)
        self._fields_scroll.setMinimumWidth(self._fields_container.sizeHint().width())

    def _select_all(self) -> None:
        for cb in self._checkboxes.values():
            cb.setChecked(True)

    def _deselect_all(self) -> None:
        for cb in self._checkboxes.values():
            cb.setChecked(False)

    def _on_fill(self) -> None:
        selected = [n for n, cb in self._checkboxes.items() if cb.isChecked()]
        if not selected:
            return
        self._result = (
            selected,
            self._prompt_edit.toPlainText().strip(),
            self._dry_run_check.isChecked(),
        )
        self.accept()

    def get_result(self) -> Optional[Tuple[List[str], str, bool]]:
        """Return (fields, prompt, dry_run) or None if cancelled."""
        return self._result
