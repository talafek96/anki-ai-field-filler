"""AI Assistant side panel for the Anki Editor.

Provides a persistent interface for selecting fields to fill and entering custom instructions,
replacing the modal FillDialog for a more fluid experience.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from aqt.editor import Editor
from aqt.qt import *
from aqt.utils import tooltip

from ..core.config import Config, FieldInstruction
from .theme import GLOBAL_STYLE, SIDEBAR_STYLE, MUTED_LABEL_STYLE


class ChatPanel(QWidget):
    """Side panel for AI Chat and custom field filling."""

    def __init__(self, editor: Editor) -> None:
        super().__init__(editor.widget)
        self.editor = editor
        self._checkboxes: Dict[str, QCheckBox] = {}
        self.setObjectName("aiChatPanel")
        self.setFixedWidth(300)
        self._setup_ui()
        self.hide() # Hidden by default

    def _setup_ui(self) -> None:
        self.setStyleSheet(GLOBAL_STYLE + SIDEBAR_STYLE)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(15)
        
        # --- Header ---
        header = QLabel("\u2728  AI Assistant")
        header.setObjectName("aiChatHeader")
        layout.addWidget(header)
        
        # --- Scroll Area for fields ---
        scroll = QScrollArea()
        scroll.setObjectName("aiChatScrollArea")
        scroll.setWidgetResizable(True)
        
        self._scroll_widget = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_widget)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(10)
        
        self._fields_group = QGroupBox("Fields to Fill")
        self._fields_group.setObjectName("aiChatFieldsGroup")
        self._fields_layout = QVBoxLayout()
        self._fields_layout.setSpacing(8)
        self._fields_group.setLayout(self._fields_layout)
        
        self._scroll_layout.addWidget(self._fields_group)
        self._scroll_layout.addStretch()
        
        scroll.setWidget(self._scroll_widget)
        layout.addWidget(scroll)
        
        # --- Instructions ---
        instr_label = QLabel("Custom Instructions")
        instr_label.setStyleSheet("font-weight: 600; margin-top: 10px;")
        layout.addWidget(instr_label)
        
        self._prompt_edit = QPlainTextEdit()
        self._prompt_edit.setPlaceholderText("e.g. 'Translate to French', 'Summarize'...")
        self._prompt_edit.setMaximumHeight(100)
        layout.addWidget(self._prompt_edit)
        
        # --- Actions ---
        self._fill_btn = QPushButton("  \u2728  Fill Selected Fields  ")
        self._fill_btn.setObjectName("aiFillButton")
        self._fill_btn.setDefault(True)
        # Using a slight delay to ensure UI responsiveness
        qconnect(self._fill_btn.clicked, self._on_fill_clicked)
        layout.addWidget(self._fill_btn)
        
        self.setLayout(layout)

    def refresh_fields(self) -> None:
        """Update the field checkbox list based on the current note."""
        # Clear existing
        while self._fields_layout.count():
            item = self._fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._checkboxes.clear()
        
        note = self.editor.note
        if not note:
            return
            
        config = Config()
        note_type_name = note.note_type()["name"]
        # We don't easily have deck_name here without calling _current_deck_name from integration.py
        # For the panel, we'll use global instructions for now
        field_instructions = config.get_global_field_instructions(note_type_name)
        
        field_names = list(note.keys())
        for name in field_names:
            value = note[name].strip()
            cb = QCheckBox(name)
            
            if value:
                cb.setChecked(False)
                cb.setEnabled(True) # Allow overwriting in chat mode
                cb.setToolTip("Field has content. Checking will overwrite.")
            else:
                instr = field_instructions.get(name)
                auto_fill = instr.auto_fill if instr else True
                cb.setChecked(auto_fill)
                
            self._checkboxes[name] = cb
            self._fields_layout.addWidget(cb)
            
        # Select/Deselect all buttons
        btn_row = QHBoxLayout()
        sel_all = QPushButton("All")
        sel_all.setFixedWidth(60)
        sel_all.setStyleSheet("font-size: 11px; padding: 4px;")
        qconnect(sel_all.clicked, self._select_all)
        
        unsel_all = QPushButton("None")
        unsel_all.setFixedWidth(60)
        unsel_all.setStyleSheet("font-size: 11px; padding: 4px;")
        qconnect(unsel_all.clicked, self._deselect_all)
        
        btn_row.addWidget(sel_all)
        btn_row.addWidget(unsel_all)
        btn_row.addStretch()
        self._fields_layout.addLayout(btn_row)

    def _select_all(self) -> None:
        for cb in self._checkboxes.values():
            cb.setChecked(True)

    def _deselect_all(self) -> None:
        for cb in self._checkboxes.values():
            cb.setChecked(False)

    def _on_fill_clicked(self) -> None:
        selected = [name for name, cb in self._checkboxes.items() if cb.isChecked()]
        if not selected:
            tooltip("No fields selected.", parent=self)
            return
            
        prompt = self._prompt_edit.toPlainText().strip()
        
        # We need to call the fill logic from EditorIntegration
        # To avoid circular imports, we'll emit a signal or call a callback
        # For now, we'll assume the integration will handle it or we provide a callback
        if hasattr(self, "on_fill_requested"):
            self.on_fill_requested(selected, prompt)

    def toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.refresh_fields()
            self.show()
