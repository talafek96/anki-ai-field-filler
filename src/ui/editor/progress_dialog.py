"""Modal progress dialog shown while AI content is being generated."""

from __future__ import annotations

from aqt.qt import *

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

        self._emoji = QLabel("\u2728")
        self._emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._emoji.setStyleSheet("font-size: 36px;")
        layout.addWidget(self._emoji)

        self._label = QLabel("Generating\u2026")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {ACCENT_COLOR};")
        layout.addWidget(self._label)

        self._sub = QLabel("This may take a moment")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub.setStyleSheet("font-size: 12px; color: #6B7280;")
        layout.addWidget(self._sub)

        self.setLayout(layout)

        # Pulse animation on the sparkle emoji
        self._anim = QPropertyAnimation(self._emoji, b"windowOpacity")
        self._anim.setDuration(900)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.3)
        self._anim.setLoopCount(-1)
        # windowOpacity only works on top-level widgets; use a timer to
        # swap emoji size instead for a gentle pulse effect.
        self._timer = QTimer(self)
        self._timer.setInterval(600)
        self._timer.timeout.connect(self._pulse)
        self._big = True
        self._timer.start()

    def _pulse(self) -> None:
        size = "36px" if self._big else "30px"
        self._emoji.setStyleSheet(f"font-size: {size};")
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
