"""Editor integration: toolbar buttons and right-click context menu."""

from __future__ import annotations

from typing import List, Optional

from aqt import gui_hooks, mw
from aqt.editor import Editor, EditorWebView
from aqt.qt import QDialog, QMenu, qconnect
from aqt.utils import showWarning, tooltip

from .config_manager import ConfigManager, FieldInstruction
from .field_filler import FieldFiller
from .ui.field_instruction_dialog import FieldInstructionDialog
from .ui.fill_dialog import FillDialog
from .ui.generating_dialog import GeneratingDialog
from .ui.quick_prompt_dialog import QuickPromptDialog


def _current_deck_name(editor: Editor) -> Optional[str]:
    """Best-effort resolve the deck name for the note being edited.

    * In the *Add* dialog the deck is available via ``editor.parentWindow``.
    * When *browsing / editing* an existing note we look at the first card's
      deck id.
    * Falls back to ``None`` (= use global instructions only).
    """
    note = editor.note
    if note is None:
        return None

    # Editing an existing note — look at its first card
    if note.id:
        cards = note.cards()
        if cards:
            deck = mw.col.decks.get(cards[0].did)
            if deck:
                return deck["name"]

    # Add dialog — the parent window usually exposes .deckChooser
    parent = getattr(editor, "parentWindow", None)
    chooser = getattr(parent, "deckChooser", None)
    if chooser:
        did = chooser.selectedId()
        deck = mw.col.decks.get(did)
        if deck:
            return deck["name"]

    return None


class EditorIntegration:
    """Manages editor toolbar buttons and context menu items."""

    _filler: FieldFiller | None = None

    @classmethod
    def init(cls) -> None:
        """Register all editor hooks."""
        cls._filler = FieldFiller()
        gui_hooks.editor_did_init_buttons.append(cls._add_toolbar_buttons)
        gui_hooks.editor_will_show_context_menu.append(cls._add_context_menu)
        gui_hooks.editor_did_init.append(cls._inject_button_style)

    @classmethod
    def _inject_button_style(cls, editor: Editor) -> None:
        """Inject CSS into the editor webview to style our toolbar buttons."""
        css = """
        (function() {
            if (document.getElementById('ai-filler-style')) return;
            var s = document.createElement('style');
            s.id = 'ai-filler-style';
            s.textContent = `
                button[title^="AI:"] {
                    background: linear-gradient(135deg, #6366F1, #8B5CF6) !important;
                    color: white !important;
                    border: none !important;
                    border-radius: 6px !important;
                    padding: 3px 10px !important;
                    font-weight: 600 !important;
                    font-size: 12px !important;
                    letter-spacing: 0.3px !important;
                    transition: opacity 0.15s !important;
                    margin: 0 2px !important;
                }
                button[title^="AI:"]:hover {
                    opacity: 0.85 !important;
                }
            `;
            document.head.appendChild(s);
        })();
        """
        editor.web.eval(css)

    @classmethod
    def _add_toolbar_buttons(cls, buttons: List[str], editor: Editor) -> None:
        config = ConfigManager()
        general = config.get_general_settings()

        btn_all = editor.addButton(
            icon=None,
            cmd="ai_filler_fill_all",
            func=lambda ed: cls._on_fill_all(ed),
            tip=f"AI: Fill all blank fields ({general.fill_all_shortcut})",
            keys=general.fill_all_shortcut or None,
            label="\u2728 Fill All",
        )
        buttons.append(btn_all)

        btn_field = editor.addButton(
            icon=None,
            cmd="ai_filler_fill_field",
            func=lambda ed: cls._on_fill_field(ed),
            tip=f"AI: Fill current field ({general.fill_field_shortcut})",
            keys=general.fill_field_shortcut or None,
            label="\U0001f9e0 Fill",
        )
        buttons.append(btn_field)

    @classmethod
    def _add_context_menu(cls, webview: EditorWebView, menu: QMenu) -> None:
        editor = webview.editor
        if not editor.note:
            return

        menu.addSeparator()

        if editor.currentField is not None:
            field_name = editor.note.keys()[editor.currentField]
            action_fill = menu.addAction(f"AI: Fill '{field_name}'")
            qconnect(action_fill.triggered, lambda: cls._on_fill_field(editor))

        action_all = menu.addAction("AI: Fill all blank fields")
        qconnect(action_all.triggered, lambda: cls._on_fill_all(editor))

        menu.addSeparator()

        if editor.currentField is not None:
            field_name = editor.note.keys()[editor.currentField]
            action_cfg = menu.addAction(f"AI: Configure instructions for '{field_name}'...")
            qconnect(
                action_cfg.triggered,
                lambda: cls._on_configure_field(editor, field_name),
            )

    @classmethod
    def _on_fill_all(cls, editor: Editor) -> None:
        """Handle 'Fill all blank fields' action."""
        if not editor.note:
            return

        config = ConfigManager()
        general = config.get_general_settings()
        note = editor.note
        note_type_name = note.note_type()["name"]
        deck_name = _current_deck_name(editor)
        field_instructions = config.get_field_instructions(note_type_name, deck_name=deck_name)

        if general.show_fill_dialog:
            field_names = list(note.keys())
            field_values = {name: note[name] for name in field_names}
            blank_fields = [n for n in field_names if not note[n].strip()]

            dialog = FillDialog(
                field_names=field_names,
                field_values=field_values,
                field_instructions=field_instructions,
                pre_selected=blank_fields,
                parent=editor.widget,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            result = dialog.get_result()
            if not result:
                return
            target_fields, user_prompt = result
        else:
            target_fields = [
                n
                for n in note.keys()
                if not note[n].strip() and field_instructions.get(n, FieldInstruction()).auto_fill
            ]
            user_prompt = general.default_user_prompt

        if not target_fields:
            tooltip("No blank fields to fill.", parent=editor.widget)
            return

        cls._run_fill(editor, target_fields, user_prompt)

    @classmethod
    def _on_fill_field(cls, editor: Editor) -> None:
        """Handle 'Fill current field' action."""
        if not editor.note or editor.currentField is None:
            return

        config = ConfigManager()
        general = config.get_general_settings()
        note = editor.note
        field_name = note.keys()[editor.currentField]

        if general.show_fill_dialog:
            dialog = QuickPromptDialog(field_name, parent=editor.widget)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            user_prompt = dialog.get_user_prompt() or ""
        else:
            user_prompt = general.default_user_prompt

        cls._run_fill(editor, [field_name], user_prompt)

    @classmethod
    def _on_configure_field(cls, editor: Editor, field_name: str) -> None:
        """Open the quick instruction editor for a field."""
        if not editor.note:
            return
        note_type_name = editor.note.note_type()["name"]
        deck_name = _current_deck_name(editor)
        dialog = FieldInstructionDialog(
            note_type_name, field_name, deck_name=deck_name, parent=editor.widget
        )
        dialog.exec()

    @classmethod
    def _run_fill(
        cls,
        editor: Editor,
        target_fields: List[str],
        user_prompt: str,
    ) -> None:
        """Execute the AI fill operation with a blocking progress dialog."""
        config = ConfigManager()
        general = config.get_general_settings()
        deck_name = _current_deck_name(editor)

        prompts = []
        if general.default_user_prompt.strip():
            prompts.append(general.default_user_prompt.strip())
        if user_prompt.strip():
            prompts.append(user_prompt.strip())
        combined_prompt = "\n\n".join(prompts)

        progress = GeneratingDialog(parent=editor.widget)

        def on_success() -> None:
            progress.finish()
            tooltip("Fields filled successfully!", parent=editor.widget)

        def on_error(msg: str) -> None:
            progress.finish_with_error(msg)
            showWarning(
                f"AI Field Filler error:\n\n{msg}",
                title="AI Field Filler",
                parent=editor.widget,
            )

        cls._filler.fill_fields(
            editor=editor,
            target_fields=target_fields,
            user_prompt=combined_prompt,
            on_success=on_success,
            on_error=on_error,
            deck_name=deck_name,
        )

        progress.exec()
