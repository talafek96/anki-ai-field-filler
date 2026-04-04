"""Modal progress dialog shown while AI content is being generated."""

from __future__ import annotations

import os

from aqt.qt import *

from ..common.icons import get_themed_icon
from ..common.theme import ACCENT_COLOR, GLOBAL_STYLE


class GeneratingDialog(QDialog):
    """Blocking 'Generating' overlay with a sparkle animation.

    Call :meth:`finish` (or :meth:`finish_with_error`) from
    ``mw.taskman.run_on_main`` once generation completes.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("AI Filler")
        self.setFixedSize(340, 160)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowCloseButtonHint
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setStyleSheet(GLOBAL_STYLE)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        addon_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        self._sparkles_icon_path = os.path.join(
            addon_dir, "assets", "icons", "app", "sparkles.svg"
        )
        self._icon_label.setPixmap(
            get_themed_icon(self._sparkles_icon_path, 36).pixmap(36, 36)
        )

        layout.addWidget(self._icon_label)

        self._label = QLabel("Generating\u2026")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            f"font-size: 16px; font-weight: 600; color: {ACCENT_COLOR};"
        )
        layout.addWidget(self._label)

        self._sub = QLabel("This may take a moment")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub.setStyleSheet("font-size: 12px; color: #6B7280;")
        layout.addWidget(self._sub)

        self.setLayout(layout)

        # Pulse animation on the sparkle emoji
        self._timer = QTimer(self)
        self._timer.setInterval(600)
        self._timer.timeout.connect(self._pulse)
        self._big = True
        self._timer.start()

    def _pulse(self) -> None:
        size = 36 if self._big else 28
        self._icon_label.setPixmap(
            get_themed_icon(self._sparkles_icon_path, size).pixmap(size, size)
        )
        self._big = not self._big

    # ------------------------------------------------------------------
    # Public API (call from main thread via mw.taskman.run_on_main)
    # ------------------------------------------------------------------

    def finish(self) -> None:
        """Close the dialog on success."""
        self._timer.stop()
        self.accept()

    def finish_with_error(self, message: str) -> None:
        """Close the dialog and report an error."""
        self._timer.stop()
        self.reject()
