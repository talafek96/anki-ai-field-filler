"""Tests for the provider logos shown in the provider picker."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ai_field_filler.ui.provider_icons import _ICON_DIR, tinted_svg

_DEFAULTS = Path(__file__).parent.parent / "src" / "ai_field_filler" / "config.json"


def _shipped_provider_types() -> list:
    return list(json.loads(_DEFAULTS.read_text(encoding="utf-8"))["providers"])


def test_every_shipped_provider_has_a_logo() -> None:
    for ptype in _shipped_provider_types():
        assert tinted_svg(ptype, "#000000") is not None, ptype


def test_single_color_logos_take_the_theme_color() -> None:
    for ptype in ("openai", "openrouter"):
        svg = tinted_svg(ptype, "#a1b2c3")
        assert svg is not None
        assert b'fill="#a1b2c3"' in svg
        assert b"currentColor" not in svg


def test_color_logos_keep_their_brand_colors() -> None:
    claude = tinted_svg("anthropic", "#a1b2c3")
    gemini = tinted_svg("google", "#a1b2c3")
    assert claude is not None and gemini is not None
    assert b"<title>Claude</title>" in claude
    assert b'fill="#D97757"' in claude
    assert b'fill="#3186FF"' in gemini
    assert b"#a1b2c3" not in claude + gemini


def test_openrouter_is_lime_only_on_dark_themes() -> None:
    # Lime #C8FF00 is ~1.1:1 against white, so light themes get the mono mark.
    light = tinted_svg("openrouter", "#111111", dark=False)
    dark = tinted_svg("openrouter", "#eeeeee", dark=True)
    assert light is not None and dark is not None
    assert b'fill="#111111"' in light and b"#C8FF00" not in light
    assert b'fill="#C8FF00"' in dark


def test_dark_theme_falls_back_to_the_normal_logo() -> None:
    assert tinted_svg("openai", "#eeeeee", dark=True) == tinted_svg("openai", "#eeeeee")


def test_unknown_provider_has_no_logo() -> None:
    assert tinted_svg("my-custom-provider", "#000000") is None


def test_logos_are_plain_vector_art() -> None:
    # The addon ships these files; they must not script or fetch anything.
    for path in _ICON_DIR.glob("*.svg"):
        svg = path.read_text(encoding="utf-8").lower()
        for banned in ("<script", "href=", "<foreignobject", "<image"):
            assert banned not in svg, (path.name, banned)
        assert not re.search(r"\son\w+\s*=", svg), (path.name, "event handler")


def test_logos_ship_with_their_license() -> None:
    notice = (_ICON_DIR / "LICENSE.txt").read_text(encoding="utf-8")
    assert "MIT License" in notice
    assert "LobeHub" in notice
