"""Review dialog — shows generated content previews and allows editing before applying."""

from __future__ import annotations

import os
import re
import threading
from html.parser import HTMLParser
from typing import Dict, List, Optional, Set

from anki.sound import SoundOrVideoTag
from aqt import mw
from aqt.qt import *
from aqt.sound import av_player

from ...core.filler import BatchProposedChange
from ..common.icons import get_themed_icon
from ..common.theme import (
    CLICKABLE_ARROW_STYLE,
    FIELD_ERROR_STYLE,
    FILTER_CHIP_STYLE,
    GLOBAL_STYLE,
    HEADER_STYLE,
    MUTED_LABEL_STYLE,
    PREVIEW_RENDERED_STYLE,
    PREVIEW_STYLE,
    REGEN_TOGGLE_STYLE,
    RESIZE_HANDLE_COLOR,
)

_PREVIEW_STYLE = PREVIEW_STYLE
_PREVIEW_RENDERED_STYLE = PREVIEW_RENDERED_STYLE
_FIELD_ERROR_STYLE = FIELD_ERROR_STYLE

_INITIAL_CONTENT_HEIGHT = 200

_SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")

# Collapse arrow — use a QLabel styled as a button so it doesn't steal focus
# or exhibit QPushButton repaint quirks.
_ARROW_EXPANDED = "\u25bc"
_ARROW_COLLAPSED = "\u25b6"


# ---------------------------------------------------------------------------
# Robust HTML body extraction
# ---------------------------------------------------------------------------


class _BodyExtractor(HTMLParser):
    """HTMLParser subclass that extracts content between <body> and </body> tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._in_body = False
        self._found_body = False
        self._depth = 0
        self._parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "body":
            if not self._in_body:
                self._in_body = True
                self._found_body = True
                self._depth = 1
                return
            self._depth += 1
        elif self._in_body:
            self._depth += 1
        if self._in_body:
            attr_str = ""
            for name, val in attrs:
                if val is None:
                    attr_str += f" {name}"
                else:
                    attr_str += f' {name}="{val}"'
            self._parts.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag: str) -> None:
        if tag == "body" and self._in_body:
            self._depth -= 1
            if self._depth <= 0:
                self._in_body = False
                return
        if self._in_body:
            self._parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._in_body:
            self._parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._in_body:
            self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._in_body:
            self._parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        if self._in_body:
            self._parts.append(f"<!--{data}-->")

    def get_body_content(self) -> str | None:
        if self._found_body:
            return "".join(self._parts).strip()
        return None


def _extract_body_html(qt_html: str) -> str:
    """Extract body content from QTextEdit.toHtml() output."""
    if not qt_html:
        return qt_html
    parser = _BodyExtractor()
    parser.feed(qt_html)
    result = parser.get_body_content()
    return result if result is not None else qt_html


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


# ---------------------------------------------------------------------------
# Proposal classification helpers
# ---------------------------------------------------------------------------


def _classify_proposal(prop: BatchProposedChange) -> Set[str]:
    """Classify a proposal's content types based on its changes."""
    types: Set[str] = set()
    for value in prop.changes.values():
        types |= _classify_value(value)
    return types


def _classify_value(value: str) -> Set[str]:
    """Classify a single field value into content types."""
    types: Set[str] = set()
    if not value:
        return types
    has_img = "<img" in value
    has_sound = "[sound:" in value
    if has_img:
        types.add("image")
    if has_sound:
        types.add("audio")
    stripped = _SOUND_RE.sub("", value)
    stripped = re.sub(r"<img[^>]*>", "", stripped)
    stripped = re.sub(r"<[^>]*>", "", stripped).strip()
    if stripped:
        types.add("text")
    return types


# ---------------------------------------------------------------------------
# Single-target resize handle
# ---------------------------------------------------------------------------


class _ResizeHandle(QWidget):
    """Draggable bar that resizes a single widget vertically."""

    def __init__(self, target: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target = target
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_h = 0
        self.setFixedHeight(12)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Drag to resize")

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(RESIZE_HANDLE_COLOR))
        pen.setWidth(1)
        p.setPen(pen)
        cx = self.width() // 2
        half_w = 14
        for dy in (-2, 1):
            y = self.height() // 2 + dy
            p.drawLine(cx - half_w, y, cx + half_w, y)
        p.end()

    def mousePressEvent(self, event: object) -> None:
        e = event  # type: ignore[assignment]
        self._dragging = True
        self._drag_start_y = int(e.globalPosition().y())
        self._drag_start_h = self._target.height()
        e.accept()

    def mouseMoveEvent(self, event: object) -> None:
        e = event  # type: ignore[assignment]
        if self._dragging:
            delta = int(e.globalPosition().y()) - self._drag_start_y
            new_h = max(36, self._drag_start_h + delta)
            self._target.setFixedHeight(new_h)
            e.accept()

    def mouseReleaseEvent(self, event: object) -> None:
        if self._dragging:
            self._dragging = False
            event.accept()  # type: ignore[union-attr]
            # Height stays locked via setFixedHeight from mouseMoveEvent.
            # Next drag starts from the current height via mousePressEvent.


# ---------------------------------------------------------------------------
# QTextEdit with custom image loading (handles JPEG-as-.png, scales to fit)
# ---------------------------------------------------------------------------

_IMG_MAX_W = 550


class _ImageTextEdit(QTextEdit):
    """QTextEdit that loads and scales images to fit the viewport.

    Overrides ``loadResource`` to load images from Anki's media folder
    with auto-detected format (handles JPEG saved as .png) and scale
    them to the current viewport width.

    On resize, the HTML is re-set so ``loadResource`` is called again
    with the new viewport dimensions, making images dynamic.

    Do NOT use ``setBaseUrl`` with this widget — it bypasses ``loadResource``.
    """

    def __init__(self, media_dir: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._media_dir = media_dir

    def setHtml(self, html: str) -> None:  # type: ignore[override]
        self.document().clear()
        super().setHtml(html)

    def loadResource(self, rtype: int, url: object) -> object:  # type: ignore[override]
        if rtype != 2 or not self._media_dir:  # 2 = ImageResource
            return super().loadResource(rtype, url)  # type: ignore[arg-type]
        url_str = url.toString() if hasattr(url, "toString") else str(url)
        basename = url_str.rsplit("/", 1)[-1] if "/" in url_str else url_str
        filepath = os.path.join(self._media_dir, basename)
        if not os.path.isfile(filepath):
            return super().loadResource(rtype, url)  # type: ignore[arg-type]
        try:
            from aqt.qt import QImage as _QImage

            img = _QImage()
            if not img.load(filepath):
                return super().loadResource(rtype, url)  # type: ignore[arg-type]
            vp = self.viewport()
            max_w = (vp.width() - 10) if vp and vp.width() > 50 else _IMG_MAX_W
            max_h = (
                (vp.height() - 10)
                if vp and vp.height() > 50
                else _INITIAL_CONTENT_HEIGHT
            )
            # Scale to fit BOTH width and height, preserving aspect ratio
            scale_w = max_w / img.width() if img.width() > max_w else 1.0
            scale_h = max_h / img.height() if img.height() > max_h else 1.0
            scale = min(scale_w, scale_h)
            if scale < 1.0:
                img = img.scaled(
                    max(1, int(img.width() * scale)),
                    max(1, int(img.height() * scale)),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            return img
        except Exception:
            return super().loadResource(rtype, url)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Clickable arrow label (avoids QPushButton focus/repaint quirks)
# ---------------------------------------------------------------------------


class _ClickableArrow(QLabel):
    """A small clickable arrow indicator for expand/collapse."""

    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_ARROW_EXPANDED, parent)
        self.setFixedSize(22, 22)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(CLICKABLE_ARROW_STYLE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Collapse / Expand")

    def set_expanded(self, expanded: bool) -> None:
        self.setText(_ARROW_EXPANDED if expanded else _ARROW_COLLAPSED)

    def mousePressEvent(self, event: object) -> None:
        self.clicked.emit()


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------


class BatchReviewDialog(QDialog):
    """Shows proposed changes per note with field previews and inline editing."""

    _regen_done_signal = pyqtSignal(int, str, str, str)  # prop_idx, field, value, error

    def __init__(
        self,
        proposals: List[BatchProposedChange],
        dry_run: bool = False,
        elapsed_seconds: float = 0.0,
        parent: QWidget | None = None,
        batch_filler: object | None = None,
        user_prompt: str = "",
        note_items: list | None = None,
    ) -> None:
        super().__init__(parent)
        self._proposals = proposals
        self._dry_run = dry_run
        self._elapsed_seconds = elapsed_seconds
        self._approved: List[BatchProposedChange] = []
        self._note_checks: List[Optional[QCheckBox]] = []
        self._field_checks: Dict[tuple, QCheckBox] = {}
        self._edits: Dict[tuple, QPlainTextEdit] = {}
        self._rendered_edits: Dict[tuple, QTextEdit] = {}
        self._new_stacks: List[QStackedWidget] = []
        self._raw_mode = False
        self._base_url: Optional[QUrl] = _media_base_url()
        self._updating_checks = False
        self._content_containers: Dict[int, QWidget] = {}
        self._collapse_arrows: Dict[int, _ClickableArrow] = {}
        self._proposal_widgets: List[QGroupBox] = []
        self._proposal_types: List[Set[str]] = [
            _classify_proposal(p) for p in proposals
        ]
        self._status_filter: str = "all"
        self._content_filters: Set[str] = set()
        self._filter_fields_only = False  # True = show only matching fields
        self._batch_filler = batch_filler
        self._user_prompt = user_prompt
        self._note_items = note_items or []
        self._regen_buttons: Dict[tuple, QPushButton] = {}  # immediate regen buttons
        self._regen_checks: Dict[
            tuple, QCheckBox
        ] = {}  # batch regen staging checkboxes
        self._regen_original: Dict[tuple, str] = {}
        # Container for audio play buttons per field, so we can rebuild on regen
        self._sound_containers: Dict[tuple, QWidget] = {}
        # Wrapper widgets per field for show/hide during filtering
        self._field_containers: Dict[tuple, QWidget] = {}
        self._regen_done_signal.connect(self._on_regen_done)
        self._apply_btn: Optional[QPushButton] = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        title = "Dry Run Preview" if self._dry_run else "Review Changes"
        self.setWindowTitle(f"AI Filler \u2014 {title}")
        self.setMinimumSize(680, 540)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setStyleSheet(GLOBAL_STYLE)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        successful = [p for p in self._proposals if p.success]
        failed = [p for p in self._proposals if not p.success]
        partial = [p for p in successful if p.field_errors]

        # Header row with icon
        header_h_layout = QHBoxLayout()
        header_h_layout.setSpacing(10)

        icon_path = self._icons["search"] if self._dry_run else self._icons["check"]
        header_icon = QLabel()
        header_icon.setPixmap(get_themed_icon(icon_path, 22).pixmap(22, 22))
        header_h_layout.addWidget(header_icon)

        parts = [
            f"{len(successful)} notes to {'process' if self._dry_run else 'update'}"
        ]
        if partial:
            parts.append(f"{len(partial)} partially failed")
        if failed:
            parts.append(f"{len(failed)} failed")
        self._header_label = QLabel(", ".join(parts))
        self._header_label.setStyleSheet(HEADER_STYLE)
        self._header_label.setWordWrap(True)
        header_h_layout.addWidget(self._header_label)
        header_h_layout.addStretch()
        layout.addLayout(header_h_layout)

        if self._elapsed_seconds > 0 and successful:
            avg = self._elapsed_seconds / len(successful)
            stats_text = f"Generated in {_fmt_seconds(self._elapsed_seconds)}  \u2022  {avg:.1f}s per note"
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

        # --- Filter bar ---
        if not self._dry_run:
            self._build_filter_bar(layout)

        # Scrollable list of proposals
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        self._list_layout = QVBoxLayout()
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._list_layout.setSpacing(8)

        for idx, prop in enumerate(self._proposals):
            row = self._make_proposal_widget(idx, prop)
            self._proposal_widgets.append(row)
            self._list_layout.addWidget(row)

        container.setLayout(self._list_layout)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Bottom toolbar — compact dropdown for batch actions
        if not self._dry_run:
            toolbar = QHBoxLayout()
            toolbar.setSpacing(8)

            batch_menu = QMenu(self)
            batch_menu.addAction("Select All", self._select_all)
            batch_menu.addAction("Deselect All", self._deselect_all)
            batch_menu.addSeparator()
            batch_menu.addAction("Collapse All", self._collapse_all)
            batch_menu.addAction("Expand All", self._expand_all)
            if self._batch_filler is not None:
                batch_menu.addSeparator()
                batch_menu.addAction("Mark All for Regen", self._regen_select_all)
                batch_menu.addAction("Unmark All for Regen", self._regen_deselect_all)

            batch_btn = QPushButton(" Batch Actions")
            batch_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            batch_btn.setMenu(batch_menu)
            # Use a standard settings/cog icon if possible, but for now just text
            toolbar.addWidget(batch_btn)

            if self._batch_filler is not None:
                self._batch_regen_btn = self._flat_btn(" Regenerate Marked")
                self._batch_regen_btn.setToolTip(
                    "Regenerate all fields with amber toggle active"
                )
                qconnect(self._batch_regen_btn.clicked, self._on_batch_regenerate)
                toolbar.addWidget(self._batch_regen_btn)

            toolbar.addStretch()
            layout.addLayout(toolbar)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel" if not self._dry_run else "Close")
        cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        qconnect(cancel_btn.clicked, self.reject)
        btn_layout.addWidget(cancel_btn)

        if not self._dry_run:
            self._apply_btn = QPushButton("  Apply Selected  ")
            self._apply_btn.setIcon(get_themed_icon(self._icons["check"], 18))
            self._apply_btn.setDefault(True)
            self._apply_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            qconnect(self._apply_btn.clicked, self._on_apply)
            btn_layout.addWidget(self._apply_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    @staticmethod
    def _flat_btn(text: str) -> QPushButton:
        """Create a small toolbar-style button that doesn't steal focus."""
        btn = QPushButton(text)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setStyleSheet("QPushButton { padding: 4px 12px; font-size: 12px; }")
        return btn

    # ------------------------------------------------------------------
    # Filter bar — QComboBox for status, chip pills for content type
    # ------------------------------------------------------------------

    def _build_filter_bar(self, parent_layout: QVBoxLayout) -> None:
        # Row 1: Status dropdown + Content type chips
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        status_label = QLabel("Status:")
        status_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        row1.addWidget(status_label)

        self._status_combo = QComboBox()
        self._status_combo.addItems(["All", "Errors only", "Partial failures"])
        self._status_combo.setCurrentIndex(0)
        self._status_combo.setFixedWidth(140)
        self._status_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        qconnect(self._status_combo.currentIndexChanged, self._on_status_combo_changed)
        row1.addWidget(self._status_combo)

        row1.addSpacing(20)

        content_label = QLabel("Content:")
        content_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        row1.addWidget(content_label)

        self._filter_text_btn = QPushButton("Text")
        self._filter_image_btn = QPushButton("Images")
        self._filter_audio_btn = QPushButton("Audio")
        for btn, key in [
            (self._filter_text_btn, "text"),
            (self._filter_image_btn, "image"),
            (self._filter_audio_btn, "audio"),
        ]:
            btn.setCheckable(True)
            btn.setChecked(False)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet(FILTER_CHIP_STYLE)
            btn.setToolTip("Toggle filter (multi-select)")
            qconnect(btn.clicked, lambda _c=False, k=key: self._on_content_filter(k))
            row1.addWidget(btn)

        row1.addStretch()
        parent_layout.addLayout(row1)

        # Row 2: Matching fields only
        row2 = QHBoxLayout()
        self._fields_only_cb = QCheckBox("Show matching fields only")
        self._fields_only_cb.setChecked(False)
        self._fields_only_cb.setStyleSheet("font-size: 12px;")
        self._fields_only_cb.setToolTip(
            "When checked, hide fields that don't match the content filter.\n"
            "When unchecked, show the full note if any field matches."
        )
        qconnect(self._fields_only_cb.toggled, self._on_fields_only_toggled)
        row2.addWidget(self._fields_only_cb)
        row2.addStretch()
        parent_layout.addLayout(row2)

    # ------------------------------------------------------------------
    # Proposal card
    # ------------------------------------------------------------------

    def _make_proposal_widget(self, idx: int, prop: BatchProposedChange) -> QGroupBox:
        preview = prop.note_preview or f"Note #{prop.note_id}"
        group = QGroupBox()

        group_layout = QVBoxLayout()
        group_layout.setSpacing(6)
        group_layout.setContentsMargins(12, 12, 12, 12)

        header_row = QHBoxLayout()

        # Collapse arrow (QLabel-based, no focus quirks)
        if not self._dry_run and prop.success and prop.changes:
            arrow = _ClickableArrow()
            qconnect(arrow.clicked, lambda i=idx: self._toggle_collapse(i))
            header_row.addWidget(arrow)
            self._collapse_arrows[idx] = arrow

        # Note-level checkbox (tri-state)
        if not self._dry_run and prop.success:
            cb = QCheckBox(preview)
            cb.setChecked(True)
            cb.setTristate(True)
            cb.setCheckState(Qt.CheckState.Checked)
            cb.setStyleSheet("font-weight: 600;")
            cb.setToolTip("Toggle all fields in this note")
            qconnect(
                cb.stateChanged,
                lambda state, i=idx: self._on_note_check_changed(i, state),
            )
            self._note_checks.append(cb)
            header_row.addWidget(cb)
        else:
            label = QLabel(preview)
            label.setStyleSheet("font-weight: 600;")
            header_row.addWidget(label)
            self._note_checks.append(None)

        header_row.addStretch()
        group_layout.addLayout(header_row)

        # Collapsible content
        content_container = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(6)
        content_layout.setContentsMargins(0, 4, 0, 0)

        if not prop.success:
            err_row = QHBoxLayout()
            err_icon = QLabel()
            err_icon.setPixmap(
                get_themed_icon(self._icons["warning"], 14).pixmap(14, 14)
            )
            err_row.addWidget(err_icon)
            err_text = QLabel(f"Error: {prop.error}")
            err_text.setStyleSheet("color: #DC2626; font-size: 12px;")
            err_row.addWidget(err_text)
            err_row.addStretch()
            content_layout.addLayout(err_row)

            # Show blank fields with context so user can retry
            for field_name in prop.blank_fields:
                self._add_field_preview(content_layout, idx, field_name, "")
        elif self._dry_run:
            fields_text = ", ".join(prop.blank_fields) if prop.blank_fields else "none"
            info = QLabel(f"Fields to fill: <b>{fields_text}</b>")
            info.setStyleSheet(MUTED_LABEL_STYLE)
            content_layout.addWidget(info)
        else:
            for field_name, new_value in prop.changes.items():
                self._add_field_preview(content_layout, idx, field_name, new_value)
            # Show fields that failed with their error AND a regen button
            for field_name, err_msg in prop.field_errors.items():
                if field_name not in prop.changes:
                    # Field completely failed — show it as blank with regen option
                    self._add_field_preview(content_layout, idx, field_name, "")

                err_row = QHBoxLayout()
                err_icon = QLabel()
                err_icon.setPixmap(
                    get_themed_icon(self._icons["warning"], 14).pixmap(14, 14)
                )
                err_row.addWidget(err_icon)
                err_text = QLabel(f"<b>{field_name}</b>: {err_msg}")
                err_text.setStyleSheet(_FIELD_ERROR_STYLE)
                err_row.addWidget(err_text)
                err_row.addStretch()
                content_layout.addLayout(err_row)

        content_container.setLayout(content_layout)
        group_layout.addWidget(content_container)
        self._content_containers[idx] = content_container

        group.setLayout(group_layout)
        return group

    _MAX_ERROR_PREVIEW = 200

    def _add_error_block(
        self, parent_layout: QVBoxLayout, text: str, style: str
    ) -> None:
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
        toggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)

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

    # ------------------------------------------------------------------
    # Field preview (single-column)
    # ------------------------------------------------------------------

    def _add_field_preview(
        self, parent_layout: QVBoxLayout, prop_idx: int, field_name: str, value: str
    ) -> None:
        # Wrapper widget so we can show/hide the entire field block
        field_wrapper = QWidget()
        field_inner = QVBoxLayout()
        field_inner.setContentsMargins(0, 0, 0, 0)
        field_inner.setSpacing(2)

        label_row = QHBoxLayout()
        label_row.setSpacing(8)

        # Apply checkbox — labeled with the field name
        field_cb = QCheckBox(field_name)
        field_cb.setChecked(True)
        field_cb.setStyleSheet("font-weight: 600;")
        field_cb.setToolTip(f"Include '{field_name}' when applying changes")
        qconnect(
            field_cb.stateChanged,
            lambda _s, pi=prop_idx: self._on_field_check_changed(pi),
        )
        label_row.addWidget(field_cb)
        self._field_checks[(prop_idx, field_name)] = field_cb

        # Audio play buttons
        sound_container = QWidget()
        sound_layout = QHBoxLayout()
        sound_layout.setContentsMargins(0, 0, 0, 0)
        sound_layout.setSpacing(4)
        self._populate_sound_buttons(sound_layout, value)
        sound_container.setLayout(sound_layout)
        label_row.addWidget(sound_container)
        self._sound_containers[(prop_idx, field_name)] = sound_container

        label_row.addStretch()

        if self._batch_filler is not None:
            # Batch regen checkbox — clearly labeled
            regen_cb = QCheckBox("Batch regen")
            regen_cb.setChecked(False)
            regen_cb.setToolTip(
                "Check this to include the field when clicking 'Regenerate Marked'"
            )
            regen_cb.setStyleSheet(
                "QCheckBox { font-size: 11px; color: #92400E; }"
                "QCheckBox::indicator:checked { background: #F59E0B; border-color: #D97706; }"
            )
            label_row.addWidget(regen_cb)
            self._regen_checks[(prop_idx, field_name)] = regen_cb

            # Regen button — simple click = immediate single regen
            regen_btn = QPushButton(" Regen")
            regen_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            regen_btn.setToolTip(f"Regenerate '{field_name}' now")
            regen_btn.setStyleSheet(REGEN_TOGGLE_STYLE)
            qconnect(
                regen_btn.clicked,
                lambda _c=False, pi=prop_idx, fn=field_name: self._on_regenerate(
                    pi, fn
                ),
            )
            label_row.addWidget(regen_btn)
            self._regen_buttons[(prop_idx, field_name)] = regen_btn

        field_inner.addLayout(label_row)

        # Content — stacked widget for rendered / raw toggle
        stack = QStackedWidget()
        stack.setFixedHeight(_INITIAL_CONTENT_HEIGHT)

        # Page 0: rendered HTML (editable).  Uses _ImageTextEdit which
        # overrides loadResource to handle JPEG files with .png extension
        # and to scale images to fit the viewport.
        media_dir = ""
        try:
            media_dir = mw.col.media.dir()
        except Exception:
            pass
        rendered = _ImageTextEdit(media_dir=media_dir)
        rendered.setStyleSheet(_PREVIEW_RENDERED_STYLE)
        if value.strip():
            rendered.setHtml(value)
        else:
            rendered.setPlaceholderText("(empty)")
        rendered.document().setModified(False)
        stack.addWidget(rendered)

        edit = QPlainTextEdit()
        edit.setStyleSheet(_PREVIEW_STYLE)
        if value.strip():
            edit.setPlainText(value)
        else:
            edit.setPlaceholderText("(empty)")
        stack.addWidget(edit)

        stack.setCurrentIndex(0)
        field_inner.addWidget(stack)

        self._rendered_edits[(prop_idx, field_name)] = rendered
        self._edits[(prop_idx, field_name)] = edit
        self._new_stacks.append(stack)

        handle = _ResizeHandle(stack)
        field_inner.addWidget(handle)

        field_wrapper.setLayout(field_inner)
        parent_layout.addWidget(field_wrapper)
        self._field_containers[(prop_idx, field_name)] = field_wrapper

    @staticmethod
    def _populate_sound_buttons(layout: QHBoxLayout, value: str) -> None:
        """Add play buttons for any [sound:...] tags in *value*."""
        sounds = list(dict.fromkeys(_SOUND_RE.findall(value)))
        for fname in sounds:
            btn = QPushButton(f"\u25b6 {fname}")
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet("QPushButton { padding: 3px 8px; font-size: 11px; }")
            qconnect(
                btn.clicked,
                lambda _c=False, f=fname: av_player.play_tags(
                    [SoundOrVideoTag(filename=f)]
                ),
            )
            layout.addWidget(btn)

    def _rebuild_sound_buttons(
        self, prop_idx: int, field_name: str, value: str
    ) -> None:
        """Replace the audio play buttons for a field after regeneration."""
        key = (prop_idx, field_name)
        container = self._sound_containers.get(key)
        if container is None:
            return
        old_layout = container.layout()
        if old_layout:
            while old_layout.count():
                item = old_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            self._populate_sound_buttons(old_layout, value)
        container.updateGeometry()
        container.update()

    # ------------------------------------------------------------------
    # Toggle rendered / raw
    # ------------------------------------------------------------------

    def _on_toggle_raw(self, raw: bool) -> None:
        self._raw_mode = raw
        page = 1 if raw else 0
        if not raw:
            # Switching to rendered: update from raw editors
            for key, edit in self._edits.items():
                rendered = self._rendered_edits[key]
                text = edit.toPlainText()
                if text.strip():
                    rendered.setHtml(text)
                else:
                    rendered.setHtml("")
                    rendered.setPlaceholderText("(empty)")
                rendered.document().setModified(False)
        for new_stack in self._new_stacks:
            new_stack.setCurrentIndex(page)

    # ------------------------------------------------------------------
    # Checkbox logic
    # ------------------------------------------------------------------

    def _on_note_check_changed(self, prop_idx: int, state: int) -> None:
        if self._updating_checks:
            return
        self._updating_checks = True
        try:
            checked = state == int(Qt.CheckState.Checked)
            prop = self._proposals[prop_idx]
            for field_name in prop.changes:
                key = (prop_idx, field_name)
                if key in self._field_checks:
                    self._field_checks[key].setChecked(checked)
        finally:
            self._updating_checks = False

    def _on_field_check_changed(self, prop_idx: int) -> None:
        if self._updating_checks:
            return
        self._updating_checks = True
        try:
            note_cb = (
                self._note_checks[prop_idx]
                if prop_idx < len(self._note_checks)
                else None
            )
            if note_cb is None:
                return
            prop = self._proposals[prop_idx]
            states = []
            for field_name in prop.changes:
                key = (prop_idx, field_name)
                if key in self._field_checks:
                    states.append(self._field_checks[key].isChecked())
            if not states:
                return
            if all(states):
                note_cb.setCheckState(Qt.CheckState.Checked)
            elif not any(states):
                note_cb.setCheckState(Qt.CheckState.Unchecked)
            else:
                note_cb.setCheckState(Qt.CheckState.PartiallyChecked)
        finally:
            self._updating_checks = False

    def _select_all(self) -> None:
        self._updating_checks = True
        try:
            for cb in self._field_checks.values():
                cb.setChecked(True)
            for cb in self._note_checks:
                if cb is not None:
                    cb.setCheckState(Qt.CheckState.Checked)
        finally:
            self._updating_checks = False

    def _deselect_all(self) -> None:
        self._updating_checks = True
        try:
            for cb in self._field_checks.values():
                cb.setChecked(False)
            for cb in self._note_checks:
                if cb is not None:
                    cb.setCheckState(Qt.CheckState.Unchecked)
        finally:
            self._updating_checks = False

    # --- Regen selection (separate from apply) ---

    def _regen_select_all(self) -> None:
        for cb in self._regen_checks.values():
            cb.setChecked(True)

    def _regen_deselect_all(self) -> None:
        for cb in self._regen_checks.values():
            cb.setChecked(False)

    # ------------------------------------------------------------------
    # Collapse / expand
    # ------------------------------------------------------------------

    def _toggle_collapse(self, prop_idx: int) -> None:
        container = self._content_containers.get(prop_idx)
        arrow = self._collapse_arrows.get(prop_idx)
        if container is None:
            return
        visible = container.isVisible()
        container.setVisible(not visible)
        if arrow:
            arrow.set_expanded(not visible)

    def _collapse_all(self) -> None:
        for idx, container in self._content_containers.items():
            container.setVisible(False)
            arrow = self._collapse_arrows.get(idx)
            if arrow:
                arrow.set_expanded(False)

    def _expand_all(self) -> None:
        for idx, container in self._content_containers.items():
            container.setVisible(True)
            arrow = self._collapse_arrows.get(idx)
            if arrow:
                arrow.set_expanded(True)

    # ------------------------------------------------------------------
    # Filter controls
    # ------------------------------------------------------------------

    def _on_status_combo_changed(self, index: int) -> None:
        mapping = {0: "all", 1: "errors", 2: "partial"}
        self._status_filter = mapping.get(index, "all")
        self._apply_filters()

    def _on_content_filter(self, key: str) -> None:
        if key in self._content_filters:
            self._content_filters.discard(key)
        else:
            self._content_filters.add(key)
        # Sync button states and update text with checkmark
        for btn, k, label in [
            (self._filter_text_btn, "text", "Text"),
            (self._filter_image_btn, "image", "Images"),
            (self._filter_audio_btn, "audio", "Audio"),
        ]:
            active = k in self._content_filters
            btn.setChecked(active)
            btn.setText(f"\u2713 {label}" if active else label)
        self._apply_filters()

    def _on_fields_only_toggled(self, checked: bool) -> None:
        self._filter_fields_only = checked
        self._apply_filters()

    def _apply_filters(self) -> None:
        visible_count = 0
        for idx, widget in enumerate(self._proposal_widgets):
            prop = self._proposals[idx]
            show = self._matches_filters(idx, prop)
            widget.setVisible(show)
            if show:
                visible_count += 1

            # Per-field visibility when "Show matching fields only" is active.
            # Works with BOTH content type filters and status filters:
            # - Content filters: show only fields whose content matches the type
            # - "Partial failures" status: show only the fields that have errors
            # - "Errors" status: show all fields (entire note failed)
            field_keys = [(pi, fn) for (pi, fn) in self._field_containers if pi == idx]
            should_filter_fields = (
                show
                and self._filter_fields_only
                and (self._content_filters or self._status_filter == "partial")
            )
            if should_filter_fields:
                for pi, fn in field_keys:
                    container = self._field_containers[(pi, fn)]
                    visible = True  # default: show

                    # Content type filtering
                    if self._content_filters:
                        edit = self._edits.get((pi, fn))
                        value = edit.toPlainText() if edit else ""
                        if value.strip():
                            field_types = _classify_value(value)
                            if not field_types.intersection(self._content_filters):
                                visible = False
                        # Empty fields always stay visible (need regen)

                    # Status "partial" filtering: only show fields that errored
                    if self._status_filter == "partial" and prop.field_errors:
                        if fn not in prop.field_errors and fn not in prop.changes:
                            # Field is neither in changes nor in errors — it's
                            # a successfully generated field, hide it
                            pass
                        elif fn in prop.changes and fn not in prop.field_errors:
                            visible = False

                    container.setVisible(visible)
            else:
                for key in field_keys:
                    self._field_containers[key].setVisible(True)

        total = len(self._proposals)
        if visible_count == 0:
            self._header_label.setText(
                f"No proposals match the current filters ({total} total)"
            )
        elif visible_count < total:
            self._header_label.setText(f"Showing {visible_count} of {total} notes")
        else:
            successful = [p for p in self._proposals if p.success]
            failed = [p for p in self._proposals if not p.success]
            partial = [p for p in successful if p.field_errors]
            icon = "\U0001f50d" if self._dry_run else "\u2705"
            parts = [
                f"{icon}  {len(successful)} notes to {'process' if self._dry_run else 'update'}"
            ]
            if partial:
                parts.append(f"{len(partial)} partially failed")
            if failed:
                parts.append(f"{len(failed)} failed")
            self._header_label.setText(", ".join(parts))
        # Filters are a viewing convenience — never disable Apply.
        # Apply always operates on ALL checked fields regardless of filter state.

    def _matches_filters(self, idx: int, prop: BatchProposedChange) -> bool:
        if self._status_filter == "errors" and prop.success:
            return False
        if self._status_filter == "partial" and not (
            prop.success and prop.field_errors
        ):
            return False
        # Content filters don't apply to failed/empty notes (they have no content to classify)
        if self._content_filters and prop.changes:
            prop_types = self._proposal_types[idx]
            if not prop_types.intersection(self._content_filters):
                return False
        return True

    # ------------------------------------------------------------------
    # Audio playback
    # ------------------------------------------------------------------

    def _play_sound(self, filename: str) -> None:
        av_player.play_tags([SoundOrVideoTag(filename=filename)])

    # ------------------------------------------------------------------
    # Regenerate — single field
    # ------------------------------------------------------------------

    def _ask_regen_prompt(self) -> Optional[str]:
        """Show an optional prompt dialog. Returns the prompt or None if cancelled."""
        from aqt.utils import getText

        prompt, ok = getText(
            "Optional instructions for regeneration (leave empty for default):",
            parent=self,
            title="Regenerate",
        )
        if not ok:
            return None
        return prompt

    def _on_regenerate(self, prop_idx: int, field_name: str) -> None:
        prompt = self._ask_regen_prompt()
        if prompt is None:
            return
        self._start_regen(prop_idx, field_name, prompt)

    def _start_regen(self, prop_idx: int, field_name: str, extra_prompt: str) -> None:
        btn = self._regen_buttons.get((prop_idx, field_name))
        if btn:
            btn.setEnabled(False)

        prop = self._proposals[prop_idx]
        note_id = prop.note_id
        key = (prop_idx, field_name)
        self._regen_original[key] = prop.changes.get(field_name, "")

        deck_name = None
        for item in self._note_items:
            if item.note_id == note_id:
                deck_name = item.deck_name
                break

        # Combine the batch-level prompt with any extra per-regen prompt
        combined_prompt = self._user_prompt
        if extra_prompt.strip():
            combined_prompt = f"{combined_prompt}\n{extra_prompt}".strip()

        filler = self._batch_filler

        def background() -> None:
            try:
                new_value, error = filler.regenerate_field(  # type: ignore[union-attr]
                    note_id=note_id,
                    field_name=field_name,
                    user_prompt=combined_prompt,
                    deck_name=deck_name,
                )
                self._regen_done_signal.emit(prop_idx, field_name, new_value, error)
            except Exception as e:
                self._regen_done_signal.emit(prop_idx, field_name, "", str(e))

        threading.Thread(target=background, daemon=True).start()

    # ------------------------------------------------------------------
    # Regenerate — batch (multiple checked fields)
    # ------------------------------------------------------------------

    def _on_batch_regenerate(self) -> None:
        """Regenerate all fields staged via the 'Stage' checkboxes."""
        selected = [
            (pi, fn) for (pi, fn), cb in self._regen_checks.items() if cb.isChecked()
        ]
        if not selected:
            from aqt.utils import tooltip

            tooltip("No fields marked for regeneration.", parent=self)
            return

        prompt = self._ask_regen_prompt()
        if prompt is None:
            return

        if hasattr(self, "_batch_regen_btn"):
            self._batch_regen_btn.setEnabled(False)
            self._batch_regen_btn.setText(f"Regenerating 0/{len(selected)}...")

        self._batch_regen_pending = list(selected)
        self._batch_regen_total = len(selected)
        self._batch_regen_done_count = 0
        self._batch_regen_prompt = prompt

        for pi, fn in selected:
            self._start_regen(pi, fn, prompt)

    # ------------------------------------------------------------------
    # Regen done handler
    # ------------------------------------------------------------------

    def _on_regen_done(
        self, prop_idx: int, field_name: str, new_value: str, error: str
    ) -> None:
        if not self.isVisible():
            return
        if prop_idx < 0 or prop_idx >= len(self._proposals):
            return

        btn = self._regen_buttons.get((prop_idx, field_name))
        if btn:
            btn.setEnabled(True)

        # Track batch regen progress
        if hasattr(self, "_batch_regen_pending"):
            key_tuple = (prop_idx, field_name)
            if key_tuple in self._batch_regen_pending:
                self._batch_regen_pending.remove(key_tuple)
                self._batch_regen_done_count = (
                    getattr(self, "_batch_regen_done_count", 0) + 1
                )
                total = getattr(self, "_batch_regen_total", 0)
                if hasattr(self, "_batch_regen_btn"):
                    if self._batch_regen_pending:
                        self._batch_regen_btn.setText(
                            f"Regenerating {self._batch_regen_done_count}/{total}..."
                        )
                    else:
                        self._batch_regen_btn.setEnabled(True)
                        self._batch_regen_btn.setText("\u21bb Regenerate Marked")

        if error:
            from aqt.utils import showWarning

            showWarning(
                f"Regeneration failed for '{field_name}':\n{error}",
                title="AI Filler",
                parent=self,
            )
            return

        # Concurrent edit protection
        key = (prop_idx, field_name)
        original_snapshot = self._regen_original.pop(key, None)
        if key in self._edits:
            current_text = self._edits[key].toPlainText()
            if original_snapshot is not None and current_text != original_snapshot:
                from aqt.utils import showWarning

                showWarning(
                    f"'{field_name}' was edited during regeneration.\n"
                    f"Your edits have been preserved.",
                    title="AI Filler",
                    parent=self,
                )
                return

        # Update proposal
        self._proposals[prop_idx].changes[field_name] = new_value

        # Update editors
        if key in self._edits:
            edit = self._edits[key]
            if new_value.strip():
                edit.setPlainText(new_value)
            else:
                edit.setPlainText("")
                edit.setPlaceholderText("(empty)")
        if key in self._rendered_edits:
            rendered = self._rendered_edits[key]
            if new_value.strip():
                rendered.setHtml(new_value)
            else:
                rendered.setHtml("")
                rendered.setPlaceholderText("(empty)")
            rendered.document().setModified(False)

        # Update audio play buttons
        self._rebuild_sound_buttons(prop_idx, field_name, new_value)

        # Update classification and re-apply filters in case content type changed
        if prop_idx < len(self._proposal_types):
            self._proposal_types[prop_idx] = _classify_proposal(
                self._proposals[prop_idx]
            )
            self._apply_filters()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event: object) -> None:
        try:
            self._regen_done_signal.disconnect()
        except (RuntimeError, TypeError):
            pass
        super().closeEvent(event)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def _on_apply(self) -> None:
        # Sync WYSIWYG edits to raw editors before reading values
        if not self._raw_mode:
            for key, rendered in self._rendered_edits.items():
                if rendered.document().isModified():
                    extracted = _extract_body_html(rendered.toHtml())
                    if extracted.strip():
                        self._edits[key].setPlainText(extracted)

        for (prop_idx, field_name), edit in self._edits.items():
            text = edit.toPlainText()
            if text.strip():
                self._proposals[prop_idx].changes[field_name] = text
            else:
                # Empty editor = no content to apply for this field
                self._proposals[prop_idx].changes.pop(field_name, None)

        self._approved = []
        for i, prop in enumerate(self._proposals):
            if not prop.success:
                continue
            checked_fields = {}
            for field_name, value in prop.changes.items():
                key = (i, field_name)
                cb = self._field_checks.get(key)
                if cb is not None and cb.isChecked():
                    checked_fields[field_name] = value
            if checked_fields:
                approved_prop = BatchProposedChange(
                    note_id=prop.note_id,
                    note_preview=prop.note_preview,
                    blank_fields=prop.blank_fields,
                    changes=checked_fields,
                    original_values=prop.original_values,
                    error=prop.error,
                    field_errors=prop.field_errors,
                )
                self._approved.append(approved_prop)
        self.accept()

    def get_approved(self) -> List[BatchProposedChange]:
        return self._approved
