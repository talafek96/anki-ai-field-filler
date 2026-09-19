"""Abstract base classes for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..config.config_manager import ProviderConfig


class ProviderError(Exception):
    """Raised when an AI provider encounters an error.

    ``str(e)`` is always a short, human-readable summary suitable for a
    one-line message.  *detail* optionally carries the full raw response
    body (pretty-printed when it is JSON) for the expandable "Details"
    pane of the error dialog — API errors are far easier to diagnose with
    the whole payload, but it must not be the headline.
    """

    def __init__(self, message: str, *, detail: Optional[str] = None) -> None:
        super().__init__(message)
        self.detail = detail


class TextProvider(ABC):
    """Abstract base for text generation providers."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate text from a system/user prompt pair."""
        ...


class TTSProvider(ABC):
    """Abstract base for text-to-speech providers."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config

    @abstractmethod
    def synthesize(
        self, text: str, language: str = "", voice: str = "", context: str = ""
    ) -> bytes:
        """Synthesize speech from text. Returns audio bytes.

        *context* is an optional description of the note being processed
        (note type, filled fields, etc.) so the TTS engine can choose the
        right pronunciation, intonation, and style.
        """
        ...


class ImageProvider(ABC):
    """Abstract base for image generation providers."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config

    @abstractmethod
    def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        """Generate an image from a text prompt. Returns PNG image bytes."""
        ...
