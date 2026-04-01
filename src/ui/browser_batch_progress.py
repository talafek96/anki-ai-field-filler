"""Batch progress dialog — progress bar, ETA, cancel, and results summary."""

from __future__ import annotations

import threading
from typing import List, Optional

from aqt.qt import *

from ..core.filler import BatchFiller, BatchNoteItem, BatchProgress, BatchResult
from .theme import ACCENT_COLOR, GLOBAL_STYLE, MUTED_LABEL_STYLE


def _fmt_time(seconds: float) -> str:
    """Format seconds as 'm:ss' or 'h:mm:ss'."""
    s = int(seconds)
    if s < 3600:
        return f"{s // 60}:{s % 60:02d}"
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


class BatchProgressDialog(QDialog):
    """Shows a progress bar while batch-filling notes, then a summary."""

    _progress_signal = pyqtSignal(object)  # BatchProgress
    _done_signal = pyqtSignal(object)  # BatchResult

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._batch_filler: Optional[BatchFiller] = None
        self._result: Optional[BatchResult] = None
        self._setup_ui()
        self._progress_signal.connect(self._on_progress)
        self._done_signal.connect(self._on_done)

    def _setup_ui(self) -> None:
        self.setWindowTitle("AI Filler \u2014 Batch Progress")
        self.setMinimumWidth(460)
        self.setFixedHeight(200)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self._status_label = QLabel("\u2728 Preparing batch...")
        self._status_label.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {ACCENT_COLOR};"
        )
        layout.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                border: 1px solid #DDE1E6;
                border-radius: 6px;
                background: #F0F2F5;
                height: 20px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {ACCENT_COLOR};
                border-radius: 5px;
            }}
            """
        )
        layout.addWidget(self._progress_bar)

        self._detail_label = QLabel("")
        self._detail_label.setStyleSheet(MUTED_LABEL_STYLE)
        layout.addWidget(self._detail_label)

        self._preview_label = QLabel("")
        self._preview_label.setStyleSheet(MUTED_LABEL_STYLE)
        self._preview_label.setMaximumWidth(420)
        layout.addWidget(self._preview_label)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        qconnect(self._cancel_btn.clicked, self._on_cancel)
        btn_layout.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def start(
        self,
        items: List[BatchNoteItem],
        target_fields: List[str],
        user_prompt: str = "",
        dry_run: bool = False,
    ) -> None:
        """Start the batch in a background thread and show the dialog."""
        self._batch_filler = BatchFiller()
        self._progress_bar.setRange(0, len(items))
        self._progress_bar.setValue(0)

        mode = "Dry run" if dry_run else "Processing"
        self._status_label.setText(f"\u2728 {mode}: 0 / {len(items)}")

        def background() -> None:
            result = self._batch_filler.run(
                items=items,
                target_fields=target_fields,
                user_prompt=user_prompt,
                dry_run=dry_run,
                on_progress=lambda p: self._progress_signal.emit(p),
            )
            self._done_signal.emit(result)

        threading.Thread(target=background, daemon=True).start()

    def _on_progress(self, p: BatchProgress) -> None:
        self._progress_bar.setValue(p.completed)
        pct = int(p.completed / p.total * 100) if p.total else 0
        eta = _fmt_time(p.eta_seconds) if p.eta_seconds > 0 else "--:--"
        elapsed = _fmt_time(p.elapsed_seconds)
        self._status_label.setText(f"\u2728 Processing: {p.completed} / {p.total} ({pct}%)")
        self._detail_label.setText(f"Elapsed: {elapsed}  \u2022  ETA: {eta}")
        if p.current_note_preview:
            self._preview_label.setText(f"Current: {p.current_note_preview}")

    def _on_done(self, result: BatchResult) -> None:
        self._result = result
        self.accept()

    def _on_cancel(self) -> None:
        if self._batch_filler:
            self._batch_filler.cancel()
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setText("Cancelling...")
        self._status_label.setText("\u23f3 Cancelling after current note...")

    def get_result(self) -> Optional[BatchResult]:
        return self._result


class BatchSummaryDialog(QDialog):
    """Shows a summary after batch processing, with failure details."""

    def __init__(self, result: BatchResult, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._result = result
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("AI Filler \u2014 Batch Complete")
        self.setMinimumWidth(460)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setStyleSheet(GLOBAL_STYLE)

        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        r = self._result
        mode = " (dry run)" if r.dry_run else ""
        icon = "\u2705" if r.failed == 0 else "\u26a0\ufe0f"
        header = QLabel(f"{icon}  Batch Complete{mode}")
        header.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {ACCENT_COLOR};")
        layout.addWidget(header)

        # Summary stats
        stats_rows = (
            f"<tr><td><b>Total notes:</b></td><td>{r.total}</td></tr>"
            f"<tr><td><b>Succeeded:</b></td><td>{r.succeeded}</td></tr>"
            f"<tr><td><b>Failed:</b></td><td>{r.failed}</td></tr>"
            f"<tr><td><b>Skipped:</b></td>"
            f"<td>{r.skipped} (already filled or cancelled)</td></tr>"
        )
        if r.elapsed_seconds > 0:
            elapsed = _fmt_time(r.elapsed_seconds)
            stats_rows += f"<tr><td><b>Elapsed:</b></td><td>{elapsed}</td></tr>"
            if r.succeeded > 0:
                avg = r.elapsed_seconds / r.succeeded
                stats_rows += f"<tr><td><b>Avg per note:</b></td><td>{avg:.1f}s</td></tr>"
        stats = QLabel(f"<table>{stats_rows}</table>")
        layout.addWidget(stats)

        # Failure details (only if there are failures)
        if r.failures:
            fail_group = QGroupBox(f"Failures ({len(r.failures)})")
            fail_layout = QVBoxLayout()

            fail_list = QPlainTextEdit()
            fail_list.setReadOnly(True)
            fail_list.setMaximumHeight(150)
            lines = []
            for f in r.failures:
                lines.append(f"Note ID {f.note_id}: {f.error}")
            fail_list.setPlainText("\n\n".join(lines))
            fail_layout.addWidget(fail_list)

            fail_group.setLayout(fail_layout)
            layout.addWidget(fail_group)

        # OK button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        qconnect(ok_btn.clicked, self.accept)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
