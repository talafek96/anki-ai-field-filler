"""Review dialog — shows proposed batch changes for approval before applying."""

from __future__ import annotations

from typing import List

from aqt.qt import *

from ..field_filler import BatchProposedChange
from .styles import GLOBAL_STYLE, HEADER_STYLE, MUTED_LABEL_STYLE


class BatchReviewDialog(QDialog):
    """Shows proposed changes per note and lets the user approve or reject."""

    def __init__(
        self,
        proposals: List[BatchProposedChange],
        dry_run: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._proposals = proposals
        self._dry_run = dry_run
        self._approved: List[BatchProposedChange] = []
        self._checks: List[QCheckBox] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        title = "Dry Run Preview" if self._dry_run else "Review Changes"
        self.setWindowTitle(f"AI Field Filler \u2014 {title}")
        self.setMinimumSize(600, 400)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setStyleSheet(GLOBAL_STYLE)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        successful = [p for p in self._proposals if p.success]
        failed = [p for p in self._proposals if not p.success]

        icon = "\U0001f50d" if self._dry_run else "\u2705"
        header = QLabel(
            f"{icon}  {len(successful)} notes to "
            f"{'process' if self._dry_run else 'update'}"
            f"{f', {len(failed)} failed' if failed else ''}"
        )
        header.setStyleSheet(HEADER_STYLE)
        layout.addWidget(header)

        # Scrollable list of proposals
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        list_layout = QVBoxLayout()
        list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        list_layout.setSpacing(8)

        for prop in self._proposals:
            row = self._make_proposal_widget(prop)
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

    def _make_proposal_widget(self, prop: BatchProposedChange) -> QGroupBox:
        preview = prop.note_preview or f"Note #{prop.note_id}"
        group = QGroupBox()

        group_layout = QVBoxLayout()
        group_layout.setSpacing(4)
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
            err = QLabel(f"\u274c Error: {prop.error[:200]}")
            err.setStyleSheet("color: #DC2626; font-size: 12px;")
            err.setWordWrap(True)
            group_layout.addWidget(err)
        elif self._dry_run:
            # Show which fields would be targeted
            fields_text = ", ".join(prop.blank_fields) if prop.blank_fields else "none"
            info = QLabel(f"Fields to fill: <b>{fields_text}</b>")
            info.setStyleSheet(MUTED_LABEL_STYLE)
            group_layout.addWidget(info)
        else:
            # Show proposed changes
            for field_name, new_value in prop.changes.items():
                field_label = QLabel(f"<b>{field_name}:</b>")
                group_layout.addWidget(field_label)
                value_preview = new_value[:150]
                if len(new_value) > 150:
                    value_preview += "..."
                val = QLabel(value_preview)
                val.setWordWrap(True)
                val.setStyleSheet(MUTED_LABEL_STYLE)
                group_layout.addWidget(val)

        group.setLayout(group_layout)
        return group

    def _select_all(self) -> None:
        for cb in self._checks:
            if cb is not None:
                cb.setChecked(True)

    def _deselect_all(self) -> None:
        for cb in self._checks:
            if cb is not None:
                cb.setChecked(False)

    def _on_apply(self) -> None:
        self._approved = []
        for i, prop in enumerate(self._proposals):
            cb = self._checks[i] if i < len(self._checks) else None
            if cb is not None and cb.isChecked() and prop.success:
                self._approved.append(prop)
        self.accept()

    def get_approved(self) -> List[BatchProposedChange]:
        """Return the list of proposals the user approved."""
        return self._approved
