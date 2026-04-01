"""Shared stylesheet constants for a modern, polished UI with Dark Mode support."""

from __future__ import annotations

try:
    from aqt import mw
    from aqt.theme import theme_manager
    IS_DARK = theme_manager.night_mode if theme_manager else False
except ImportError:
    IS_DARK = False

# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------

if IS_DARK:
    # Dark Mode Palette
    _ACCENT = "#7DA7F5"  # Lighter blue for dark bg
    _ACCENT_HOVER = "#9BBDF9"
    _ACCENT_PRESSED = "#6392E6"
    _BG_WINDOW = "#1C1D1F"
    _BG_CARD = "#2D2E31"
    _BG_INPUT = "#3E3F43"
    _BORDER = "#4B4D51"
    _BORDER_FOCUS = "#7DA7F5"
    _TEXT_PRIMARY = "#E3E3E3"
    _TEXT_MUTED = "#9CA3AF"
    _BTN_BG = "#3E3F43"
    _BTN_HOVER = "#4B4D51"
    _BTN_PRESSED = "#2D2E31"
    _TAB_BG = "#262729"
    _TAB_HOVER = "#353639"
else:
    # Light Mode Palette
    _ACCENT = "#5B8DEF"
    _ACCENT_HOVER = "#4A7DE0"
    _ACCENT_PRESSED = "#3D6DD4"
    _BG_WINDOW = "#F5F6F8"
    _BG_CARD = "#FAFBFC"
    _BG_INPUT = "white"
    _BORDER = "#DDE1E6"
    _BORDER_FOCUS = "#5B8DEF"
    _TEXT_PRIMARY = "#1F2937"
    _TEXT_MUTED = "#6B7280"
    _BTN_BG = "white"
    _BTN_HOVER = "#F0F2F5"
    _BTN_PRESSED = "#E5E8EC"
    _TAB_BG = "#F5F6F8"
    _TAB_HOVER = "#EDEEF1"

# ---------------------------------------------------------------------------
# Reusable stylesheet fragments
# ---------------------------------------------------------------------------

GLOBAL_STYLE = f"""
    QDialog {{
        background-color: {_BG_WINDOW};
    }}

    QGroupBox {{
        background-color: {_BG_CARD};
        border: 1px solid {_BORDER};
        border-radius: 8px;
        margin-top: 14px;
        padding: 16px 12px 12px 12px;
        font-weight: 600;
        color: {_TEXT_PRIMARY};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 6px;
        color: {_ACCENT};
    }}

    QLabel {{
        color: {_TEXT_PRIMARY};
    }}

    QLineEdit, QPlainTextEdit, QSpinBox {{
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 6px 8px;
        background: {_BG_INPUT};
        color: {_TEXT_PRIMARY};
        selection-background-color: {_ACCENT};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{
        border-color: {_BORDER_FOCUS};
    }}

    QComboBox {{
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 5px 8px;
        background: {_BG_INPUT};
        color: {_TEXT_PRIMARY};
    }}
    QComboBox:focus {{
        border-color: {_BORDER_FOCUS};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QPushButton {{
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 7px 18px;
        background: {_BTN_BG};
        color: {_TEXT_PRIMARY};
        font-weight: 500;
        outline: none;
    }}
    QPushButton:hover {{
        background: {_BTN_HOVER};
        border-color: {"#555" if IS_DARK else "#C4CAD3"};
    }}
    QPushButton:pressed {{
        background: {_BTN_PRESSED};
    }}
    QPushButton:focus {{
        outline: none;
        background: {_BTN_BG};
        border-color: {_BORDER};
    }}
    QPushButton:default {{
        background: {_ACCENT};
        color: white;
        border-color: {_ACCENT};
    }}
    QPushButton:default:hover {{
        background: {_ACCENT_HOVER};
        border-color: {_ACCENT_HOVER};
    }}
    QPushButton:default:pressed {{
        background: {_ACCENT_PRESSED};
        border-color: {_ACCENT_PRESSED};
    }}
    QPushButton:disabled {{
        background: {_BTN_HOVER};
        color: {"#666" if IS_DARK else "#A0A7B3"};
        border-color: {_BORDER};
    }}

    QCheckBox {{
        spacing: 6px;
        color: {_TEXT_PRIMARY};
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid {_BORDER};
        background: {_BG_INPUT};
    }}
    QCheckBox::indicator:checked {{
        background: {_ACCENT};
        border-color: {_ACCENT};
    }}

    QTabWidget::pane {{
        border: 1px solid {_BORDER};
        border-radius: 8px;
        background: {_TAB_BG};
        top: -1px;
    }}
    QTabBar::tab {{
        padding: 8px 20px;
        margin-right: 2px;
        border: 1px solid transparent;
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        color: {_TEXT_MUTED};
    }}
    QTabBar::tab:selected {{
        background: {_TAB_BG};
        color: {_ACCENT};
        border-color: {_BORDER};
        font-weight: 600;
    }}
    QTabBar::tab:hover:!selected {{
        color: {_TEXT_PRIMARY};
        background: {_TAB_HOVER};
    }}

    QListWidget {{
        border: 1px solid {_BORDER};
        border-radius: 6px;
        background: {_BG_INPUT};
        color: {_TEXT_PRIMARY};
        outline: none;
    }}
    QListWidget::item:selected {{
        background: {_ACCENT};
        color: white;
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
        background: {"#555" if IS_DARK else "#D1D5DB"};
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {"#777" if IS_DARK else "#9CA3AF"};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QToolButton {{
        border: 1px solid {_BORDER};
        border-radius: 6px;
        background: {_BTN_BG};
        color: {_TEXT_PRIMARY};
        outline: none;
    }}
    QToolButton:hover {{
        background: {_BTN_HOVER};
        border-color: {"#555" if IS_DARK else "#C4CAD3"};
    }}
    QToolButton:pressed {{
        background: {_BTN_PRESSED};
    }}

    QDialogButtonBox > QPushButton {{
        min-width: 80px;
    }}
"""

MUTED_LABEL_STYLE = f"color: {_TEXT_MUTED}; font-size: 12px;"

HEADER_STYLE = f"""
    font-size: 15px;
    font-weight: 600;
    color: {_TEXT_PRIMARY};
    padding: 2px 0;
"""

ACCENT_COLOR = _ACCENT

# ---------------------------------------------------------------------------
# Specific dialog styles
# ---------------------------------------------------------------------------

_INPUT_BORDER = "#5E626B" if IS_DARK else "#DDE1E6"

PREVIEW_STYLE = (
    f"border: 1px solid {_INPUT_BORDER}; border-radius: 6px; "
    f"padding: 6px 8px; background: {_BG_INPUT}; color: {_TEXT_PRIMARY}; font-size: 13px;"
)

PREVIEW_RENDERED_STYLE = (
    f"background: {_BG_INPUT}; border: 1px solid {_INPUT_BORDER}; border-radius: 6px; "
    f"color: {_TEXT_PRIMARY}; font-size: 13px;"
)

FIELD_ERROR_STYLE = (
    f"color: {'#FBBF24' if IS_DARK else '#92400E'}; font-size: 12px; padding: 4px 8px; "
    f"background: {'#453D2A' if IS_DARK else '#FEF3C7'}; "
    f"border-left: 3px solid #F59E0B; border-radius: 2px;"
)

CLICKABLE_ARROW_STYLE = f"font-size: 11px; color: {_TEXT_MUTED}; background: transparent; border: none;"

RESIZE_HANDLE_COLOR = "#555" if IS_DARK else "#C4CAD3"

# ---------------------------------------------------------------------------
# Filter chip style — rounded pill with clear active/inactive states
# ---------------------------------------------------------------------------

FILTER_CHIP_STYLE = f"""
    QPushButton {{
        border: 1px solid {_BORDER};
        border-radius: 14px;
        padding: 4px 14px;
        background: {_BTN_BG};
        color: {_TEXT_MUTED};
        font-weight: 500;
        font-size: 12px;
        outline: none;
    }}
    QPushButton:hover {{
        border-color: {_ACCENT};
        background: {"#2A2D3A" if IS_DARK else "#EEF2FD"};
        color: {_TEXT_PRIMARY};
    }}
    QPushButton:checked {{
        background: {_ACCENT};
        color: white;
        border-color: {_ACCENT};
        font-weight: 600;
    }}
    QPushButton:checked:hover {{
        background: {_ACCENT_HOVER};
        border-color: {_ACCENT_HOVER};
    }}
"""

# ---------------------------------------------------------------------------
# Regen toggle button — amber when marked for batch regeneration
# ---------------------------------------------------------------------------

REGEN_TOGGLE_STYLE = f"""
    QPushButton {{
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 3px 10px;
        background: {_BTN_BG};
        color: {_TEXT_MUTED};
        font-size: 12px;
        outline: none;
    }}
    QPushButton:hover {{
        border-color: #F59E0B;
        background: {"#453D2A" if IS_DARK else "#FFFBEB"};
        color: {"#FCD34D" if IS_DARK else "#92400E"};
    }}
    QPushButton:checked {{
        background: #F59E0B;
        color: white;
        border-color: #D97706;
    }}
    QPushButton:checked:hover {{
        background: #D97706;
        border-color: #B45309;
    }}
"""

# ---------------------------------------------------------------------------
# Editor floating toolbar style
# ---------------------------------------------------------------------------

EDITOR_TOOLBAR_STYLE = f"""
    .ai-filler-toolbar {{
        position: absolute;
        top: 8px;
        right: 25px;
        display: flex;
        background: {"#2D2E31" if IS_DARK else "white"};
        border: 1px solid {_BORDER};
        border-radius: 20px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
        z-index: 1000;
        overflow: hidden;
        opacity: 0.85;
        transition: opacity 0.2s, transform 0.2s, box-shadow 0.2s;
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
    }}
    .ai-filler-toolbar:hover {{
        opacity: 1;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }}
    .ai-filler-btn {{
        background: transparent;
        border: none;
        padding: 7px 12px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        color: {_TEXT_MUTED};
        transition: background 0.15s, color 0.15s;
        min-width: 38px;
        outline: none;
    }}
    .ai-filler-btn:hover {{
        background: {_BTN_HOVER};
        color: {_ACCENT};
    }}
    .ai-filler-btn:active {{
        background: {_BTN_PRESSED};
    }}
    .ai-filler-btn svg {{
        width: 16px;
        height: 16px;
        stroke: currentColor;
        stroke-width: 2.2px;
        pointer-events: none;
    }}
    .ai-filler-btn:not(:last-child) {{
        border-right: 1px solid {_BORDER};
    }}
    
    /* Hide the original toolbar buttons */
    button[cmd^="ai_filler_"] {{
        display: none !important;
    }}
"""
