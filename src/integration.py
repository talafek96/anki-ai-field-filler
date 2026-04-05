"""Anki UI integration: toolbar buttons, context menus, and startup."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional, Sequence

from aqt import gui_hooks, mw
from aqt.browser import Browser
from aqt.editor import Editor, EditorWebView
from aqt.qt import QDialog, QMenu, qconnect, QVBoxLayout, QCheckBox, QDialogButtonBox, Qt
from aqt.utils import showWarning, tooltip

from .core.config import Config
from .core.filler import BatchFiller, BatchNoteItem, Filler
from .ui.browser.fill_dialog import BatchFillDialog
from .ui.browser.progress import BatchProgressDialog, BatchSummaryDialog
from .ui.browser.review import BatchReviewDialog
from .ui.common.icons import get_themed_icon
from .ui.config.field_dialog import FieldInstructionDialog
from .ui.editor.progress_dialog import GeneratingDialog


def _current_deck_name(editor: Editor) -> Optional[str]:
    """Best-effort resolve the deck name for the note being edited."""
    note = editor.note
    if note is None:
        return None

    if note.id:
        cards = note.cards()
        if cards:
            did = mw.col.decks.get(cards[0].did)
            if did:
                return did["name"]

    parent = getattr(editor, "parentWindow", None)
    chooser = getattr(parent, "deckChooser", None)
    if chooser:
        did = chooser.selectedId()
        deck = mw.col.decks.get(did)
        if deck:
            return deck["name"]

    return None


class BrowserIntegration:
    """Adds batch AI fill to the browser's context menu."""

    @classmethod
    def init(cls) -> None:
        gui_hooks.browser_will_show_context_menu.append(cls._on_context_menu)

    @classmethod
    def _on_context_menu(cls, browser: Browser, menu: QMenu) -> None:
        selected = browser.selected_cards()
        if not selected:
            return
        menu.addSeparator()
        action = menu.addAction(
            f"\u2728 AI: Batch fill blank fields ({len(selected)} cards)"
        )
        qconnect(action.triggered, lambda: cls._on_batch_fill(browser, selected))

    @classmethod
    def _on_batch_fill(cls, browser: Browser, card_ids: Sequence[int]) -> None:
        note_map: Dict[int, BatchNoteItem] = {}
        for cid in card_ids:
            card = mw.col.get_card(cid)
            nid = card.nid
            if nid not in note_map:
                deck = mw.col.decks.get(card.did)
                deck_name = deck["name"] if deck else None
                note_map[nid] = BatchNoteItem(note_id=nid, deck_name=deck_name)

        items = list(note_map.values())
        if not items:
            return

        note_types: Dict[str, int] = {}
        for item in items:
            note = mw.col.get_note(item.note_id)
            nt_name = note.note_type()["name"]
            note_types[nt_name] = note_types.get(nt_name, 0) + 1

        if len(note_types) > 1:
            detail = "\n".join(
                f"  - {name}: {count} notes" for name, count in note_types.items()
            )
            showWarning(
                f"Batch fill requires all selected cards to be the "
                f"same note type.\n\n"
                f"Found {len(note_types)} note types:\n{detail}\n\n"
                f"Please select cards from a single note type.",
                title="AI Filler",
                parent=browser,
            )
            return

        note_type_name = next(iter(note_types))
        sample_note = mw.col.get_note(items[0].note_id)
        field_names = list(sample_note.keys())

        config = Config()
        field_instructions = config.get_global_field_instructions(note_type_name)

        dialog = BatchFillDialog(
            note_count=len(items),
            note_type_name=note_type_name,
            field_names=field_names,
            field_instructions=field_instructions,
            parent=browser,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = dialog.get_result()
        if not result:
            return
        target_fields, user_prompt, dry_run = result

        progress = BatchProgressDialog(parent=browser)
        progress.start(
            items=items,
            target_fields=target_fields,
            user_prompt=user_prompt,
            dry_run=dry_run,
        )
        progress.exec()

        batch_result = progress.get_result()
        if not batch_result or not batch_result.proposals:
            return

        review = BatchReviewDialog(
            proposals=batch_result.proposals,
            dry_run=dry_run,
            elapsed_seconds=batch_result.elapsed_seconds,
            parent=browser,
            batch_filler=BatchFiller(),
            user_prompt=user_prompt,
            note_items=items,
        )
        if review.exec() != QDialog.DialogCode.Accepted:
            return

        approved = review.get_approved()
        if not approved:
            tooltip("No changes applied.", parent=browser)
            return

        filler = BatchFiller()
        applied = filler.apply_proposals(approved)
        browser.model.reset()

        summary = BatchSummaryDialog(batch_result, parent=browser)
        summary.exec()

        tooltip(
            f"Applied {applied} of {batch_result.total} notes.",
            parent=browser,
        )


class FieldSelectorDialog(QDialog):
    """A dialog to select which fields the AI should fill/update."""

    def __init__(
        self, 
        fields: List[str], 
        selected: List[str], 
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("AI Filler: Select Fields")
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        self.checkboxes: Dict[str, QCheckBox] = {}
        
        for field in fields:
            cb = QCheckBox(field)
            cb.setChecked(field in selected)
            self.checkboxes[field] = cb
            layout.addWidget(cb)
            
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_fields(self) -> List[str]:
        return [name for name, cb in self.checkboxes.items() if cb.isChecked()]


class HistoryManager:
    """Manages note state history specifically for AI Filler."""

    def __init__(self, depth: int = 20):
        self._depth = depth
        self._history: Dict[int, List[Dict[str, str]]] = {}
        self._redo_stack: Dict[int, List[Dict[str, str]]] = {}

    def save_state(self, editor: Editor) -> None:
        """Save the current note state before an AI fill."""
        if not editor.note:
            return
        
        eid = id(editor)
        state = {name: editor.note[name] for name in editor.note.keys()}
        
        if eid not in self._history:
            self._history[eid] = []
        
        self._history[eid].append(state)
        # Clear redo stack on new action
        self._redo_stack[eid] = []
        
        # Limit depth
        if len(self._history[eid]) > self._depth:
            self._history[eid].pop(0)

    def undo(self, editor: Editor) -> bool:
        """Restore the previous note state."""
        eid = id(editor)
        if eid not in self._history or not self._history[eid]:
            return False
        
        if not editor.note:
            return False

        # Current state goes to redo stack
        current_state = {name: editor.note[name] for name in editor.note.keys()}
        if eid not in self._redo_stack:
            self._redo_stack[eid] = []
        self._redo_stack[eid].append(current_state)

        # Restore from history
        prev_state = self._history[eid].pop()
        for name, value in prev_state.items():
            editor.note[name] = value
        
        editor.loadNote()
        return True

    def redo(self, editor: Editor) -> bool:
        """Restore the state before an undo."""
        eid = id(editor)
        if eid not in self._redo_stack or not self._redo_stack[eid]:
            return False
            
        if not editor.note:
            return False

        # Current state goes back to history
        current_state = {name: editor.note[name] for name in editor.note.keys()}
        self._history[eid].append(current_state)

        # Restore from redo stack
        next_state = self._redo_stack[eid].pop()
        for name, value in next_state.items():
            editor.note[name] = value
            
        editor.loadNote()
        return True


class EditorIntegration:
    """Manages editor toolbar buttons and context menu items."""

    _filler: Filler | None = None
    _history: HistoryManager = HistoryManager()
    _selected_fields: Dict[int, List[str]] = {}

    @classmethod
    def init(cls) -> None:
        """Register all editor hooks."""
        cls._filler = Filler()
        gui_hooks.editor_will_show_context_menu.append(cls._add_context_menu)
        gui_hooks.editor_did_init.append(cls._on_editor_did_init)
        gui_hooks.editor_did_load_note.append(cls._on_editor_did_load_note)
        gui_hooks.webview_did_receive_js_message.append(cls._on_webview_did_receive_js_message)


    @classmethod
    def _add_context_menu(cls, webview: EditorWebView, menu: QMenu) -> None:
        editor = webview.editor
        if not editor.note:
            return

        menu.addSeparator()

        action_all = menu.addAction("\u2728 AI: Toggle prompt field...")
        qconnect(action_all.triggered, lambda: webview.eval("aiFiller.togglePrompt()"))

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
        on_success: Optional[Callable] = None,
    ) -> None:
        """Execute the AI fill operation with a blocking progress dialog."""
        deck_name = _current_deck_name(editor)

        combined_prompt = user_prompt.strip()

        progress = GeneratingDialog(parent=editor.widget)

        def _on_success() -> None:
            progress.finish()
            tooltip("Fields filled successfully!", parent=editor.widget)
            if on_success:
                mw.taskman.run_on_main(on_success)

        def on_error(msg: str) -> None:
            progress.finish_with_error(msg)
            showWarning(
                f"AI Filler error:\n\n{msg}",
                title="AI Filler",
                parent=editor.widget,
            )

        cls._filler.fill_fields(
            editor=editor,
            target_fields=target_fields,
            user_prompt=combined_prompt,
            on_success=_on_success,
            on_error=on_error,
            deck_name=deck_name,
        )

        progress.exec()

    @classmethod
    def _on_editor_did_init(cls, editor: Editor) -> None:
        """Inject JS and CSS into the editor."""
        webview = editor.web
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        editor_dir = os.path.join(addon_dir, "src", "ui", "editor")
        
        css_path = os.path.join(editor_dir, "editor.css")
        js_path = os.path.join(editor_dir, "editor.js")
        
        try:
            # Read assets
            with open(css_path, "r", encoding="utf-8") as f:
                css = f.read().replace("`", "\\`").replace("\n", " ")
                webview.eval(f"const s = document.createElement('style'); s.innerHTML = `{css}`; document.head.appendChild(s);")
            
            # Read SVG sparkle icon
            sparkle_ico_path = os.path.join(addon_dir, "assets", "icons", "app", "sparkles.svg")
            sparkle_svg = ""
            if os.path.exists(sparkle_ico_path):
                with open(sparkle_ico_path, "r", encoding="utf-8") as f:
                    sparkle_svg = f.read().replace("`", "\\`").replace("\n", " ")

            with open(js_path, "r", encoding="utf-8") as f:
                js = f.read()
                webview.eval(f"window.aiFillerSparkleSVG = `{sparkle_svg}`;")
                webview.eval(js)
                # Force init check
                webview.eval("if (window.aiFiller) aiFiller.init();")
        except Exception as e:
            print(f"AI Filler: Failed to inject editor assets: {e}")

    @classmethod
    def _on_webview_did_receive_js_message(
        cls, handled: tuple[bool, Any], message: str, context: Any
    ) -> tuple[bool, Any]:
        """Handle messages from the integrated prompt field."""
        if not message.startswith("ai_filler:"):
            return handled

        # Check if the context is an Editor
        # In some Anki versions, we might need to check context type carefully
        editor = None
        if isinstance(context, Editor):
            editor = context
        elif hasattr(context, "editor") and isinstance(context.editor, Editor):
            editor = context.editor

        if not editor:
            return handled

        if message.startswith("ai_filler:generate:"):
            prompt = message[len("ai_filler:generate:") :]
            cls._run_integrated_fill(editor, prompt)
            return (True, None)
        
        if message == "ai_filler:undo":
            cls._history.undo(editor)
            return (True, None)
            
        if message == "ai_filler:redo":
            cls._history.redo(editor)
            return (True, None)

        if message == "ai_filler:select_fields":
            cls._on_select_fields(editor)
            return (True, None)

        return handled

    @classmethod
    def _on_select_fields(cls, editor: Editor) -> None:
        """Open the field selector dialog."""
        if not editor.note:
            return
            
        eid = id(editor)
        all_fields = list(editor.note.keys())
        
        # Default to all fields if none selected yet
        if eid not in cls._selected_fields:
            cls._selected_fields[eid] = all_fields
            
        dialog = FieldSelectorDialog(
            all_fields, 
            cls._selected_fields[eid], 
            parent=editor.widget
        )
        
        if dialog.exec():
            cls._selected_fields[eid] = dialog.get_selected_fields()

    @classmethod
    def _run_integrated_fill(cls, editor: Editor, user_prompt: str) -> None:
        """Handle fill request from the integrated prompt field."""
        if not editor.note:
            return

        eid = id(editor)
        note = editor.note
        
        # Use manually selected fields if available, otherwise filter by config
        if eid in cls._selected_fields:
            target_fields = cls._selected_fields[eid]
        else:
            config = Config()
            note_type_name = note.note_type()["name"]
            deck_name = _current_deck_name(editor)
            field_instructions = config.get_field_instructions(
                note_type_name, deck_name=deck_name
            )

            target_fields = []
            for name in note.keys():
                instr = field_instructions.get(name)
                if instr is None or instr.auto_fill:
                    target_fields.append(name)

        if not target_fields:
            tooltip("No fields selected to fill.", parent=editor.widget)
            return

        # Save state for undo
        cls._history.save_state(editor)

        cls._run_fill(
            editor,
            target_fields,
            user_prompt,
        )

    @classmethod
    def _on_editor_did_load_note(cls, editor: Editor) -> None:
        """Ensure the prompt field is present when a note is loaded."""
        # The Svelte editor might fully recreate the fields DOM.
        # Calling init again picks up the new container.
        editor.web.eval("if (window.aiFiller) aiFiller.init();")
