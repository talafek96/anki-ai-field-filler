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
    # Dark Mode Palette — Charcoal/Deep Black theme matching Anki's native look
    _ACCENT = "#72A1ED"  # Soft, premium blue
    _ACCENT_HOVER = "#8DB6F4"
    _ACCENT_PRESSED = "#5B8BDB"
    _BG_WINDOW = "#1C1C1C"  # Matches Anki's deep dark background
    _BG_CARD = "#2D2D2D"    # Slightly lighter for grouping
    _BG_INPUT = "#333333"   # Subtle contrast for fields
    _BORDER = "#444444"
    _BORDER_FOCUS = "#72A1ED"
    _TEXT_PRIMARY = "#E0E0E0"
    _TEXT_MUTED = "#9CA3AF"
    _BTN_BG = "#333333"
    _BTN_HOVER = "#444444"
    _BTN_PRESSED = "#2D2D2D"
    _TAB_BG = "#262626"
    _TAB_HOVER = "#333333"
else:
    # Light Mode Palette — Clean, modern grayscale with soft accents
    _ACCENT = "#4F46E5"
    _ACCENT_HOVER = "#4338CA"
    _ACCENT_PRESSED = "#3730A3"
    _BG_WINDOW = "#F3F4F6"
    _BG_CARD = "#FFFFFF"
    _BG_INPUT = "#F9FAFB"
    _BORDER = "#E5E7EB"
    _BORDER_FOCUS = "#4F46E5"
    _TEXT_PRIMARY = "#111827"
    _TEXT_MUTED = "#6B7280"
    _BTN_BG = "#FFFFFF"
    _BTN_HOVER = "#F3F4F6"
    _BTN_PRESSED = "#E5E7EB"
    _TAB_BG = "#F3F4F6"
    _TAB_HOVER = "#E5E7EB"

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
# Side Panel (AI Chat) Styles
# ---------------------------------------------------------------------------

SIDEBAR_STYLE = f"""
    QWidget#aiChatPanel {{
        background-color: {_BG_WINDOW};
        border-left: 1px solid {_BORDER};
    }}
    
    QScrollArea#aiChatScrollArea {{
        border: none;
        background-color: transparent;
    }}
    
    QLabel#aiChatHeader {{
        font-size: 16px;
        font-weight: 700;
        color: {_ACCENT};
        padding: 4px 0 8px 0;
    }}
    
    QGroupBox#aiChatFieldsGroup {{
        margin-top: 20px;
    }}
"""

# ---------------------------------------------------------------------------
# Chat interface styles
# ---------------------------------------------------------------------------

CHAT_MESSAGE_LIST_STYLE = f"""
    background-color: transparent;
    border: none;
"""

def get_chat_bubble_user_style() -> str:
    return f"""
        background-color: {_ACCENT};
        color: white;
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
        border-bottom-left-radius: 12px;
        border-bottom-right-radius: 2px;
        padding: 10px 14px;
        margin: 4px 8px;
    """

def get_chat_bubble_bot_style() -> str:
    return f"""
        background-color: {"#333" if IS_DARK else "#EDF2F4"};
        color: {_TEXT_PRIMARY};
        border-top-left-radius: 2px;
        border-top-right-radius: 12px;
        border-bottom-left-radius: 12px;
        border-bottom-right-radius: 12px;
        padding: 10px 14px;
        margin: 4px 8px;
        border: 1px solid {"#444" if IS_DARK else "#DDE2E5"};
    """

CHAT_INPUT_STYLE = f"""
    background-color: {_BG_INPUT};
    border: 1px solid {_BORDER};
    border-radius: 12px;
    padding: 8px 12px;
    font-size: 13px;
    color: {_TEXT_PRIMARY};
"""

CHAT_RECEPTION_NAME_STYLE = f"""
    color: {_TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    margin-left: 10px;
    margin-bottom: 2px;
    text-transform: uppercase;
"""

CHAT_APPLY_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {"#444" if IS_DARK else "#F3F4F6"};
        border: 1px solid {_BORDER};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
        color: {_ACCENT};
        font-weight: 600;
        margin-top: 5px;
    }}
    QPushButton:hover {{
        background-color: {_ACCENT};
        color: white;
    }}
"""
