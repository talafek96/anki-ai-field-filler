"""AI Field Filler — Anki addon for AI-powered note field completion.

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
    from aqt.qt import QAction, QMenu, qconnect

    from .config.config_manager import ConfigManager
    from .hooks import browser_hooks, editor_hooks
    from .ui.dev_tools_dialog import open_dev_tools, register_dev_shortcut
    from .ui.settings_dialog import SettingsDialog

    editor_hooks.EditorIntegration.init()
    browser_hooks.BrowserIntegration.init()

    menu = QMenu("AI Field Filler", mw)
    settings_action = QAction("Settings...", menu)
    qconnect(settings_action.triggered, lambda: SettingsDialog(mw).exec())
    menu.addAction(settings_action)
    mw.form.menuTools.addMenu(menu)

    addon_name = mw.addonManager.addonFromModule(__name__)
    config = ConfigManager()

    # Developer tools: always reachable by the hidden shortcut, but only
    # listed in the menu when general.dev_mode is turned on.
    register_dev_shortcut()
    if config.get_general_settings().dev_mode:
        dev_action = QAction("\U0001f9ea Developer Tools...", menu)
        qconnect(dev_action.triggered, lambda: open_dev_tools(mw))
        menu.addAction(dev_action)

    mw.addonManager.setConfigAction(addon_name, lambda: SettingsDialog(mw).exec())
    mw.addonManager.setConfigUpdatedAction(addon_name, config.update_from_addon_manager)


if mw and "pytest" not in sys.modules:
    start_addon()
