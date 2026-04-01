"""Anki UI integration: toolbar buttons, context menus, and startup."""

from __future__ import annotations

import sys
from typing import Dict, List, Optional, Sequence

from aqt import gui_hooks, mw
from aqt.browser import Browser
from aqt.editor import Editor, EditorWebView
from aqt.qt import QAction, QDialog, QMenu, qconnect
from aqt.utils import showWarning, tooltip

from ..core.config import Config, FieldInstruction
from ..core.filler import BatchFiller, BatchNoteItem, Filler
from ..core.factory import test_provider_connection, fetch_available_models
from .browser_batch_fill_dialog import BatchFillDialog
from .browser_batch_progress import BatchProgressDialog, BatchSummaryDialog
from .browser_batch_review import BatchReviewDialog
from .config_field_dialog import FieldInstructionDialog
from .editor_fill_dialog import FillDialog
from .editor_progress_dialog import GeneratingDialog
from .editor_prompt_dialog import QuickPromptDialog
from .config_dialog import SettingsDialog
from .chat_panel import ChatPanel


def start_addon() -> None:
    """Initialize the addon: register hooks, menus, and config actions."""
    from aqt.qt import QAction, QMenu, qconnect

    EditorIntegration.init()
    BrowserIntegration.init()

    # Tools menu item
    settings_action = QAction("Anki AI Filler", mw)
    qconnect(settings_action.triggered, lambda: SettingsDialog(mw).exec())
    mw.form.menuTools.addAction(settings_action)

    # Addon manager integration
    addon_name = mw.addonManager.addonFromModule(__name__)
    config = Config()

    mw.addonManager.setConfigAction(addon_name, lambda: SettingsDialog(mw).exec())
    mw.addonManager.setConfigUpdatedAction(addon_name, config.update_from_addon_manager)


def _current_deck_name(editor: Editor) -> Optional[str]:
    """Best-effort resolve the deck name for the note being edited."""
    note = editor.note
    if note is None:
        return None

    if note.id:
        cards = note.cards()
        if cards:
            deck = mw.col.decks.get(cards[0].did)
            if deck:
                return deck["name"]

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
        action = menu.addAction(f"\u2728 AI: Batch fill blank fields ({len(selected)} cards)")
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
            detail = "\n".join(f"  - {name}: {count} notes" for name, count in note_types.items())
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


class EditorIntegration:
    """Manages editor toolbar buttons and context menu items."""

    _filler: Filler | None = None

    @classmethod
    def init(cls) -> None:
        """Register all editor hooks."""
        cls._filler = Filler()
        gui_hooks.editor_did_init_buttons.append(cls._add_toolbar_buttons)
        gui_hooks.editor_will_show_context_menu.append(cls._add_context_menu)
        gui_hooks.editor_did_load_note.append(cls._on_note_loaded)

    @classmethod
    def _add_toolbar_buttons(cls, buttons: List[str], editor: Editor) -> None:
        config = Config()
        general = config.get_general_settings()

        import os
        # __file__ is src/ui/hooks.py, so we go up 3 levels to reach the addon root
        addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        icons_dir = os.path.join(addon_dir, "assets", "icons", "app")

        sparkles_icon = os.path.join(icons_dir, "sparkles.svg")
        zap_icon = os.path.join(icons_dir, "zap.svg")
        chat_icon = os.path.join(icons_dir, "chat.svg")

        btn_all = editor.addButton(
            icon=sparkles_icon,
            cmd="ai_filler_fill_all",
            func=lambda ed: cls._on_fill_all(ed),
            tip=f"AI: Fill all blank fields ({general.fill_all_shortcut})",
            keys=general.fill_all_shortcut or None,
            label="",
        )
        buttons.append(btn_all)

        btn_field = editor.addButton(
            icon=zap_icon,
            cmd="ai_filler_fill_field",
            func=lambda ed: cls._on_fill_field(ed),
            tip=f"AI: Fill current field ({general.fill_field_shortcut})",
            keys=general.fill_field_shortcut or None,
            label="",
        )
        buttons.append(btn_field)

        btn_chat = editor.addButton(
            icon=chat_icon,
            cmd="ai_filler_chat",
            func=lambda ed: cls._on_chat(ed),
            tip="AI: Custom fill (select fields & prompt)",
            keys=None,
            label="",
        )
        buttons.append(btn_chat)

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
            action_cfg = menu.addAction(f"AI: Configure '{field_name}' instructions...")
            qconnect(
                action_cfg.triggered,
                lambda: cls._on_configure_field(editor, field_name),
            )

    @classmethod
    def _on_fill_all(cls, editor: Editor) -> None:
        """Handle 'Fill all blank fields' action."""
        if not editor.note:
            return

        config = Config()
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
    def _on_chat(cls, editor: Editor) -> None:
        """Handle 'Custom fill' action (now shows side panel)."""
        if not editor.note:
            return

        panel: ChatPanel = getattr(editor, "ai_chat_panel", None)
        if not panel:
            panel = ChatPanel(editor)
            setattr(editor, "ai_chat_panel", panel)
            panel.on_fill_requested = lambda fields, prompt: cls._run_fill(
                editor, fields, prompt
            )
            cls._inject_side_panel(editor, panel)

        panel.toggle_visibility()

    @classmethod
    def _on_note_loaded(cls, editor: Editor) -> None:
        """Refresh side panel when a new note is loaded."""
        panel: ChatPanel = getattr(editor, "ai_chat_panel", None)
        if panel and panel.isVisible():
            panel.refresh_fields()

    @classmethod
    def _inject_side_panel(cls, editor: Editor, panel: ChatPanel) -> None:
        """Safely inject the panel to the right of the editor fields."""
        from aqt.qt import QHBoxLayout, QWidget

        # Get the widget that holds the editor fields
        ed_widget = editor.widget
        parent_widget = ed_widget.parent()
        if not parent_widget:
            return

        p_layout = parent_widget.layout()
        if not p_layout:
            return

        # Create a container to hold both editor and panel
        container = QWidget()
        container.setObjectName("aiChatContainer")
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        # Replace editor with container in parent layout
        idx = p_layout.indexOf(ed_widget)
        if idx != -1:
            p_layout.takeAt(idx)
            h_layout.addWidget(ed_widget)
            h_layout.addWidget(panel)
            p_layout.insertWidget(idx, container)

    @classmethod
    def _on_fill_field(cls, editor: Editor) -> None:
        """Handle 'Fill current field' action."""
        if not editor.note or editor.currentField is None:
            return

        config = Config()
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
        config = Config()
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
                f"AI Filler error:\n\n{msg}",
                title="AI Filler",
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
