"""Provider logos for provider pickers, matched to the current theme."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from aqt.qt import *

_ICON_DIR = Path(__file__).parent / "icons" / "providers"


def tinted_svg(provider_type: str, color: str, dark: bool = False) -> Optional[bytes]:
    """SVG bytes of *provider_type*'s logo, or None if it has none.

    Brands with a colour logo (Claude, Gemini) keep their own colours. Brands
    whose logo is a single colour ship as ``fill="currentColor"`` and are drawn
    in *color*, the theme's text colour: Qt has no notion of ``currentColor``.
    A brand colour that only reads on a dark background (OpenRouter's lime)
    ships as ``<provider>-dark.svg``, used instead when *dark* is set.
    """
    candidates = [f"{provider_type}-dark.svg"] if dark else []
    candidates.append(f"{provider_type}.svg")
    for name in candidates:
        path = _ICON_DIR / name
        if path.is_file():
            svg = path.read_text(encoding="utf-8")
            return svg.replace('fill="currentColor"', f'fill="{color}"').encode("utf-8")
    return None


def provider_icon(provider_type: str, color: QColor) -> QIcon:
    """Logo for *provider_type* on a background whose text is *color*.

    Light text means a dark theme. Returns an empty icon when there is no logo.
    """
    data = tinted_svg(provider_type, color.name(), dark=color.lightness() > 127)
    pixmap = QPixmap()
    # Without Qt's SVG image plugin loadFromData fails; the picker then shows
    # plain names, which is better than breaking the settings dialog.
    if data is None or not pixmap.loadFromData(data, "SVG"):
        return QIcon()
    return QIcon(pixmap)
