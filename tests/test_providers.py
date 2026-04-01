"""Tests for provider factory functions and model classifiers."""

from __future__ import annotations

import pytest

from src.api import (
    _classify_google_model,
    _classify_openai_model,
    create_image_provider,
    create_text_provider,
    create_tts_provider,
)
from src.api.base import (
    ImageProvider,
    ProviderError,
    TextProvider,
    TTSProvider,
)


class TestProviderFactory:
    def test_create_openai_text(self, provider_config) -> None:
        provider = create_text_provider(provider_config("openai"))
        assert isinstance(provider, TextProvider)

    def test_create_anthropic_text(self, provider_config) -> None:
        provider = create_text_provider(provider_config("anthropic"))
        assert isinstance(provider, TextProvider)

    def test_create_google_text(self, provider_config) -> None:
        provider = create_text_provider(provider_config("google"))
        assert isinstance(provider, TextProvider)

    def test_create_unknown_text_raises(self, provider_config) -> None:
        with pytest.raises(ProviderError, match="Unknown text provider"):
            create_text_provider(provider_config("nonexistent"))

    def test_create_openai_tts(self, provider_config) -> None:
        provider = create_tts_provider(provider_config("openai"))
        assert isinstance(provider, TTSProvider)

    def test_create_google_tts(self, provider_config) -> None:
        provider = create_tts_provider(provider_config("google"))
        assert isinstance(provider, TTSProvider)

    def test_create_anthropic_tts_raises(self, provider_config) -> None:
        with pytest.raises(ProviderError, match="No TTS support"):
            create_tts_provider(provider_config("anthropic"))

    def test_create_openai_image(self, provider_config) -> None:
        provider = create_image_provider(provider_config("openai"))
        assert isinstance(provider, ImageProvider)

    def test_create_google_image(self, provider_config) -> None:
        provider = create_image_provider(provider_config("google"))
        assert isinstance(provider, ImageProvider)

    def test_create_anthropic_image_raises(self, provider_config) -> None:
        with pytest.raises(ProviderError, match="No image support"):
            create_image_provider(provider_config("anthropic"))


class TestClassifyOpenAI:
    """Verify OpenAI model ID classification."""

    @pytest.mark.parametrize(
        "model_id",
        [
            "gpt-5.4",
            "gpt-5-mini",
            "gpt-4o",
            "gpt-4.1",
            "o1",
            "o3-mini",
            "o4-mini",
            "chatgpt-4o-latest",
        ],
    )
    def test_text_models(self, model_id: str) -> None:
        assert _classify_openai_model(model_id) == "text"

    @pytest.mark.parametrize(
        "model_id",
        [
            "gpt-image-1.5",
            "gpt-image-1",
            "gpt-image-1-mini",
            "chatgpt-image-latest",
            "dall-e-3",
            "dall-e-2",
        ],
    )
    def test_image_models(self, model_id: str) -> None:
        assert _classify_openai_model(model_id) == "image"

    @pytest.mark.parametrize(
        "model_id",
        [
            "tts-1",
            "tts-1-hd",
            "gpt-4o-mini-tts",
        ],
    )
    def test_tts_models(self, model_id: str) -> None:
        assert _classify_openai_model(model_id) == "tts"

    @pytest.mark.parametrize(
        "model_id",
        [
            "whisper-1",
            "text-embedding-3-large",
            "omni-moderation-latest",
            "gpt-4o-realtime-preview",
            "gpt-4o-audio-preview",
            "gpt-4o-transcribe",
            "sora-2",
        ],
    )
    def test_skipped_models(self, model_id: str) -> None:
        assert _classify_openai_model(model_id) is None


class TestClassifyGoogle:
    """Verify Google model classification using metadata."""

    def _model(
        self, name: str, desc: str = "", display: str = "", methods: list | None = None
    ) -> tuple[dict, list]:
        m = {"name": f"models/{name}", "description": desc, "displayName": display}
        return m, methods or ["generateContent"]

    def test_image_model_by_description(self) -> None:
        m, methods = self._model(
            "gemini-2.5-flash-image",
            desc="Native image generation and editing",
        )
        assert _classify_google_model(m, methods) == "image"

    def test_image_model_nano_banana(self) -> None:
        m, methods = self._model(
            "gemini-3.1-flash-image-preview",
            desc="Nano Banana 2 provides high-quality image generation",
        )
        assert _classify_google_model(m, methods) == "image"

    def test_imagen_model(self) -> None:
        m, methods = self._model(
            "imagen-4-preview",
            display="Imagen 4",
        )
        assert _classify_google_model(m, methods) == "image"

    def test_tts_model(self) -> None:
        m, methods = self._model(
            "gemini-2.5-flash-preview-tts",
            desc="Text-to-speech audio generation",
        )
        assert _classify_google_model(m, methods) == "tts"

    def test_text_model(self) -> None:
        m, methods = self._model(
            "gemini-2.5-flash",
            desc="Fast and versatile model for everyday tasks",
        )
        assert _classify_google_model(m, methods) == "text"

    def test_embedding_model_skipped(self) -> None:
        m, methods = self._model(
            "text-embedding-004",
            desc="Embedding model",
        )
        assert _classify_google_model(m, ["embedContent"]) is None
