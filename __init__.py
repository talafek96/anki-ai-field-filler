"""AI Filler — Anki addon for AI-powered note field completion.

Uses LLM-based AI to intelligently auto-fill blank note fields, taking into
account already-filled fields, configurable per-field instructions, and
optional user prompts. Supports text, audio (TTS), and image generation.
"""

import sys

try:
    from aqt import mw
except ImportError:
    mw = None  # Running outside Anki (e.g. pytest)


def start_addon() -> None:
    """Initialize the addon: register hooks, menus, and config actions."""
    from aqt.qt import QAction, qconnect
    from .src.core.config import Config
    from .src.ui.config.dialog import SettingsDialog
    from .src.ui.integration import BrowserIntegration, EditorIntegration

    # Initialize sub-integrations
    EditorIntegration.init()
    BrowserIntegration.init()

    # Tools menu item
    settings_action = QAction("Anki AI Filler", mw)
    qconnect(settings_action.triggered, lambda: SettingsDialog(mw).exec())
    mw.form.menuTools.addAction(settings_action)

    # Addon manager integration (config button in Anki's addon list)
    addon_name = mw.addonManager.addonFromModule(__name__)
    config = Config()

    mw.addonManager.setConfigAction(addon_name, lambda: SettingsDialog(mw).exec())
    mw.addonManager.setConfigUpdatedAction(
        addon_name, config.update_from_addon_manager
    )


if mw and "pytest" not in sys.modules:
    start_addon()
