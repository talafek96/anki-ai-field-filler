"""Fill activation dialog.

Shown when the user triggers a fill action with show_fill_dialog enabled.
Allows selecting which fields to fill and adding an optional prompt.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from aqt.qt import *

from ...core.config import FieldInstruction
from ..common.icons import get_themed_icon
from ..common.theme import GLOBAL_STYLE, HEADER_STYLE, MUTED_LABEL_STYLE


class FillDialog(QDialog):
    """Dialog for selecting fields to fill and providing optional instructions."""

    def __init__(
        self,
        field_names: List[str],
        field_values: Dict[str, str],
        field_instructions: Dict[str, FieldInstruction],
        pre_selected: Optional[List[str]] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._field_names = field_names
        self._field_values = field_values
        self._field_instructions = field_instructions
        self._pre_selected = pre_selected or []
        self._checkboxes: Dict[str, QCheckBox] = {}
        self._result: Optional[Tuple[List[str], str]] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("AI Filler")
        self.setMinimumWidth(440)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setStyleSheet(GLOBAL_STYLE)

        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # --- Header ---
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        # Icon
        addon_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        sparkles_icon = os.path.join(
            addon_dir, "assets", "icons", "app", "sparkles.svg"
        )

        icon_label = QLabel()
        icon_label.setPixmap(get_themed_icon(sparkles_icon, 20).pixmap(20, 20))
        header_row.addWidget(icon_label)

        header = QLabel("Fields to Generate")
        header.setStyleSheet(HEADER_STYLE)
        header_row.addWidget(header)
        header_row.addStretch()

        layout.addLayout(header_row)

        # --- Field selection ---
        fields_group = QGroupBox("Fields")
        fields_layout = QVBoxLayout()
        fields_layout.setSpacing(6)

        for name in self._field_names:
            value = self._field_values.get(name, "").strip()
            cb = QCheckBox(name)

            if value:
                cb.setChecked(False)
                cb.setEnabled(False)
                preview = value[:80].replace("\n", " ")
                if len(value) > 80:
                    preview += "..."
                cb.setToolTip(f"Already filled: {preview}")
                cb.setStyleSheet(MUTED_LABEL_STYLE)
            else:
                is_pre_selected = not self._pre_selected or name in self._pre_selected
                instr = self._field_instructions.get(name)
                auto_fill = instr.auto_fill if instr else True
                cb.setChecked(is_pre_selected and auto_fill)
                if not auto_fill:
                    cb.setToolTip("Auto-fill is disabled for this field in settings")

            self._checkboxes[name] = cb
            fields_layout.addWidget(cb)

        # Select/deselect all buttons
        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        qconnect(select_all_btn.clicked, self._select_all)
        btn_row.addWidget(select_all_btn)
        deselect_all_btn = QPushButton("Deselect All")
        qconnect(deselect_all_btn.clicked, self._deselect_all)
        btn_row.addWidget(deselect_all_btn)
        btn_row.addStretch()
        fields_layout.addLayout(btn_row)

        fields_group.setLayout(fields_layout)
        layout.addWidget(fields_group)

        # --- User prompt ---
        prompt_group = QGroupBox("Prompt / Instructions")
        prompt_layout = QVBoxLayout()
        self._prompt_edit = QPlainTextEdit()
        self._prompt_edit.setPlaceholderText(
            "Add any additional context or instructions for the AI...\n"
            "e.g. 'Use simple vocabulary' or 'Include romaji readings'"
        )
        self._prompt_edit.setMaximumHeight(80)
        prompt_layout.addWidget(self._prompt_edit)
        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)

        # --- Buttons ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        qconnect(cancel_btn.clicked, self.reject)
        button_layout.addWidget(cancel_btn)

        self._fill_btn = QPushButton(" Fill Fields ")
        self._fill_btn.setDefault(True)
        qconnect(self._fill_btn.clicked, self._on_fill)
        button_layout.addWidget(self._fill_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _select_all(self) -> None:
        for cb in self._checkboxes.values():
            if cb.isEnabled():
                cb.setChecked(True)

    def _deselect_all(self) -> None:
        for cb in self._checkboxes.values():
            if cb.isEnabled():
                cb.setChecked(False)

    def _on_fill(self) -> None:
        selected = [name for name, cb in self._checkboxes.items() if cb.isChecked()]
        if not selected:
            return
        self._result = (selected, self._prompt_edit.toPlainText().strip())
        self.accept()

    def get_result(self) -> Optional[Tuple[List[str], str]]:
        """Get the dialog result: (selected_fields, user_prompt) or None."""
        return self._result
