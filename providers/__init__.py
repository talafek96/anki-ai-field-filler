"""AI provider factory and public API."""

from __future__ import annotations

from typing import Tuple

from ..config_manager import ProviderConfig
from .base import ImageProvider, ProviderError, TextProvider, TTSProvider


def create_text_provider(config: ProviderConfig) -> TextProvider:
    """Create a text provider from config."""
    if config.provider_type == "openai":
        from .openai_provider import OpenAITextProvider

        return OpenAITextProvider(config)
    elif config.provider_type == "anthropic":
        from .anthropic_provider import AnthropicTextProvider

        return AnthropicTextProvider(config)
    elif config.provider_type == "google":
        from .google_provider import GoogleTextProvider

        return GoogleTextProvider(config)
    raise ProviderError(f"Unknown text provider: {config.provider_type}")


def create_tts_provider(config: ProviderConfig) -> TTSProvider:
    """Create a TTS provider from config. Currently only OpenAI is supported."""
    if config.provider_type == "openai":
        from .openai_provider import OpenAITTSProvider

        return OpenAITTSProvider(config)
    raise ProviderError(f"No TTS support for provider: {config.provider_type}")


def create_image_provider(config: ProviderConfig) -> ImageProvider:
    """Create an image provider from config. Currently only OpenAI is supported."""
    if config.provider_type == "openai":
        from .openai_provider import OpenAIImageProvider

        return OpenAIImageProvider(config)
    raise ProviderError(f"No image support for provider: {config.provider_type}")


def test_provider_connection(config: ProviderConfig) -> Tuple[bool, str]:
    """Test connection to a provider. Returns (success, message)."""
    try:
        provider = create_text_provider(config)
        provider.generate(
            "Reply with exactly the word OK and nothing else.",
            "Test connection.",
        )
        return True, "Connection successful!"
    except ProviderError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"
