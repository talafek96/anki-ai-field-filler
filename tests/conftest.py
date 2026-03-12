"""Install aqt mocks before test files import addon submodules.

This conftest runs after ai_field_filler/__init__.py (which handles
missing aqt gracefully) but before test files are imported. The mocks
installed here allow submodules like field_filler.py and providers/
to be imported without a real Anki installation.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


def _install_aqt_mocks() -> None:
    """Install fake aqt/anki modules into sys.modules."""
    if "aqt" in sys.modules and not isinstance(sys.modules["aqt"], types.ModuleType):
        return  # Real aqt already loaded

    aqt = types.ModuleType("aqt")
    aqt.mw = MagicMock()
    aqt.gui_hooks = MagicMock()

    aqt_qt = types.ModuleType("aqt.qt")
    for name in [
        "QWidget", "QDialog", "QMenu", "QAction", "QComboBox", "QLineEdit",
        "QCheckBox", "QLabel", "QPushButton", "QToolButton", "QSpinBox",
        "QVBoxLayout", "QHBoxLayout", "QFormLayout", "QGroupBox",
        "QTabWidget", "QScrollArea", "QFrame", "QPlainTextEdit",
        "QListWidget", "QListWidgetItem", "QDialogButtonBox",
        "QSizePolicy", "QSize", "QStyle", "QApplication",
        "Qt", "qconnect", "pyqtSignal",
    ]:
        setattr(aqt_qt, name, MagicMock())

    aqt_utils = types.ModuleType("aqt.utils")
    aqt_utils.showInfo = MagicMock()
    aqt_utils.showWarning = MagicMock()
    aqt_utils.tooltip = MagicMock()
    aqt_utils.restoreGeom = MagicMock()
    aqt_utils.saveGeom = MagicMock()

    aqt_editor = types.ModuleType("aqt.editor")
    aqt_editor.Editor = MagicMock()
    aqt_editor.EditorWebView = MagicMock()

    aqt_webview = types.ModuleType("aqt.webview")
    aqt_webview.AnkiWebView = MagicMock()

    sys.modules["aqt"] = aqt
    sys.modules["aqt.qt"] = aqt_qt
    sys.modules["aqt.utils"] = aqt_utils
    sys.modules["aqt.editor"] = aqt_editor
    sys.modules["aqt.webview"] = aqt_webview
    sys.modules["aqt.gui_hooks"] = aqt.gui_hooks


_install_aqt_mocks()

# These imports MUST come after aqt mocks are installed.
from ai_field_filler.config_manager import ProviderConfig  # noqa: E402
from ai_field_filler.field_filler import FieldFiller  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def provider_config():
    """Create a :class:`ProviderConfig` pre-filled for testing."""

    def _make(provider_type: str = "openai", **overrides) -> ProviderConfig:
        defaults = dict(
            provider_type=provider_type,
            api_url="https://fake.test/v1",
            api_key="test-key",
            text_model="test-model",
            max_tokens=4096,
        )
        defaults.update(overrides)
        return ProviderConfig(**defaults)

    return _make


@pytest.fixture()
def filler():
    """Create a :class:`FieldFiller` without calling __init__ (skips ConfigManager)."""
    return FieldFiller.__new__(FieldFiller)


@pytest.fixture()
def mock_mw():
    """Patch ``mw`` inside the media_handler module."""
    with patch("ai_field_filler.media_handler.mw") as m:
        m.col.media.write_data = MagicMock()
        yield m
