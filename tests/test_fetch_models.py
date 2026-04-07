"""Tests for fetch_available_models, test_provider_connection, and model fetching."""

from __future__ import annotations

import json
import urllib.error
from io import BytesIO

from src.core.config import ProviderConfig
from src.core.factory import (
    fetch_available_models,
)
from src.core.factory import (
    test_provider_connection as _test_provider_connection,
)

# ---------------------------------------------------------------------------
# fetch_available_models
# ---------------------------------------------------------------------------


class TestFetchOpenAIModels:
    def test_fetch_text_models(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {
                "data": [
                    {"id": "gpt-4o"},
                    {"id": "gpt-5"},
                    {"id": "tts-1"},
                    {"id": "dall-e-3"},
                    {"id": "whisper-1"},
                ]
            }
        ).encode("utf-8")
        cfg = ProviderConfig(provider_type="openai", api_url="https://api.test/v1", api_key="k")
        result = fetch_available_models(cfg, "text")
        assert result == ["gpt-4o", "gpt-5"]

    def test_fetch_tts_models(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {
                "data": [
                    {"id": "gpt-4o"},
                    {"id": "tts-1"},
                    {"id": "gpt-4o-mini-tts"},
                ]
            }
        ).encode("utf-8")
        cfg = ProviderConfig(provider_type="openai", api_url="https://api.test/v1", api_key="k")
        result = fetch_available_models(cfg, "tts")
        assert result == ["gpt-4o-mini-tts", "tts-1"]

    def test_fetch_image_models(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {
                "data": [
                    {"id": "gpt-4o"},
                    {"id": "dall-e-3"},
                    {"id": "gpt-image-1"},
                ]
            }
        ).encode("utf-8")
        cfg = ProviderConfig(provider_type="openai", api_url="https://api.test/v1", api_key="k")
        result = fetch_available_models(cfg, "image")
        assert result == ["dall-e-3", "gpt-image-1"]


class TestFetchAnthropicModels:
    def test_fetch_models(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {
                "data": [
                    {"id": "claude-sonnet-4-20250514"},
                    {"id": "claude-3-haiku-20240307"},
                ]
            }
        ).encode("utf-8")
        cfg = ProviderConfig(provider_type="anthropic", api_url="https://api.test/v1", api_key="k")
        result = fetch_available_models(cfg, "text")
        assert result == ["claude-3-haiku-20240307", "claude-sonnet-4-20250514"]


class TestFetchGoogleModels:
    def test_fetch_text_models(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {
                "models": [
                    {
                        "name": "models/gemini-2.5-flash",
                        "description": "Fast model",
                        "displayName": "Gemini 2.5 Flash",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-2.5-flash-image",
                        "description": "Native image generation",
                        "displayName": "Gemini 2.5 Flash Image",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/text-embedding-004",
                        "description": "Embedding model",
                        "displayName": "Text Embedding",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                ]
            }
        ).encode("utf-8")
        cfg = ProviderConfig(provider_type="google", api_url="https://api.test/v1beta", api_key="k")
        result = fetch_available_models(cfg, "text")
        assert result == ["gemini-2.5-flash"]

    def test_fetch_image_models(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps(
            {
                "models": [
                    {
                        "name": "models/gemini-2.5-flash",
                        "description": "Fast model",
                        "displayName": "Gemini 2.5 Flash",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-2.5-flash-image",
                        "description": "Native image generation and editing",
                        "displayName": "Gemini 2.5 Flash Image",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                ]
            }
        ).encode("utf-8")
        cfg = ProviderConfig(provider_type="google", api_url="https://api.test/v1beta", api_key="k")
        result = fetch_available_models(cfg, "image")
        assert result == ["gemini-2.5-flash-image"]


class TestFetchUnknownProvider:
    def test_returns_empty_list(self) -> None:
        cfg = ProviderConfig(provider_type="unknown", api_url="https://test", api_key="k")
        assert fetch_available_models(cfg, "text") == []


# ---------------------------------------------------------------------------
# test_provider_connection
# ---------------------------------------------------------------------------


class TestTestProviderConnection:
    def test_success(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode(
            "utf-8"
        )
        cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://api.test/v1",
            api_key="k",
            text_model="gpt-4o",
        )
        ok, msg = _test_provider_connection(cfg)
        assert ok is True
        assert "successful" in msg.lower()

    def test_provider_error(self, mock_urlopen) -> None:
        error = urllib.error.HTTPError(
            "https://api.test",
            401,
            "Unauthorized",
            {},
            BytesIO(b"bad key"),
        )
        mock_urlopen.side_effect = error
        cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://api.test/v1",
            api_key="bad",
            text_model="gpt-4o",
        )
        ok, msg = _test_provider_connection(cfg)
        assert ok is False
        assert "401" in msg
