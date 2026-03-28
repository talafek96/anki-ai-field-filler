"""Shared stylesheet constants for a modern, polished UI."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

_ACCENT = "#5B8DEF"
_ACCENT_HOVER = "#4A7DE0"
_ACCENT_PRESSED = "#3D6DD4"
_BG_CARD = "#FAFBFC"
_BORDER = "#DDE1E6"
_BORDER_FOCUS = "#5B8DEF"
_TEXT_MUTED = "#6B7280"
_TEXT_PRIMARY = "#1F2937"

# ---------------------------------------------------------------------------
# Reusable stylesheet fragments
# ---------------------------------------------------------------------------

GLOBAL_STYLE = f"""
    QDialog {{
        background-color: #F5F6F8;
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
        background: white;
        selection-background-color: {_ACCENT};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{
        border-color: {_BORDER_FOCUS};
    }}

    QComboBox {{
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 5px 8px;
        background: white;
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
        background: white;
        color: {_TEXT_PRIMARY};
        font-weight: 500;
        outline: none;
    }}
    QPushButton:hover {{
        background: #F0F2F5;
        border-color: #C4CAD3;
    }}
    QPushButton:pressed {{
        background: #E5E8EC;
    }}
    QPushButton:focus {{
        outline: none;
        background: white;
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
        background: #F0F2F5;
        color: #A0A7B3;
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
        background: white;
    }}
    QCheckBox::indicator:checked {{
        background: {_ACCENT};
        border-color: {_ACCENT};
    }}

    QTabWidget::pane {{
        border: 1px solid {_BORDER};
        border-radius: 8px;
        background: #F5F6F8;
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
        background: #F5F6F8;
        color: {_ACCENT};
        border-color: {_BORDER};
        font-weight: 600;
    }}
    QTabBar::tab:hover:!selected {{
        color: {_TEXT_PRIMARY};
        background: #EDEEF1;
    }}

    QListWidget {{
        border: 1px solid {_BORDER};
        border-radius: 6px;
        background: white;
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
        background: #D1D5DB;
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #9CA3AF;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QToolButton {{
        border: 1px solid {_BORDER};
        border-radius: 6px;
        background: white;
        outline: none;
    }}
    QToolButton:hover {{
        background: #F0F2F5;
        border-color: #C4CAD3;
    }}
    QToolButton:pressed {{
        background: #E5E8EC;
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
# Filter chip style — rounded pill with clear active/inactive states
# ---------------------------------------------------------------------------

FILTER_CHIP_STYLE = f"""
    QPushButton {{
        border: 1px solid {_BORDER};
        border-radius: 14px;
        padding: 4px 14px;
        background: white;
        color: {_TEXT_MUTED};
        font-weight: 500;
        font-size: 12px;
        outline: none;
    }}
    QPushButton:hover {{
        border-color: {_ACCENT};
        background: #EEF2FD;
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
        background: white;
        color: {_TEXT_MUTED};
        font-size: 12px;
        outline: none;
    }}
    QPushButton:hover {{
        border-color: #F59E0B;
        background: #FFFBEB;
        color: #92400E;
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
