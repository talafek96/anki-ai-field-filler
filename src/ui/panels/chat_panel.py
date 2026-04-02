"""AI Assistant side panel for the Anki Editor.

Provides a modern chat interface for brainstorming and custom field filling.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Callable

from aqt import mw
from aqt.editor import Editor
from aqt.qt import *
from aqt.utils import tooltip

from ...core.config import Config
from ...core.filler import Filler
from ..common.theme import (
    GLOBAL_STYLE,
    SIDEBAR_STYLE,
    CHAT_MESSAGE_LIST_STYLE,
    CHAT_INPUT_STYLE,
    CHAT_RECEPTION_NAME_STYLE,
    CHAT_APPLY_BUTTON_STYLE,
    get_chat_bubble_bot_style,
    get_chat_bubble_user_style,
    ACCENT_COLOR,
)


class ChatBubble(QWidget):
    """A single chat message bubble."""

    def __init__(
        self,
        text: str,
        is_user: bool = True,
        provider_icon: Optional[QIcon] = None,
        provider_name: str = "",
        on_apply: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__()
        self.text = text
        self.is_user = is_user
        self.on_apply = on_apply
        self._setup_ui(provider_icon, provider_name)

    def _setup_ui(self, icon: Optional[QIcon], name: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(2)

        # Header (Provider Name + Icon)
        if not self.is_user and (name or icon):
            header = QHBoxLayout()
            header.setContentsMargins(10, 0, 0, 0)
            header.setSpacing(6)
            
            if icon:
                icon_label = QLabel()
                icon_label.setPixmap(icon.pixmap(14, 14))
                header.addWidget(icon_label)
            
            if name:
                name_label = QLabel(name.upper())
                name_label.setStyleSheet(CHAT_RECEPTION_NAME_STYLE)
                header.addWidget(name_label)
            
            header.addStretch()
            layout.addLayout(header)

        # Bubble
        bubble = QLabel(self.text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setStyleSheet(
            get_chat_bubble_user_style() if self.is_user else get_chat_bubble_bot_style()
        )
        
        # Align bubble
        bubble_layout = QHBoxLayout()
        bubble_layout.setContentsMargins(0, 0, 0, 0)
        if self.is_user:
            bubble_layout.addStretch()
            bubble_layout.addWidget(bubble)
        else:
            bubble_layout.addWidget(bubble)
            bubble_layout.addStretch()
        
        layout.addLayout(bubble_layout)

        # Action Buttons for AI responses
        if not self.is_user and self.on_apply:
            actions = QHBoxLayout()
            actions.setContentsMargins(10, 0, 0, 0)
            
            apply_btn = QPushButton("Apply to Fields")
            apply_btn.setStyleSheet(CHAT_APPLY_BUTTON_STYLE)
            apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            qconnect(apply_btn.clicked, lambda: self.on_apply(self.text))
            
            actions.addWidget(apply_btn)
            actions.addStretch()
            layout.addLayout(actions)


class ChatPanel(QWidget):
    """Side panel for AI Chat and brainstorming."""

    def __init__(self, editor: Editor) -> None:
        super().__init__(editor.widget)
        self.editor = editor
        self.filler = Filler()
        self.messages: List[Dict[str, str]] = []
        self._checkboxes: Dict[str, QCheckBox] = {}
        
        self.setObjectName("aiChatPanel")
        self.setFixedWidth(350)
        self._load_icons()
        self._setup_ui()
        self.hide()

    def _load_icons(self) -> None:
        self.provider_icons: Dict[str, QIcon] = {}
        addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        icons_dir = os.path.join(addon_dir, "assets", "icons", "providers")
        
        for name in ["openai", "claude", "gemini", "vercel"]:
            path = os.path.join(icons_dir, f"{name}.svg")
            if os.path.exists(path):
                self.provider_icons[name] = QIcon(path)

    def _setup_ui(self) -> None:
        self.setStyleSheet(GLOBAL_STYLE + SIDEBAR_STYLE)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- Header ---
        header_widget = QWidget()
        header_widget.setStyleSheet(f"background-color: {SIDEBAR_STYLE.split('_BG_WINDOW};')[0].split(': ')[-1] if '_BG_WINDOW' in SIDEBAR_STYLE else 'transparent'}; border-bottom: 1px solid #444;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        title = QLabel("\u2728  AI Assistant")
        title.setObjectName("aiChatHeader")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        close_btn = QToolButton()
        close_btn.setText("\u2715")
        close_btn.setStyleSheet("border: none; font-size: 14px; color: #9CA3AF;")
        qconnect(close_btn.clicked, self.hide)
        
        clear_btn = QToolButton()
        clear_btn.setText("\u21BA")  # Refresh/Clear icon
        clear_btn.setToolTip("Clear chat history")
        clear_btn.setStyleSheet("border: none; font-size: 16px; color: #9CA3AF; margin-right: 5px;")
        qconnect(clear_btn.clicked, self.clear_chat)

        header_layout.addWidget(clear_btn)
        header_layout.addWidget(close_btn)
        
        main_layout.addWidget(header_widget)
        
        # --- Collapsible Fields Section ---
        self._fields_toggle = QPushButton("Target Fields \u25BE")
        self._fields_toggle.setStyleSheet("text-align: left; border: none; padding: 10px 15px; font-weight: 600; color: #9CA3AF; background: transparent;")
        self._fields_toggle.setCheckable(True)
        qconnect(self._fields_toggle.clicked, self._toggle_fields_visibility)
        main_layout.addWidget(self._fields_toggle)
        
        self._fields_container = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_container)
        self._fields_layout.setContentsMargins(15, 0, 15, 10)
        self._fields_layout.setSpacing(5)
        self._fields_container.hide()
        main_layout.addWidget(self._fields_container)
        
        # --- Chat History ---
        self._scroll = QScrollArea()
        self._scroll.setObjectName("aiChatScrollArea")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._history_widget = QWidget()
        self._history_layout = QVBoxLayout(self._history_widget)
        self._history_layout.setContentsMargins(10, 10, 10, 10)
        self._history_layout.setSpacing(10)
        self._history_layout.addStretch()
        
        self._scroll.setWidget(self._history_widget)
        main_layout.addWidget(self._scroll)
        
        # --- Input Area ---
        input_container = QWidget()
        input_container.setStyleSheet(f"border-top: 1px solid #444; padding: 10px;")
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(10, 10, 10, 10)
        
        self._input_edit = QPlainTextEdit()
        self._input_edit.setPlaceholderText("Ask anything or brainstorm ideas...")
        self._input_edit.setStyleSheet(CHAT_INPUT_STYLE)
        self._input_edit.setMaximumHeight(100)
        self._input_edit.setMinimumHeight(40)
        input_layout.addWidget(self._input_edit)
        
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        self._send_btn = QPushButton("Send")
        self._send_btn.setDefault(True)
        self._send_btn.setFixedWidth(80)
        qconnect(self._send_btn.clicked, self._on_send_clicked)
        btn_row.addWidget(self._send_btn)
        
        input_layout.addLayout(btn_row)
        main_layout.addWidget(input_container)

    def _toggle_fields_visibility(self) -> None:
        is_visible = self._fields_container.isVisible()
        self._fields_container.setVisible(not is_visible)
        self._fields_toggle.setText("Target Fields \u25B4" if not is_visible else "Target Fields \u25BE")

    def refresh_fields(self) -> None:
        """Update the field checkbox list based on the current note."""
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
        field_instructions = config.get_global_field_instructions(note_type_name)
        
        for name in note.keys():
            value = note[name].strip()
            cb = QCheckBox(name)
            cb.setStyleSheet("font-size: 11px;")
            
            if value:
                cb.setChecked(False)
                cb.setToolTip("Field has content. Checking will overwrite.")
            else:
                instr = field_instructions.get(name)
                cb.setChecked(instr.auto_fill if instr else True)
                
            self._checkboxes[name] = cb
            self._fields_layout.addWidget(cb)
        
        # Select All/None row
        btn_row = QHBoxLayout()
        all_btn = QPushButton("All")
        all_btn.setStyleSheet("font-size: 10px; padding: 2px 5px;")
        all_btn.setFixedWidth(40)
        qconnect(all_btn.clicked, lambda: [cb.setChecked(True) for cb in self._checkboxes.values()])
        
        none_btn = QPushButton("None")
        none_btn.setStyleSheet("font-size: 10px; padding: 2px 5px;")
        none_btn.setFixedWidth(40)
        qconnect(none_btn.clicked, lambda: [cb.setChecked(False) for cb in self._checkboxes.values()])
        
        btn_row.addWidget(all_btn)
        btn_row.addWidget(none_btn)
        btn_row.addStretch()
        self._fields_layout.addLayout(btn_row)

    def _on_send_clicked(self) -> None:
        text = self._input_edit.toPlainText().strip()
        if not text:
            return
            
        self._input_edit.clear()
        self.add_message(text, is_user=True)
        
        # Prepare context for AI
        context_messages = self._build_context_messages(text)
        
        self.filler.chat(
            messages=context_messages,
            on_success=self._on_ai_response,
            on_error=self._on_ai_error
        )
        
        # Show a "typing" bubble or disable input
        self._send_btn.setEnabled(False)
        self._input_edit.setPlaceholderText("Thinking...")

    def _build_context_messages(self, user_text: str) -> List[Dict[str, str]]:
        note = self.editor.note
        if not note:
            return [{"role": "user", "content": user_text}]
            
        # Add system context about the current note
        note_type = note.note_type()["name"]
        fields = {k: v for k, v in note.items()}
        
        system_content = f"You are an Anki AI assistant. Current Note Type: {note_type}\n"
        system_content += "Current Fields:\n"
        for k, v in fields.items():
            content = v[:200] + "..." if len(v) > 200 else v
            system_content += f"- {k}: {content or '(empty)'}\n"
        
        system_content += "\nHelp the user brainstorm or generate content for these fields. "
        system_content += "If you generate content they might want to use, provide it clearly."
        
        # Maintain a bit of history (last 10 messages)
        msgs = [{"role": "system", "content": system_content}]
        msgs.extend(self.messages[-10:])
        msgs.append({"role": "user", "content": user_text})
        return msgs

    def _on_ai_response(self, text: str) -> None:
        self._send_btn.setEnabled(True)
        self._input_edit.setPlaceholderText("Ask anything or brainstorm ideas...")
        self.add_message(text, is_user=False)

    def _on_ai_error(self, error: str) -> None:
        self._send_btn.setEnabled(True)
        self._input_edit.setPlaceholderText("Ask anything or brainstorm ideas...")
        self.add_message(f"Error: {error}", is_user=False)

    def add_message(self, text: str, is_user: bool) -> None:
        self.messages.append({"role": "user" if is_user else "assistant", "content": text})
        
        # Resolve provider info for assistant messages
        icon = None
        name = ""
        if not is_user:
            config = Config()
            prov_config = config.get_active_text_provider()
            ptype = prov_config.provider_type
            name = prov_config.text_model or ptype
            icon = self.provider_icons.get(ptype) or self.provider_icons.get("vercel")

        bubble = ChatBubble(
            text, 
            is_user=is_user, 
            provider_icon=icon, 
            provider_name=name,
            on_apply=self._on_apply_requested if not is_user else None
        )
        
        # Insert before the stretch
        self._history_layout.insertWidget(self._history_layout.count() - 1, bubble)
        
        # Scroll to bottom
        QTimer.singleShot(100, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _on_apply_requested(self, text: str) -> None:
        selected = [name for name, cb in self._checkboxes.items() if cb.isChecked()]
        if not selected:
            tooltip("No target fields selected. Open 'Target Fields' above to select.")
            return
            
        # Use the existing fill logic but pass the brainstormed text as custom instructions
        if hasattr(self, "on_fill_requested"):
            self.on_fill_requested(selected, f"Use this brainstormed content as the source: {text}")

    def clear_chat(self) -> None:
        """Clear all messages and history widgets."""
        self.messages.clear()
        # Remove all widgets from history layout (except the spacer at the end)
        while self._history_layout.count() > 1:
            item = self._history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        tooltip("Chat cleared.")

    def toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.refresh_fields()
            self.show()
            self._input_edit.setFocus()
