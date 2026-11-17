"""Tests for fetch_available_models, test_provider_connection, and model fetching."""

from __future__ import annotations

import base64
import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

from ai_field_filler.config.config_manager import ProviderConfig
from ai_field_filler.providers import (
    fetch_available_models,
)
from ai_field_filler.providers import (
    test_image_connection as _test_image_connection,
)
from ai_field_filler.providers import (
    test_provider_connection as _test_provider_connection,
)
from ai_field_filler.providers import (
    test_tts_connection as _test_tts_connection,
)

_HTTP_URLOPEN = "ai_field_filler.providers.http.urllib.request.urlopen"


def _mock_urlopen(response_data: str | bytes):
    mock_resp = MagicMock()
    if isinstance(response_data, str):
        response_data = response_data.encode("utf-8")
    mock_resp.read.return_value = response_data
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# fetch_available_models
# ---------------------------------------------------------------------------


class TestFetchOpenAIModels:
    @patch(_HTTP_URLOPEN)
    def test_fetch_text_models(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(
            json.dumps(
                {
                    "data": [
                        {"id": "gpt-4o"},
                        {"id": "gpt-5"},
                        {"id": "tts-1"},
                        {"id": "dall-e-3"},
                        {"id": "whisper-1"},
                    ]
                }
            )
        )
        cfg = ProviderConfig(provider_type="openai", api_url="https://api.test/v1", api_key="k")
        result = fetch_available_models(cfg, "text")
        assert result == ["gpt-4o", "gpt-5"]

    @patch(_HTTP_URLOPEN)
    def test_fetch_tts_models(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(
            json.dumps(
                {
                    "data": [
                        {"id": "gpt-4o"},
                        {"id": "tts-1"},
                        {"id": "gpt-4o-mini-tts"},
                    ]
                }
            )
        )
        cfg = ProviderConfig(provider_type="openai", api_url="https://api.test/v1", api_key="k")
        result = fetch_available_models(cfg, "tts")
        assert result == ["gpt-4o-mini-tts", "tts-1"]

    @patch(_HTTP_URLOPEN)
    def test_fetch_image_models(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(
            json.dumps(
                {
                    "data": [
                        {"id": "gpt-4o"},
                        {"id": "dall-e-3"},
                        {"id": "gpt-image-1"},
                    ]
                }
            )
        )
        cfg = ProviderConfig(provider_type="openai", api_url="https://api.test/v1", api_key="k")
        result = fetch_available_models(cfg, "image")
        assert result == ["dall-e-3", "gpt-image-1"]


class TestFetchAnthropicModels:
    @patch(_HTTP_URLOPEN)
    def test_fetch_models(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(
            json.dumps(
                {
                    "data": [
                        {"id": "claude-sonnet-4-20250514"},
                        {"id": "claude-3-haiku-20240307"},
                    ]
                }
            )
        )
        cfg = ProviderConfig(provider_type="anthropic", api_url="https://api.test/v1", api_key="k")
        result = fetch_available_models(cfg, "text")
        assert result == ["claude-3-haiku-20240307", "claude-sonnet-4-20250514"]


class TestFetchGoogleModels:
    @patch(_HTTP_URLOPEN)
    def test_fetch_text_models(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(
            json.dumps(
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
            )
        )
        cfg = ProviderConfig(provider_type="google", api_url="https://api.test/v1beta", api_key="k")
        result = fetch_available_models(cfg, "text")
        assert result == ["gemini-2.5-flash"]

    @patch(_HTTP_URLOPEN)
    def test_fetch_image_models(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(
            json.dumps(
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
            )
        )
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
    @patch(_HTTP_URLOPEN)
    def test_success(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(
            json.dumps({"choices": [{"message": {"content": "OK"}}]})
        )
        cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://api.test/v1",
            api_key="k",
            text_model="gpt-4o",
        )
        ok, msg, _detail = _test_provider_connection(cfg)
        assert ok is True
        assert "successful" in msg.lower()

    @patch(_HTTP_URLOPEN)
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
        ok, msg, _detail = _test_provider_connection(cfg)
        assert ok is False
        assert "401" in msg


# ---------------------------------------------------------------------------
# Dedicated speech / image servers (issue #18)
# ---------------------------------------------------------------------------


def _speech_server_cfg(**extra: str) -> ProviderConfig:
    """An OpenAI config whose speech goes to a local server, already resolved."""
    return ProviderConfig(
        provider_type="openai",
        api_url="https://api.openai.com/v1",
        api_key="main-key",
        tts_model="kokoro",
        tts_api_url="http://localhost:8880/v1",
        **extra,
    ).for_capability("tts")


class TestDedicatedServerModels:
    @patch(_HTTP_URLOPEN)
    def test_lists_every_model_from_a_dedicated_server(self, mock_urlopen) -> None:
        # Self-hosted model ids carry no "tts" signal; classifying would hide them.
        mock_urlopen.return_value = _mock_urlopen(
            json.dumps({"data": [{"id": "kokoro"}, {"id": "piper-en"}]})
        )
        result = fetch_available_models(_speech_server_cfg(), "tts")
        assert result == ["kokoro", "piper-en"]
        assert mock_urlopen.call_args[0][0].full_url == "http://localhost:8880/v1/models"

    @patch(_HTTP_URLOPEN)
    def test_main_server_is_still_classified(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(
            json.dumps({"data": [{"id": "gpt-4o"}, {"id": "tts-1"}]})
        )
        cfg = ProviderConfig(provider_type="openai", api_url="https://api.test/v1", api_key="k")
        assert fetch_available_models(cfg.for_capability("tts"), "tts") == ["tts-1"]


class TestTestTTSConnection:
    @patch(_HTTP_URLOPEN)
    def test_success_hits_the_speech_server(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(b"ID3-fake-mp3-bytes")
        ok, msg, _detail = _test_tts_connection(_speech_server_cfg())
        assert ok is True
        assert msg == "Speech works."
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:8880/v1/audio/speech"
        # No speech key given, so the main key is reused.
        assert req.get_header("Authorization") == "Bearer main-key"

    @patch(_HTTP_URLOPEN)
    def test_empty_audio_fails(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(b"")
        ok, msg, _detail = _test_tts_connection(_speech_server_cfg())
        assert ok is False
        assert "no audio" in msg

    @patch(_HTTP_URLOPEN)
    def test_missing_endpoint_reports_provider_error(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://localhost:8880/v1/audio/speech", 404, "Not Found", {}, BytesIO(b"nope")
        )
        ok, msg, _detail = _test_tts_connection(_speech_server_cfg())
        assert ok is False
        assert "404" in msg


class TestTestImageConnection:
    @patch(_HTTP_URLOPEN)
    def test_success_hits_the_image_server(self, mock_urlopen) -> None:
        png = base64.b64encode(b"\x89PNG-fake").decode("ascii")
        mock_urlopen.return_value = _mock_urlopen(json.dumps({"data": [{"b64_json": png}]}))
        cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://api.openai.com/v1",
            api_key="main-key",
            image_model="gpt-image-1",
            image_api_url="http://localhost:7860/v1",
            image_api_key="image-key",
        ).for_capability("image")
        ok, msg, _detail = _test_image_connection(cfg)
        assert ok is True
        assert msg == "Images work."
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:7860/v1/images/generations"
        assert req.get_header("Authorization") == "Bearer image-key"
