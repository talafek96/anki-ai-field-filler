"""Install aqt mocks before test files import addon submodules.

This conftest runs after ai_field_filler/__init__.py (which handles
missing aqt gracefully) but before test files are imported. The mocks
installed here allow submodules like field_filler.py and providers/
to be imported without a real Anki installation.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


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
