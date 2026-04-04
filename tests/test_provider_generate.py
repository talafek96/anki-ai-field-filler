"""Tests for provider generate/synthesize/generate_image methods with mocked HTTP."""

from __future__ import annotations

import base64
import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from src.core.config import ProviderConfig
from src.api.anthropic import AnthropicTextProvider
from src.core.interfaces import ProviderError
from src.api.google import (
    GoogleImageProvider,
    GoogleTextProvider,
    GoogleTTSProvider,
)
from src.api.openai import (
    OpenAIImageProvider,
    OpenAITextProvider,
    OpenAITTSProvider,
)

_OPENAI_CFG = ProviderConfig(
    provider_type="openai",
    api_url="https://api.openai.com/v1",
    api_key="sk-test",
    text_model="gpt-4o",
    max_tokens=4096,
    tts_model="tts-1",
    tts_voice="alloy",
    image_model="dall-e-3",
)

_ANTHROPIC_CFG = ProviderConfig(
    provider_type="anthropic",
    api_url="https://api.anthropic.com/v1",
    api_key="ant-key",
    text_model="claude-sonnet-4-20250514",
    max_tokens=4096,
)

_GOOGLE_CFG = ProviderConfig(
    provider_type="google",
    api_url="https://generativelanguage.googleapis.com/v1beta",
    api_key="goog-key",
    text_model="gemini-2.5-flash",
    max_tokens=4096,
    tts_model="gemini-2.5-flash-preview-tts",
    tts_voice="Kore",
    image_model="gemini-2.5-flash-image",
)


# ---------------------------------------------------------------------------
# OpenAI providers
# ---------------------------------------------------------------------------


class TestOpenAITextProvider:
    def test_generate(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "Hello world"}}]}
        ).encode("utf-8")
        provider = OpenAITextProvider(_OPENAI_CFG)
        result = provider.generate("system prompt", "user prompt")
        assert result == "Hello world"

    def test_generate_fallback_to_max_tokens(self, mock_urlopen) -> None:
        """First call fails with max_completion_tokens unsupported, retry succeeds."""
        error = urllib.error.HTTPError(
            "https://api.openai.com",
            400,
            "Bad Request",
            {},
            BytesIO(b'{"error": {"message": "max_completion_tokens is unsupported"}}'),
        )
        success_mock = MagicMock()
        success_mock.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "OK"}}]}
        ).encode("utf-8")
        success_mock.__enter__.return_value = success_mock

        mock_urlopen.side_effect = [error, success_mock]
        provider = OpenAITextProvider(_OPENAI_CFG)
        result = provider.generate("sys", "usr")
        assert result == "OK"
        assert mock_urlopen.call_count == 2

    def test_generate_non_fallback_error_propagates(self, mock_urlopen) -> None:
        error = urllib.error.HTTPError(
            "https://api.openai.com",
            401,
            "Unauthorized",
            {},
            BytesIO(b'{"error": {"message": "Invalid API key"}}'),
        )
        mock_urlopen.side_effect = error
        provider = OpenAITextProvider(_OPENAI_CFG)
        with pytest.raises(ProviderError, match="401"):
            provider.generate("sys", "usr")


class TestOpenAITTSProvider:
    def test_synthesize(self, mock_urlopen) -> None:
        audio_bytes = b"\xff\xfb\x90\x00audio"
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = audio_bytes
        provider = OpenAITTSProvider(_OPENAI_CFG)
        result = provider.synthesize("Hello world")
        assert result == audio_bytes


class TestOpenAIImageProvider:
    def test_generate_image_dalle(self, mock_urlopen) -> None:
        img_data = b"PNG-image-bytes"
        b64 = base64.b64encode(img_data).decode()
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {"data": [{"b64_json": b64}]}
        ).encode("utf-8")
        cfg = ProviderConfig(**{**_OPENAI_CFG.__dict__, "image_model": "dall-e-3"})
        provider = OpenAIImageProvider(cfg)
        result = provider.generate_image("a cat")
        assert result == img_data
        # DALL-E should use response_format
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data)
        assert "response_format" in body
        assert "output_format" not in body

    def test_generate_image_gpt_image(self, mock_urlopen) -> None:
        img_data = b"PNG-image-bytes"
        b64 = base64.b64encode(img_data).decode()
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {"data": [{"b64_json": b64}]}
        ).encode("utf-8")
        cfg = ProviderConfig(**{**_OPENAI_CFG.__dict__, "image_model": "gpt-image-1"})
        provider = OpenAIImageProvider(cfg)
        result = provider.generate_image("a dog")
        assert result == img_data
        # gpt-image should use output_format, not response_format
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data)
        assert "output_format" in body
        assert body["output_format"] == "png"
        assert "response_format" not in body

    def test_generate_image_fallback_response_format(self, mock_urlopen) -> None:
        """If the API rejects response_format, retry with output_format."""
        img_data = b"PNG-image-bytes"
        b64 = base64.b64encode(img_data).decode()
        error = urllib.error.HTTPError(
            "https://api.openai.com",
            400,
            "Bad Request",
            {},
            BytesIO(b'{"error": {"message": "Unknown parameter: \'response_format\'."}}'),
        )
        success_mock = MagicMock()
        success_mock.read.return_value = json.dumps(
            {"data": [{"b64_json": b64}]}
        ).encode("utf-8")
        success_mock.__enter__.return_value = success_mock

        mock_urlopen.side_effect = [error, success_mock]
        cfg = ProviderConfig(**{**_OPENAI_CFG.__dict__, "image_model": "dall-e-3"})
        provider = OpenAIImageProvider(cfg)
        result = provider.generate_image("a cat")
        assert result == img_data
        assert mock_urlopen.call_count == 2
        # Retry should use output_format instead
        retry_req = mock_urlopen.call_args[0][0]
        retry_body = json.loads(retry_req.data)
        assert "output_format" in retry_body
        assert retry_body["output_format"] == "png"
        assert "response_format" not in retry_body


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------


class TestAnthropicTextProvider:
    def test_generate(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {"content": [{"text": "Claude says hi"}]}
        ).encode("utf-8")
        provider = AnthropicTextProvider(_ANTHROPIC_CFG)
        result = provider.generate("system", "user")
        assert result == "Claude says hi"

    def test_generate_bad_format(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = b'{"unexpected": true}'
        provider = AnthropicTextProvider(_ANTHROPIC_CFG)
        with pytest.raises(ProviderError, match="Unexpected Anthropic"):
            provider.generate("system", "user")


# ---------------------------------------------------------------------------
# Google providers
# ---------------------------------------------------------------------------


class TestGoogleTextProvider:
    def test_generate(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": "Gemini says hi"}]}}]}
        ).encode("utf-8")
        provider = GoogleTextProvider(_GOOGLE_CFG)
        result = provider.generate("system", "user")
        assert result == "Gemini says hi"

    def test_generate_no_candidates(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = b'{"candidates": []}'
        provider = GoogleTextProvider(_GOOGLE_CFG)
        with pytest.raises(ProviderError, match="returned no candidates"):
            provider.generate("system", "user")

    def test_generate_prompt_blocked(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {"promptFeedback": {"blockReason": "SAFETY"}}
        ).encode("utf-8")
        provider = GoogleTextProvider(_GOOGLE_CFG)
        with pytest.raises(ProviderError, match="prompt blocked: SAFETY"):
            provider.generate("system", "user")

    def test_generate_no_content(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {"candidates": [{"finishReason": "SAFETY"}]}
        ).encode("utf-8")
        provider = GoogleTextProvider(_GOOGLE_CFG)
        with pytest.raises(ProviderError, match="finishReason: SAFETY"):
            provider.generate("system", "user")

    def test_generate_empty_text(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": ""}]}}]}
        ).encode("utf-8")
        provider = GoogleTextProvider(_GOOGLE_CFG)
        with pytest.raises(ProviderError, match="empty text"):
            provider.generate("system", "user")


class TestGoogleImageProvider:
    def test_generate_image(self, mock_urlopen) -> None:
        img_data = b"PNG-image"
        b64 = base64.b64encode(img_data).decode()
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "here is the image"},
                                {"inlineData": {"data": b64, "mimeType": "image/png"}},
                            ]
                        }
                    }
                ]
            }
        ).encode("utf-8")
        provider = GoogleImageProvider(_GOOGLE_CFG)
        result = provider.generate_image("a dog")
        assert result == img_data

    def test_generate_image_no_data(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": "sorry no image"}]}}]}
        ).encode("utf-8")
        provider = GoogleImageProvider(_GOOGLE_CFG)
        with pytest.raises(ProviderError, match="No image data"):
            provider.generate_image("a dog")


class TestGoogleTTSProvider:
    def test_synthesize(self, mock_urlopen) -> None:
        audio = b"wav-audio-data"
        b64 = base64.b64encode(audio).decode()
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"inlineData": {"data": b64, "mimeType": "audio/wav"}}]
                        }
                    }
                ]
            }
        ).encode("utf-8")
        provider = GoogleTTSProvider(_GOOGLE_CFG)
        result = provider.synthesize("Hello")
        assert result == audio

    def test_synthesize_no_audio(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": "no audio"}]}}]}
        ).encode("utf-8")
        provider = GoogleTTSProvider(_GOOGLE_CFG)
        with pytest.raises(ProviderError, match="No audio data"):
            provider.synthesize("Hello")
