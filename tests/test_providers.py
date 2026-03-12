"""Tests for provider factory functions."""

from __future__ import annotations

import pytest

from ai_field_filler.config_manager import ProviderConfig
from ai_field_filler.providers import (
    create_image_provider,
    create_text_provider,
    create_tts_provider,
)
from ai_field_filler.providers.base import (
    ImageProvider,
    ProviderError,
    TextProvider,
    TTSProvider,
)


class TestProviderFactory:
    def _config(self, ptype: str) -> ProviderConfig:
        return ProviderConfig(
            provider_type=ptype,
            api_url="https://fake.test",
            api_key="test-key",
            text_model="test-model",
        )

    def test_create_openai_text(self) -> None:
        provider = create_text_provider(self._config("openai"))
        assert isinstance(provider, TextProvider)

    def test_create_anthropic_text(self) -> None:
        provider = create_text_provider(self._config("anthropic"))
        assert isinstance(provider, TextProvider)

    def test_create_google_text(self) -> None:
        provider = create_text_provider(self._config("google"))
        assert isinstance(provider, TextProvider)

    def test_create_unknown_text_raises(self) -> None:
        with pytest.raises(ProviderError, match="Unknown text provider"):
            create_text_provider(self._config("nonexistent"))

    def test_create_openai_tts(self) -> None:
        provider = create_tts_provider(self._config("openai"))
        assert isinstance(provider, TTSProvider)

    def test_create_google_tts(self) -> None:
        provider = create_tts_provider(self._config("google"))
        assert isinstance(provider, TTSProvider)

    def test_create_anthropic_tts_raises(self) -> None:
        with pytest.raises(ProviderError, match="No TTS support"):
            create_tts_provider(self._config("anthropic"))

    def test_create_openai_image(self) -> None:
        provider = create_image_provider(self._config("openai"))
        assert isinstance(provider, ImageProvider)

    def test_create_google_image(self) -> None:
        provider = create_image_provider(self._config("google"))
        assert isinstance(provider, ImageProvider)

    def test_create_anthropic_image_raises(self) -> None:
        with pytest.raises(ProviderError, match="No image support"):
            create_image_provider(self._config("anthropic"))
