"""Shared stylesheet helpers for a modern, polished UI with dark mode support.

Every public name is a **function** so it evaluates the correct palette
(light or dark) at call time rather than at import time.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Theme detection
# ---------------------------------------------------------------------------


def _is_dark() -> bool:
    """Return ``True`` when Anki's night-mode is active."""
    try:
        from aqt.theme import theme_manager

        return theme_manager.night_mode
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------

_LIGHT = dict(
    accent="#5B8DEF",
    accent_hover="#4A7DE0",
    accent_pressed="#3D6DD4",
    bg="#F5F6F8",
    bg_card="#FAFBFC",
    bg_input="#FFFFFF",
    border="#DDE1E6",
    border_focus="#5B8DEF",
    border_hover="#C4CAD3",
    text_muted="#6B7280",
    text_primary="#1F2937",
    hover_bg="#F0F2F5",
    pressed_bg="#E5E8EC",
    disabled_bg="#F0F2F5",
    disabled_text="#A0A7B3",
    scrollbar="#D1D5DB",
    scrollbar_hover="#9CA3AF",
    chip_hover_bg="#EEF2FD",
    tab_hover_bg="#EDEEF1",
    error_text="#DC2626",
    warning_text="#92400E",
    warning_bg="#FEF3C7",
    warning_border="#F59E0B",
    regen="#F59E0B",
    regen_hover_bg="#FFFBEB",
    regen_hover_text="#92400E",
    regen_checked_border="#D97706",
    regen_pressed="#D97706",
    regen_pressed_border="#B45309",
    resize_handle="#C4CAD3",
)

_DARK = dict(
    accent="#7AA2F7",
    accent_hover="#89B4FA",
    accent_pressed="#5D8AD0",
    bg="#2B2B2B",
    bg_card="#363636",
    bg_input="#3C3C3C",
    border="#505050",
    border_focus="#7AA2F7",
    border_hover="#5A5A5A",
    text_muted="#8C8C8C",
    text_primary="#D4D4D4",
    hover_bg="#424242",
    pressed_bg="#4A4A4A",
    disabled_bg="#333333",
    disabled_text="#606060",
    scrollbar="#505050",
    scrollbar_hover="#6A6A6A",
    chip_hover_bg="#2A3555",
    tab_hover_bg="#3A3A3A",
    error_text="#FF6B6B",
    warning_text="#FFB86C",
    warning_bg="#3A3220",
    warning_border="#CC8030",
    regen="#FFB86C",
    regen_hover_bg="#3A3220",
    regen_hover_text="#FFB86C",
    regen_checked_border="#D09050",
    regen_pressed="#D09050",
    regen_pressed_border="#B07030",
    resize_handle="#606060",
)


def palette() -> dict:
    """Return the active colour palette (light or dark)."""
    return _DARK if _is_dark() else _LIGHT


# ---------------------------------------------------------------------------
# Public style helpers — call these as functions, e.g. GLOBAL_STYLE()
# ---------------------------------------------------------------------------


def ACCENT_COLOR() -> str:  # noqa: N802
    return palette()["accent"]


def MUTED_LABEL_STYLE() -> str:  # noqa: N802
    p = palette()
    return f"color: {p['text_muted']}; font-size: 12px;"


def HEADER_STYLE() -> str:  # noqa: N802
    p = palette()
    return f"""
        font-size: 15px;
        font-weight: 600;
        color: {p["text_primary"]};
        padding: 2px 0;
    """


def GLOBAL_STYLE() -> str:  # noqa: N802
    p = palette()
    return f"""
    QDialog {{
        background-color: {p["bg"]};
    }}

    QGroupBox {{
        background-color: {p["bg_card"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        margin-top: 14px;
        padding: 16px 12px 12px 12px;
        font-weight: 600;
        color: {p["text_primary"]};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 6px;
        color: {p["accent"]};
    }}

    QLabel {{
        color: {p["text_primary"]};
    }}

    QLineEdit, QPlainTextEdit, QSpinBox {{
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 6px 8px;
        background: {p["bg_input"]};
        color: {p["text_primary"]};
        selection-background-color: {p["accent"]};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{
        border-color: {p["border_focus"]};
    }}

    QComboBox {{
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 5px 8px;
        background: {p["bg_input"]};
        color: {p["text_primary"]};
    }}
    QComboBox:focus {{
        border-color: {p["border_focus"]};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background: {p["bg_input"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border"]};
        selection-background-color: {p["accent"]};
        selection-color: #FFFFFF;
    }}

    QPushButton {{
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 7px 18px;
        background: {p["bg_input"]};
        color: {p["text_primary"]};
        font-weight: 500;
        outline: none;
    }}
    QPushButton:hover {{
        background: {p["hover_bg"]};
        border-color: {p["border_hover"]};
    }}
    QPushButton:pressed {{
        background: {p["pressed_bg"]};
    }}
    QPushButton:focus {{
        outline: none;
        background: {p["bg_input"]};
        border-color: {p["border"]};
    }}
    QPushButton:default {{
        background: {p["accent"]};
        color: #FFFFFF;
        border-color: {p["accent"]};
    }}
    QPushButton:default:hover {{
        background: {p["accent_hover"]};
        border-color: {p["accent_hover"]};
    }}
    QPushButton:default:pressed {{
        background: {p["accent_pressed"]};
        border-color: {p["accent_pressed"]};
    }}
    QPushButton:disabled {{
        background: {p["disabled_bg"]};
        color: {p["disabled_text"]};
        border-color: {p["border"]};
    }}

    QCheckBox {{
        spacing: 6px;
        color: {p["text_primary"]};
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid {p["border"]};
        background: {p["bg_input"]};
    }}
    QCheckBox::indicator:checked {{
        background: {p["accent"]};
        border-color: {p["accent"]};
    }}

    QTabWidget::pane {{
        border: 1px solid {p["border"]};
        border-radius: 8px;
        background: {p["bg"]};
        top: -1px;
    }}
    QTabBar::tab {{
        padding: 8px 20px;
        margin-right: 2px;
        border: 1px solid transparent;
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        color: {p["text_muted"]};
    }}
    QTabBar::tab:selected {{
        background: {p["bg"]};
        color: {p["accent"]};
        border-color: {p["border"]};
        font-weight: 600;
    }}
    QTabBar::tab:hover:!selected {{
        color: {p["text_primary"]};
        background: {p["tab_hover_bg"]};
    }}

    QListWidget {{
        border: 1px solid {p["border"]};
        border-radius: 6px;
        background: {p["bg_input"]};
        color: {p["text_primary"]};
        outline: none;
    }}
    QListWidget::item:selected {{
        background: {p["accent"]};
        color: #FFFFFF;
    }}

    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        border: none;
        background: transparent;
        width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: {p["scrollbar"]};
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p["scrollbar_hover"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QToolButton {{
        border: 1px solid {p["border"]};
        border-radius: 6px;
        background: {p["bg_input"]};
        outline: none;
    }}
    QToolButton:hover {{
        background: {p["hover_bg"]};
        border-color: {p["border_hover"]};
    }}
    QToolButton:pressed {{
        background: {p["pressed_bg"]};
    }}

    QDialogButtonBox > QPushButton {{
        min-width: 80px;
    }}
    """


# ---------------------------------------------------------------------------
# Filter chip style — rounded pill with clear active/inactive states
# ---------------------------------------------------------------------------


def FILTER_CHIP_STYLE() -> str:  # noqa: N802
    p = palette()
    return f"""
    QPushButton {{
        border: 1px solid {p["border"]};
        border-radius: 14px;
        padding: 4px 14px;
        background: {p["bg_input"]};
        color: {p["text_muted"]};
        font-weight: 500;
        font-size: 12px;
        outline: none;
    }}
    QPushButton:hover {{
        border-color: {p["accent"]};
        background: {p["chip_hover_bg"]};
        color: {p["text_primary"]};
    }}
    QPushButton:checked {{
        background: {p["accent"]};
        color: #FFFFFF;
        border-color: {p["accent"]};
        font-weight: 600;
    }}
    QPushButton:checked:hover {{
        background: {p["accent_hover"]};
        border-color: {p["accent_hover"]};
    }}
    """


# ---------------------------------------------------------------------------
# Regen toggle button — amber when marked for batch regeneration
# ---------------------------------------------------------------------------


def REGEN_TOGGLE_STYLE() -> str:  # noqa: N802
    p = palette()
    return f"""
    QPushButton {{
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 3px 10px;
        background: {p["bg_input"]};
        color: {p["text_muted"]};
        font-size: 12px;
        outline: none;
    }}
    QPushButton:hover {{
        border-color: {p["regen"]};
        background: {p["regen_hover_bg"]};
        color: {p["regen_hover_text"]};
    }}
    QPushButton:checked {{
        background: {p["regen"]};
        color: #FFFFFF;
        border-color: {p["regen_checked_border"]};
    }}
    QPushButton:checked:hover {{
        background: {p["regen_pressed"]};
        border-color: {p["regen_pressed_border"]};
    }}
    """


# ---------------------------------------------------------------------------
# Batch review dialog — preview and error styles
# ---------------------------------------------------------------------------


def PREVIEW_STYLE() -> str:  # noqa: N802
    p = palette()
    return (
        f"border: 1px solid {p['border']}; border-radius: 6px; "
        f"padding: 6px 8px; background: {p['bg_input']}; "
        f"color: {p['text_primary']}; font-size: 13px;"
    )


def PREVIEW_RENDERED_STYLE() -> str:  # noqa: N802
    p = palette()
    return (
        f"background: {p['bg_input']}; border: 1px solid {p['border']}; "
        f"border-radius: 6px; color: {p['text_primary']}; font-size: 13px;"
    )


def FIELD_ERROR_STYLE() -> str:  # noqa: N802
    p = palette()
    return (
        f"color: {p['warning_text']}; font-size: 12px; padding: 4px 8px; "
        f"background: {p['warning_bg']}; border-left: 3px solid {p['warning_border']}; "
        f"border-radius: 2px;"
    )


def ERROR_LABEL_STYLE() -> str:  # noqa: N802
    """Red error text (used for fully-failed notes)."""
    p = palette()
    return f"color: {p['error_text']}; font-size: 12px;"


def REGEN_CHECKBOX_STYLE() -> str:  # noqa: N802
    p = palette()
    return (
        f"QCheckBox {{ font-size: 11px; color: {p['warning_text']}; }}"
        f"QCheckBox::indicator:checked {{ background: {p['regen']}; "
        f"border-color: {p['regen_checked_border']}; }}"
    )


def PROGRESS_BAR_STYLE() -> str:  # noqa: N802
    p = palette()
    return f"""
    QProgressBar {{
        border: 1px solid {p["border"]};
        border-radius: 6px;
        background: {p["hover_bg"]};
        height: 20px;
        text-align: center;
        color: {p["text_primary"]};
    }}
    QProgressBar::chunk {{
        background: {p["accent"]};
        border-radius: 5px;
    }}
    """
