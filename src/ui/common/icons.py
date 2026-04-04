"""Utility for loading and tinting SVG icons based on Anki's theme."""

from __future__ import annotations

import os

from aqt.qt import *

try:
    from aqt.qt import QSvgRenderer
except ImportError:
    # Fallback for different PyQt versions/Anki builds
    try:
        from PyQt6.QtSvg import QSvgRenderer
    except ImportError:
        from PyQt5.QtSvg import QSvgRenderer
from aqt.theme import theme_manager


def get_themed_icon(icon_path: str, size: int = 20, should_tint: bool = True) -> QIcon:
    """Load an SVG and tint it white for dark mode or black for light mode."""
    if not os.path.exists(icon_path) or not icon_path:
        return QIcon()

    if not should_tint:
        return QIcon(icon_path)

    # Use SVG renderer for high-quality scaling
    renderer = QSvgRenderer(icon_path)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)

    # Apply theme-based tint
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    if theme_manager.night_mode:
        painter.fillRect(pixmap.rect(), QColor("#FFFFFF"))
    else:
        painter.fillRect(pixmap.rect(), QColor("#000000"))
    painter.end()

    return QIcon(pixmap)
