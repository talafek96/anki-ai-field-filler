"""Review dialog — shows before/after diffs and allows editing before applying."""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

from anki.sound import SoundOrVideoTag
from aqt import mw
from aqt.qt import *
from aqt.sound import av_player

from ..field_filler import BatchProposedChange
from .styles import GLOBAL_STYLE, HEADER_STYLE, MUTED_LABEL_STYLE

_DIFF_OLD_STYLE = (
    "background: #FEF2F2; border: 1px solid #FECACA; border-radius: 4px; "
    "padding: 6px 8px; color: #991B1B; font-size: 12px;"
)
_DIFF_NEW_STYLE = (
    "border: 1px solid #BBF7D0; border-radius: 4px; "
    "padding: 4px 6px; background: #F0FDF4; color: #166534; font-size: 12px;"
)
_DIFF_LABEL_OLD = "color: #DC2626; font-weight: 600; font-size: 11px;"
_DIFF_LABEL_NEW = "color: #16A34A; font-weight: 600; font-size: 11px;"

_RENDERED_OLD_STYLE = (
    "background: #FEF2F2; border: 1px solid #FECACA; border-radius: 4px; "
    "color: #991B1B; font-size: 12px;"
)

_RENDERED_NEW_STYLE = (
    "background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; "
    "color: #166534; font-size: 12px;"
)

_FIELD_ERROR_STYLE = "color: #B45309; font-size: 12px; padding: 2px 0;"

_EMPTY_HTML = '<span style="color: #9CA3AF; font-style: italic; font-size: 12px;">(empty)</span>'

_INITIAL_CONTENT_HEIGHT = 80

_BODY_RE = re.compile(r"<body[^>]*>(.*)</body>", re.DOTALL)
_SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")

# Display-only CSS applied via setDefaultStyleSheet so images scale to fit
# the diff panel.  Not embedded in toHtml() output.
_IMG_DISPLAY_CSS = "img { max-width: 100%; height: auto; }"


def _fmt_seconds(seconds: float) -> str:
    """Format seconds as 'm:ss'."""
    s = int(seconds)
    if s < 3600:
        return f"{s // 60}:{s % 60:02d}"
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _media_base_url() -> Optional[QUrl]:
    """Return a file:// QUrl pointing to Anki's media folder, or None."""
    try:
        media_dir = mw.col.media.dir()
        return QUrl.fromLocalFile(media_dir + os.sep)
    except Exception:
        return None


def _extract_body_html(qt_html: str) -> str:
    """Extract body content from QTextEdit.toHtml() output.

    Qt wraps edited content in a full HTML document with doctype, head,
    and verbose inline styles.  We only want the inner body content so
    the stored value stays close to what the AI originally produced.
    """
    m = _BODY_RE.search(qt_html)
    return m.group(1).strip() if m else qt_html


class _PairedResizeHandle(QWidget):
    """Draggable bar that resizes two widgets in sync.

    Draws three short horizontal grip lines as a visual indicator.
    """

    def __init__(
        self,
        target_a: QWidget,
        target_b: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._targets = (target_a, target_b)
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_h = 0
        self.setFixedHeight(14)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Drag to resize")

    def paintEvent(self, event: object) -> None:
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
        self._drag_start_h = self._targets[0].height()
        e.accept()

    def mouseMoveEvent(self, event: object) -> None:
        e = event  # type: ignore[assignment]
        if self._dragging:
            delta = int(e.globalPosition().y()) - self._drag_start_y
            new_h = max(48, self._drag_start_h + delta)
            for t in self._targets:
                t.setFixedHeight(new_h)
            e.accept()

    def mouseReleaseEvent(self, event: object) -> None:
        if self._dragging:
            self._dragging = False
            h = self._targets[0].height()
            for t in self._targets:
                t.setMinimumHeight(h)
                t.setMaximumHeight(16777215)
            event.accept()  # type: ignore[union-attr]


class BatchReviewDialog(QDialog):
    """Shows proposed changes per note with before/after diffs and inline editing."""

    def __init__(
        self,
        proposals: List[BatchProposedChange],
        dry_run: bool = False,
        elapsed_seconds: float = 0.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._proposals = proposals
        self._dry_run = dry_run
        self._elapsed_seconds = elapsed_seconds
        self._approved: List[BatchProposedChange] = []
        self._checks: List[QCheckBox] = []
        # Map (proposal index, field_name) -> widgets
        self._edits: Dict[tuple, QPlainTextEdit] = {}  # raw HTML editors
        self._rendered_edits: Dict[tuple, QTextEdit] = {}  # WYSIWYG editors
        # Stacked widgets for rendered/raw toggle
        self._old_stacks: List[QStackedWidget] = []
        self._new_stacks: List[QStackedWidget] = []
        self._raw_mode = False
        self._base_url: Optional[QUrl] = _media_base_url()
        self._setup_ui()

    def _setup_ui(self) -> None:
        title = "Dry Run Preview" if self._dry_run else "Review Changes"
        self.setWindowTitle(f"AI Field Filler \u2014 {title}")
        self.setMinimumSize(750, 520)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setStyleSheet(GLOBAL_STYLE)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        successful = [p for p in self._proposals if p.success]
        failed = [p for p in self._proposals if not p.success]
        partial = [p for p in successful if p.field_errors]

        icon = "\U0001f50d" if self._dry_run else "\u2705"
        parts = [f"{icon}  {len(successful)} notes to {'process' if self._dry_run else 'update'}"]
        if partial:
            parts.append(f"{len(partial)} partially failed")
        if failed:
            parts.append(f"{len(failed)} failed")
        header = QLabel(", ".join(parts))
        header.setStyleSheet(HEADER_STYLE)
        layout.addWidget(header)

        # Generation stats
        if self._elapsed_seconds > 0 and successful:
            avg = self._elapsed_seconds / len(successful)
            stats_text = (
                f"Generated in {_fmt_seconds(self._elapsed_seconds)}  \u2022  {avg:.1f}s per note"
            )
            stats_label = QLabel(stats_text)
            stats_label.setStyleSheet(MUTED_LABEL_STYLE)
            layout.addWidget(stats_label)

        if not self._dry_run:
            hint_row = QHBoxLayout()
            hint = QLabel("Toggle <b>Show raw HTML</b> to view and edit the raw HTML.")
            hint.setStyleSheet(MUTED_LABEL_STYLE)
            hint_row.addWidget(hint)
            hint_row.addStretch()

            self._raw_toggle = QCheckBox("Show raw HTML")
            self._raw_toggle.setChecked(False)
            qconnect(self._raw_toggle.toggled, self._on_toggle_raw)
            hint_row.addWidget(self._raw_toggle)
            layout.addLayout(hint_row)

        # Scrollable list of proposals
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        list_layout = QVBoxLayout()
        list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        list_layout.setSpacing(10)

        for idx, prop in enumerate(self._proposals):
            row = self._make_proposal_widget(idx, prop)
            list_layout.addWidget(row)

        container.setLayout(list_layout)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Select all / deselect all
        if not self._dry_run:
            toggle_row = QHBoxLayout()
            select_all = QPushButton("Select All")
            qconnect(select_all.clicked, self._select_all)
            toggle_row.addWidget(select_all)
            deselect_all = QPushButton("Deselect All")
            qconnect(deselect_all.clicked, self._deselect_all)
            toggle_row.addWidget(deselect_all)
            toggle_row.addStretch()
            layout.addLayout(toggle_row)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel" if not self._dry_run else "Close")
        qconnect(cancel_btn.clicked, self.reject)
        btn_layout.addWidget(cancel_btn)

        if not self._dry_run:
            apply_btn = QPushButton("  \u2705  Apply Selected  ")
            apply_btn.setDefault(True)
            qconnect(apply_btn.clicked, self._on_apply)
            btn_layout.addWidget(apply_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def _make_proposal_widget(self, idx: int, prop: BatchProposedChange) -> QGroupBox:
        preview = prop.note_preview or f"Note #{prop.note_id}"
        group = QGroupBox()

        group_layout = QVBoxLayout()
        group_layout.setSpacing(6)
        group_layout.setContentsMargins(10, 10, 10, 10)

        # Header row with checkbox (for real runs) or just label (dry run)
        header_row = QHBoxLayout()
        if not self._dry_run and prop.success:
            cb = QCheckBox(preview)
            cb.setChecked(True)
            cb.setStyleSheet("font-weight: 600;")
            self._checks.append(cb)
            header_row.addWidget(cb)
        else:
            label = QLabel(preview)
            label.setStyleSheet("font-weight: 600;")
            header_row.addWidget(label)
            self._checks.append(None)  # type: ignore[arg-type]

        header_row.addStretch()
        group_layout.addLayout(header_row)

        if not prop.success:
            self._add_error_block(
                group_layout, f"\u274c Error: {prop.error}", "color: #DC2626; font-size: 12px;"
            )
        elif self._dry_run:
            # Show which fields would be targeted
            fields_text = ", ".join(prop.blank_fields) if prop.blank_fields else "none"
            info = QLabel(f"Fields to fill: <b>{fields_text}</b>")
            info.setStyleSheet(MUTED_LABEL_STYLE)
            group_layout.addWidget(info)
        else:
            # Show before/after diff for each changed field
            for field_name, new_value in prop.changes.items():
                old_value = prop.original_values.get(field_name, "")
                self._add_field_diff(group_layout, idx, field_name, old_value, new_value)
            # Show per-field errors as warnings
            for field_name, err_msg in prop.field_errors.items():
                self._add_error_block(
                    group_layout,
                    f"\u26a0\ufe0f <b>{field_name}</b>: {err_msg}",
                    _FIELD_ERROR_STYLE,
                )

        group.setLayout(group_layout)
        return group

    _MAX_ERROR_PREVIEW = 200

    def _add_error_block(
        self,
        parent_layout: QVBoxLayout,
        text: str,
        style: str,
    ) -> None:
        """Add an error label that can expand if the message is long."""
        if len(text) <= self._MAX_ERROR_PREVIEW:
            label = QLabel(text)
            label.setStyleSheet(style)
            label.setWordWrap(True)
            parent_layout.addWidget(label)
            return

        preview = QLabel(text[: self._MAX_ERROR_PREVIEW] + "\u2026")
        preview.setStyleSheet(style)
        preview.setWordWrap(True)
        parent_layout.addWidget(preview)

        full_edit = QPlainTextEdit()
        plain = re.sub(r"<[^>]+>", "", text)
        full_edit.setPlainText(plain)
        full_edit.setReadOnly(True)
        full_edit.setMaximumHeight(120)
        full_edit.setStyleSheet(style)
        full_edit.setVisible(False)
        parent_layout.addWidget(full_edit)

        toggle = QPushButton("Show full error")

        def _toggle() -> None:
            if full_edit.isVisible():
                full_edit.setVisible(False)
                preview.setVisible(True)
                toggle.setText("Show full error")
            else:
                full_edit.setVisible(True)
                preview.setVisible(False)
                toggle.setText("Hide full error")

        qconnect(toggle.clicked, lambda _c=False: _toggle())
        parent_layout.addWidget(toggle)

    def _add_field_diff(
        self,
        parent_layout: QVBoxLayout,
        prop_idx: int,
        field_name: str,
        old_value: str,
        new_value: str,
    ) -> None:
        """Add a before/after diff block for a single field."""
        # Field label row — play buttons sit next to the name when audio tags
        # are present so they're easy to find and don't shift the layout.
        label_row = QHBoxLayout()
        field_label = QLabel(f"<b>{field_name}</b>")
        label_row.addWidget(field_label)

        all_sounds = list(
            dict.fromkeys(_SOUND_RE.findall(old_value) + _SOUND_RE.findall(new_value))
        )
        for fname in all_sounds:
            btn = QPushButton(f"\u25b6 {fname}")
            qconnect(btn.clicked, lambda _c=False, f=fname: self._play_sound(f))
            label_row.addWidget(btn)

        label_row.addStretch()
        parent_layout.addLayout(label_row)

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 1)

        # Row 0: column headers
        old_header = QLabel("\u2190 Before")
        old_header.setStyleSheet(_DIFF_LABEL_OLD)
        old_header.setFixedHeight(18)
        grid.addWidget(old_header, 0, 0)

        new_header = QLabel("After \u2192")
        new_header.setStyleSheet(_DIFF_LABEL_NEW)
        new_header.setFixedHeight(18)
        grid.addWidget(new_header, 0, 2)

        # Row 1: content — stacked widgets for rendered / raw toggle
        # --- Old side ---
        old_stack = QStackedWidget()
        old_stack.setFixedHeight(_INITIAL_CONTENT_HEIGHT)

        # Page 0: rendered HTML
        old_rendered = QTextBrowser()
        old_rendered.setOpenExternalLinks(False)
        old_rendered.setStyleSheet(_RENDERED_OLD_STYLE)
        old_rendered.document().setDefaultStyleSheet(_IMG_DISPLAY_CSS)
        if self._base_url:
            old_rendered.document().setBaseUrl(self._base_url)
        if old_value.strip():
            old_rendered.setHtml(old_value)
        else:
            old_rendered.setHtml(_EMPTY_HTML)
        old_stack.addWidget(old_rendered)

        # Page 1: raw text (read-only)
        old_raw = QPlainTextEdit()
        old_raw.setReadOnly(True)
        old_raw.setPlainText(old_value if old_value.strip() else "(empty)")
        old_raw.setStyleSheet(_DIFF_OLD_STYLE)
        old_stack.addWidget(old_raw)

        old_stack.setCurrentIndex(0)
        grid.addWidget(old_stack, 1, 0)

        # --- Arrow ---
        arrow = QLabel("\u2192")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setStyleSheet("font-size: 18px; color: #9CA3AF;")
        arrow.setFixedWidth(28)
        grid.addWidget(arrow, 1, 1, Qt.AlignmentFlag.AlignCenter)

        # --- New side (stacked: rendered+editable / raw editable) ---
        new_stack = QStackedWidget()
        new_stack.setFixedHeight(_INITIAL_CONTENT_HEIGHT)

        # Page 0: rendered HTML (editable WYSIWYG)
        new_rendered = QTextEdit()
        new_rendered.setStyleSheet(_RENDERED_NEW_STYLE)
        new_rendered.document().setDefaultStyleSheet(_IMG_DISPLAY_CSS)
        if self._base_url:
            new_rendered.document().setBaseUrl(self._base_url)
        new_rendered.setHtml(new_value if new_value.strip() else _EMPTY_HTML)
        new_rendered.document().setModified(False)
        new_stack.addWidget(new_rendered)

        # Page 1: raw text (editable)
        edit = QPlainTextEdit()
        edit.setPlainText(new_value)
        edit.setStyleSheet(_DIFF_NEW_STYLE)
        new_stack.addWidget(edit)

        new_stack.setCurrentIndex(0)
        grid.addWidget(new_stack, 1, 2)

        self._rendered_edits[(prop_idx, field_name)] = new_rendered
        self._edits[(prop_idx, field_name)] = edit
        self._old_stacks.append(old_stack)
        self._new_stacks.append(new_stack)

        parent_layout.addLayout(grid)

        # Resize handle — drags both old and new panels together
        handle = _PairedResizeHandle(old_stack, new_stack)
        parent_layout.addWidget(handle)

    # --- Toggle rendered / raw ---

    def _on_toggle_raw(self, raw: bool) -> None:
        self._raw_mode = raw
        page = 1 if raw else 0
        for old_stack in self._old_stacks:
            old_stack.setCurrentIndex(page)
        if raw:
            # Switching to raw: sync WYSIWYG edits into the raw editors
            for key, rendered in self._rendered_edits.items():
                if rendered.document().isModified():
                    self._edits[key].setPlainText(_extract_body_html(rendered.toHtml()))
                    rendered.document().setModified(False)
        else:
            # Switching to rendered: refresh WYSIWYG from raw editors
            for key, edit in self._edits.items():
                rendered = self._rendered_edits[key]
                text = edit.toPlainText()
                rendered.setHtml(text if text.strip() else _EMPTY_HTML)
                rendered.document().setModified(False)
        for new_stack in self._new_stacks:
            new_stack.setCurrentIndex(page)

    # --- Select / deselect ---

    def _select_all(self) -> None:
        for cb in self._checks:
            if cb is not None:
                cb.setChecked(True)

    def _deselect_all(self) -> None:
        for cb in self._checks:
            if cb is not None:
                cb.setChecked(False)

    # --- Audio playback ---

    def _play_sound(self, filename: str) -> None:
        """Play an audio file via Anki's av_player."""
        av_player.play_tags([SoundOrVideoTag(filename=filename)])

    # --- Apply ---

    def _on_apply(self) -> None:
        # If in rendered mode, sync any WYSIWYG edits to the raw editors
        if not self._raw_mode:
            for key, rendered in self._rendered_edits.items():
                if rendered.document().isModified():
                    self._edits[key].setPlainText(_extract_body_html(rendered.toHtml()))

        # Write edited values back into proposals before returning
        for (prop_idx, field_name), edit in self._edits.items():
            self._proposals[prop_idx].changes[field_name] = edit.toPlainText()

        self._approved = []
        for i, prop in enumerate(self._proposals):
            cb = self._checks[i] if i < len(self._checks) else None
            if cb is not None and cb.isChecked() and prop.success:
                self._approved.append(prop)
        self.accept()

    def get_approved(self) -> List[BatchProposedChange]:
        """Return the list of proposals the user approved."""
        return self._approved
