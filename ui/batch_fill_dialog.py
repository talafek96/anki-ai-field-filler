"""Batch fill dialog — field selection, prompt, and cost/dry-run controls.

Shown from the browser context menu when multiple cards are selected.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from aqt.qt import *

from ..config_manager import FieldInstruction
from .styles import GLOBAL_STYLE, HEADER_STYLE, MUTED_LABEL_STYLE


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

    def _setup_ui(self) -> None:
        self.setWindowTitle("AI Field Filler \u2014 Batch Fill")
        self.setMinimumWidth(480)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setStyleSheet(GLOBAL_STYLE)

        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header
        header = QLabel(f"\u2728  Batch Fill \u2014 {self._note_count} notes")
        header.setStyleSheet(HEADER_STYLE)
        layout.addWidget(header)

        sub = QLabel(f"Note type: <b>{self._note_type_name}</b>")
        sub.setStyleSheet(MUTED_LABEL_STYLE)
        layout.addWidget(sub)

        # Field selection
        fields_group = QGroupBox("Fields to Fill")
        fields_layout = QVBoxLayout()
        fields_layout.setSpacing(6)

        for name in self._field_names:
            cb = QCheckBox(name)
            instr = self._field_instructions.get(name)
            auto_fill = instr.auto_fill if instr else True
            cb.setChecked(auto_fill)
            if instr and instr.instruction:
                cb.setToolTip(instr.instruction)
            self._checkboxes[name] = cb
            fields_layout.addWidget(cb)

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
        cost_label.setStyleSheet(MUTED_LABEL_STYLE)
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
