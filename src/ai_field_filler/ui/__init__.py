"""UI components for AI Field Filler addon."""

from __future__ import annotations

from aqt.qt import QAbstractSpinBox, QCheckBox, QComboBox, QEvent, QObject, QWidget

from ..config.config_manager import FIELD_TYPES

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


class _WheelGuard(QObject):
    """Event filter that swallows wheel events.

    Qt's default is for the mouse wheel to change a combo box's selection
    and a spin box's value.  In a scrollable dialog that means scrolling
    past one silently edits a setting — here, silently switching the model
    or provider.  Scrolling the dialog must never change a value, so the
    event is dropped rather than forwarded to the parent scroll area,
    which would otherwise scroll twice.
    """

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event is not None and event.type() == QEvent.Type.Wheel:
            event.ignore()
            return True
        return False


# Parented to nothing and kept alive for the process: the filter is
# stateless, so one shared instance serves every dialog.
_WHEEL_GUARD = _WheelGuard()


def install_wheel_guard(root: QWidget) -> None:
    """Stop the wheel from changing combo/spin values inside *root*.

    Call once after a dialog's widgets are built; it walks the whole
    subtree, so nested tabs and group boxes are covered.
    """
    for widget in root.findChildren(QComboBox):
        widget.installEventFilter(_WHEEL_GUARD)
    for widget in root.findChildren(QAbstractSpinBox):
        widget.installEventFilter(_WHEEL_GUARD)
