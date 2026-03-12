"""Browser integration — batch fill from card selection."""

from __future__ import annotations

from typing import Dict, Sequence

from aqt import gui_hooks, mw
from aqt.browser import Browser
from aqt.qt import QDialog, QMenu, qconnect
from aqt.utils import showWarning

from .config_manager import ConfigManager
from .field_filler import BatchNoteItem
from .ui.batch_fill_dialog import BatchFillDialog
from .ui.batch_progress_dialog import BatchProgressDialog, BatchSummaryDialog


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
        action = menu.addAction(f"AI: Batch fill blank fields ({len(selected)} cards)")
        qconnect(action.triggered, lambda: cls._on_batch_fill(browser, selected))

    @classmethod
    def _on_batch_fill(cls, browser: Browser, card_ids: Sequence[int]) -> None:
        # Deduplicate notes and determine deck per note
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

        # Validate: all notes must be the same note type
        note_types: Dict[str, int] = {}
        for item in items:
            note = mw.col.get_note(item.note_id)
            nt_name = note.note_type()["name"]
            note_types[nt_name] = note_types.get(nt_name, 0) + 1

        if len(note_types) > 1:
            detail = "\n".join(f"  - {name}: {count} notes" for name, count in note_types.items())
            showWarning(
                f"Batch fill requires all selected cards to be the same note type.\n\n"
                f"Found {len(note_types)} note types:\n{detail}\n\n"
                f"Please select cards from a single note type.",
                title="AI Field Filler",
                parent=browser,
            )
            return

        note_type_name = next(iter(note_types))
        sample_note = mw.col.get_note(items[0].note_id)
        field_names = list(sample_note.keys())

        config = ConfigManager()
        field_instructions = config.get_global_field_instructions(note_type_name)

        # Show batch fill dialog
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

        # Show progress dialog and run batch
        progress = BatchProgressDialog(parent=browser)
        progress.start(
            items=items,
            target_fields=target_fields,
            user_prompt=user_prompt,
            dry_run=dry_run,
        )
        progress.exec()

        batch_result = progress.get_result()
        if not batch_result:
            return

        # Refresh the browser to show updated content
        if not dry_run and batch_result.succeeded > 0:
            browser.model.reset()

        # Show summary
        summary = BatchSummaryDialog(batch_result, parent=browser)
        summary.exec()
