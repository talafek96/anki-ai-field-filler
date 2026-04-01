"""UI components for AI Field Filler addon."""

from __future__ import annotations

from aqt.qt import QCheckBox, QComboBox

from ..core.config_manager import FIELD_TYPES

_TYPE_TOOLTIP = (
    "auto: let the AI decide the best type\n"
    "text: plain text or HTML content\n"
    "audio: generate TTS audio file\n"
    "image: generate an image\n"
    "rich: mixed content with text, images, and audio"
)

_AUTO_FILL_TOOLTIP = "When checked, this field will be included when using 'Fill All Blank Fields'."


def create_field_type_combo() -> QComboBox:
    """Create a Content Type combo box populated with :data:`FIELD_TYPES`."""
    combo = QComboBox()
    combo.setToolTip(_TYPE_TOOLTIP)
    for ft in FIELD_TYPES:
        combo.addItem(ft.capitalize(), ft)
    return combo


def create_auto_fill_checkbox() -> QCheckBox:
    """Create an 'Include in auto-fill' checkbox."""
    cb = QCheckBox("Include in auto-fill")
    cb.setToolTip(_AUTO_FILL_TOOLTIP)
    return cb
