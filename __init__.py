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
    """Initialize the addon via the src package."""
    from .src.ui.integration import start_addon as run_start
    run_start()


if mw and "pytest" not in sys.modules:
    start_addon()
