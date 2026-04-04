"""Install aqt mocks before test files import addon submodules.

This conftest runs after ai_field_filler/__init__.py (which handles
missing aqt gracefully) but before test files are imported. The mocks
installed here allow submodules like filler.py and providers/
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
        "QVBoxLayout", "QHBoxLayout", "QFormLayout", "QGridLayout", "QGroupBox",
        "QTabWidget", "QScrollArea", "QFrame", "QPlainTextEdit", "QTextEdit",
        "QTextBrowser", "QStackedWidget", "QListWidget", "QListWidgetItem",
        "QDialogButtonBox", "QSizePolicy", "QSize", "QStyle", "QApplication",
        "QProgressBar", "QRadioButton", "QStandardItem", "QStandardItemModel",
        "QStyleOptionComboBox", "QStylePainter", "QPen", "QColor", "QPixmap",
        "QIcon", "QPainter", "QSvgRenderer", "QPropertyAnimation", "QTimer",
        "QSizeGrip", "QSplitter", "QUrl", "Qt", "qconnect", "pyqtSignal",
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

    aqt_browser = types.ModuleType("aqt.browser")
    aqt_browser.Browser = MagicMock()

    aqt_sound = types.ModuleType("aqt.sound")
    aqt_sound.av_player = MagicMock()

    anki = types.ModuleType("anki")
    anki_sound = types.ModuleType("anki.sound")
    anki_sound.SoundOrVideoTag = MagicMock()

    aqt_theme = types.ModuleType("aqt.theme")
    aqt_theme.theme_manager = MagicMock()
    aqt_theme.theme_manager.night_mode = False

    sys.modules["aqt"] = aqt
    sys.modules["aqt.qt"] = aqt_qt
    sys.modules["aqt.utils"] = aqt_utils
    sys.modules["aqt.editor"] = aqt_editor
    sys.modules["aqt.webview"] = aqt_webview
    sys.modules["aqt.browser"] = aqt_browser
    sys.modules["aqt.gui_hooks"] = aqt.gui_hooks
    sys.modules["aqt.sound"] = aqt_sound
    sys.modules["aqt.theme"] = aqt_theme
    sys.modules["anki"] = anki
    sys.modules["anki.sound"] = anki_sound


_install_aqt_mocks()

# These imports MUST come after aqt mocks are installed.
from src.core.config import Config, ProviderConfig  # noqa: E402
from src.core.filler import BatchFiller, Filler  # noqa: E402


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
def mock_mw():
    """Fixture that provides a mocked ``mw`` and handles cleanup."""
    import aqt
    with patch("src.core.media.mw", aqt.mw), \
         patch("src.core.filler.mw", aqt.mw), \
         patch("src.integration.mw", aqt.mw):
        aqt.mw.col.media.write_data = MagicMock()
        yield aqt.mw


@pytest.fixture()
def mock_urlopen():
    """Fixture to mock ``urllib.request.urlopen``."""

    def _make_mock(response_data: str | bytes):
        mock_resp = MagicMock()
        if isinstance(response_data, str):
            response_data = response_data.encode("utf-8")
        mock_resp.read.return_value = response_data
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("src.core.network.urllib.request.urlopen") as m:
        default_mock = _make_mock(b"{}")
        m.return_value = default_mock
        m.side_effect = lambda *args, **kwargs: _make_mock(b"{}")
        yield m


@pytest.fixture()
def mock_note():
    """Fixture to create a mock Anki note."""

    def _make(nid: int, fields: dict[str, str], note_type: str = "Basic"):
        note = MagicMock()
        note.id = nid
        note.note_type.return_value = {"name": note_type}
        note.keys.return_value = list(fields.keys())
        note.__getitem__.side_effect = fields.__getitem__
        note.__setitem__.side_effect = fields.__setitem__
        note.__contains__.side_effect = fields.__contains__
        return note, fields

    return _make


@pytest.fixture()
def mock_config():
    """Fixture to mock Anki's addon configuration manager."""
    import copy

    def _make(config_data: dict | None = None, defaults: dict | None = None, raw_config: dict | None = None):
        Config._instance = None
        # Support raw_config as an alias for config_data
        if config_data is None and raw_config is not None:
            config_data = raw_config
        cfg = copy.deepcopy(config_data) if config_data is not None else {}
        dfl = copy.deepcopy(defaults if defaults is not None else cfg)

        import aqt
        mock_mgr = MagicMock()
        mock_mgr.addonFromModule.return_value = "ai_field_filler"
        mock_mgr.getConfig.return_value = cfg
        mock_mgr.addonConfigDefaults.return_value = dfl
        aqt.mw.addonManager = mock_mgr

        return Config(), mock_mgr

    return _make


@pytest.fixture()
def filler(mock_config):
    """Fixture to create a Filler instance with a mocked config."""
    cm, _ = mock_config({
        "providers": {
            "openai": {
                "provider_type": "openai",
                "api_url": "https://fake.test/v1",
                "api_key": "test-key",
                "text_model": "gpt-4o",
                "max_tokens": 4096,
            }
        },
        "active_providers": {"text": "openai"}
    })
    f = Filler()
    f._config = MagicMock(spec=Config)
    # Forward mocked calls to the real mock config where needed
    f._config.get_active_text_provider.return_value = cm.get_active_text_provider()
    f._config.get_field_instructions.side_effect = cm.get_field_instructions
    return f


@pytest.fixture()
def batch_filler(mock_config):
    """Fixture to create a BatchFiller instance with a mocked config."""
    cm, _ = mock_config({
        "providers": {
            "openai": {
                "provider_type": "openai",
                "api_url": "https://fake.test/v1",
                "api_key": "test-key",
                "text_model": "gpt-4o",
                "max_tokens": 4096,
            }
        },
        "active_providers": {"text": "openai"}
    })
    f = BatchFiller()
    mock_cfg = MagicMock(spec=Config)
    f._config = mock_cfg
    f._filler._config = mock_cfg
    
    # Pre-configure common mock returns
    f._config.get_active_text_provider.return_value = cm.get_active_text_provider()
    f._config.get_field_instructions.side_effect = cm.get_field_instructions
    
    return f
