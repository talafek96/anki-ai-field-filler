"""Tests for the OpenRouter provider."""

from __future__ import annotations

import base64
import json
from unittest.mock import patch

import pytest

from ai_field_filler.config_manager import ProviderConfig
from ai_field_filler.providers import (
    _fetch_openrouter_models,
    create_image_provider,
    create_text_provider,
    create_tts_provider,
)
from ai_field_filler.providers.base import ProviderError
from ai_field_filler.providers.openrouter_provider import (
    OpenRouterImageProvider,
    OpenRouterTextProvider,
    _decode_data_uri,
)

_HTTP_POST_JSON = "ai_field_filler.providers.openai_provider.http_post_json"
_OR_POST_JSON = "ai_field_filler.providers.openrouter_provider.http_post_json"
_HTTP_GET_JSON = "ai_field_filler.providers.http_get_json"

_CFG = ProviderConfig(
    provider_type="openrouter",
    api_url="https://openrouter.ai/api/v1",
    api_key="or-key",
    text_model="anthropic/claude-sonnet-5",
    image_model="google/gemini-3.1-flash-image",
    max_tokens=4096,
)

_PNG = b"\x89PNG\r\n\x1a\n" + b"rest-of-png"


class TestFactory:
    def test_creates_text_provider(self) -> None:
        assert isinstance(create_text_provider(_CFG), OpenRouterTextProvider)

    def test_creates_image_provider(self) -> None:
        assert isinstance(create_image_provider(_CFG), OpenRouterImageProvider)

    def test_has_no_tts_support(self) -> None:
        with pytest.raises(ProviderError, match="No TTS support"):
            create_tts_provider(_CFG)


class TestTextProvider:
    @patch(_HTTP_POST_JSON)
    def test_generate(self, mock_post) -> None:
        mock_post.return_value = {"choices": [{"message": {"content": "Hi"}}]}
        assert OpenRouterTextProvider(_CFG).generate("sys", "user") == "Hi"

    @patch(_HTTP_POST_JSON)
    def test_sends_openrouter_headers_and_label(self, mock_post) -> None:
        mock_post.return_value = {"choices": [{"message": {"content": "Hi"}}]}
        OpenRouterTextProvider(_CFG).generate("sys", "user")
        headers = mock_post.call_args[0][1]
        assert headers["Authorization"] == "Bearer or-key"
        assert headers["HTTP-Referer"]
        assert headers["X-Title"] == "Anki AI Field Filler"
        # Errors must be attributed to OpenRouter, not OpenAI.
        assert mock_post.call_args.kwargs["label"] == "OpenRouter API"

    @patch(_HTTP_POST_JSON)
    def test_posts_to_chat_completions(self, mock_post) -> None:
        mock_post.return_value = {"choices": [{"message": {"content": "Hi"}}]}
        OpenRouterTextProvider(_CFG).generate("sys", "user")
        assert mock_post.call_args[0][0] == ("https://openrouter.ai/api/v1/chat/completions")

    @patch(_HTTP_POST_JSON)
    def test_missing_endpoint_gets_actionable_message(self, mock_post) -> None:
        mock_post.side_effect = ProviderError(
            "OpenRouter API error 404: No endpoints found for x/y.", detail="{}"
        )
        with pytest.raises(ProviderError, match="No provider is currently serving"):
            OpenRouterTextProvider(_CFG).generate("sys", "user")

    @patch(_HTTP_POST_JSON)
    def test_other_errors_propagate(self, mock_post) -> None:
        mock_post.side_effect = ProviderError("OpenRouter API error 401: bad key")
        with pytest.raises(ProviderError, match="401"):
            OpenRouterTextProvider(_CFG).generate("sys", "user")


class TestDecodeDataUri:
    def test_decodes_base64_png(self) -> None:
        uri = "data:image/png;base64," + base64.b64encode(_PNG).decode()
        assert _decode_data_uri(uri) == _PNG

    def test_rejects_remote_url(self) -> None:
        with pytest.raises(ProviderError, match="image URL"):
            _decode_data_uri("https://example.com/a.png")

    def test_rejects_empty_payload(self) -> None:
        with pytest.raises(ProviderError, match="empty image payload"):
            _decode_data_uri("data:image/png;base64,")


class TestImageProvider:
    @patch(_OR_POST_JSON)
    def test_extracts_inline_image(self, mock_post) -> None:
        uri = "data:image/png;base64," + base64.b64encode(_PNG).decode()
        mock_post.return_value = {
            "choices": [{"message": {"images": [{"image_url": {"url": uri}}]}}]
        }
        assert OpenRouterImageProvider(_CFG).generate_image("a circle") == _PNG

    @patch(_OR_POST_JSON)
    def test_requests_image_modality(self, mock_post) -> None:
        uri = "data:image/png;base64," + base64.b64encode(_PNG).decode()
        mock_post.return_value = {
            "choices": [{"message": {"images": [{"image_url": {"url": uri}}]}}]
        }
        OpenRouterImageProvider(_CFG).generate_image("a circle")
        payload = mock_post.call_args[0][2]
        assert payload["modalities"] == ["image", "text"]
        assert payload["model"] == "google/gemini-3.1-flash-image"

    @patch(_OR_POST_JSON)
    def test_surfaces_refusal(self, mock_post) -> None:
        mock_post.return_value = {"choices": [{"message": {"images": [], "refusal": "nope"}}]}
        with pytest.raises(ProviderError, match="refused the image request"):
            OpenRouterImageProvider(_CFG).generate_image("a circle")

    @patch(_OR_POST_JSON)
    def test_no_image_data(self, mock_post) -> None:
        mock_post.return_value = {"choices": [{"message": {"content": "text only"}}]}
        with pytest.raises(ProviderError, match="No image data"):
            OpenRouterImageProvider(_CFG).generate_image("a circle")

    @patch(_OR_POST_JSON)
    def test_malformed_response(self, mock_post) -> None:
        mock_post.return_value = {"choices": []}
        with pytest.raises(ProviderError, match="Unexpected OpenRouter"):
            OpenRouterImageProvider(_CFG).generate_image("a circle")


def _models_payload() -> dict:
    def entry(mid, outs):
        return {"id": mid, "architecture": {"output_modalities": outs}}

    return {
        "data": [
            entry("anthropic/claude-sonnet-5", ["text"]),
            entry("openai/gpt-6-astra", ["text"]),
            entry("google/gemini-3.1-flash-image", ["image", "text"]),
            entry("openai/gpt-audio", ["text", "audio"]),
            entry("broken/no-id", ["text"]),
        ]
    }


class TestModelListing:
    """Classification uses real capability metadata, not id guessing."""

    @patch(_HTTP_GET_JSON)
    def test_text_excludes_image_models(self, mock_get) -> None:
        mock_get.return_value = _models_payload()
        models = _fetch_openrouter_models(_CFG, "text")
        assert "anthropic/claude-sonnet-5" in models
        assert "openai/gpt-6-astra" in models
        assert "google/gemini-3.1-flash-image" not in models

    @patch(_HTTP_GET_JSON)
    def test_image_only_image_models(self, mock_get) -> None:
        mock_get.return_value = _models_payload()
        assert _fetch_openrouter_models(_CFG, "image") == ["google/gemini-3.1-flash-image"]

    @patch(_HTTP_GET_JSON)
    def test_tts_is_empty(self, mock_get) -> None:
        mock_get.return_value = _models_payload()
        assert _fetch_openrouter_models(_CFG, "tts") == []
        mock_get.assert_not_called()

    @patch(_HTTP_GET_JSON)
    def test_sends_bearer_token(self, mock_get) -> None:
        mock_get.return_value = {"data": []}
        _fetch_openrouter_models(_CFG, "text")
        assert mock_get.call_args[0][1] == {"Authorization": "Bearer or-key"}

    @patch(_HTTP_GET_JSON)
    def test_skips_entries_without_id(self, mock_get) -> None:
        mock_get.return_value = {"data": [{"architecture": {"output_modalities": ["text"]}}]}
        assert _fetch_openrouter_models(_CFG, "text") == []

    @patch(_HTTP_GET_JSON)
    def test_results_are_sorted(self, mock_get) -> None:
        mock_get.return_value = json.loads(json.dumps(_models_payload()))
        models = _fetch_openrouter_models(_CFG, "text")
        assert models == sorted(models)


class TestBatchVariantsExcluded:
    """':batch' models are async-only and 404 on chat/completions."""

    @staticmethod
    def _payload() -> dict:
        def entry(mid, outs):
            return {"id": mid, "architecture": {"output_modalities": outs}}

        return {
            "data": [
                entry("openai/gpt-6-astra", ["text"]),
                entry("openai/gpt-6-astra:batch", ["text"]),
                entry("anthropic/claude-fable-5.1:batch", ["text"]),
                entry("google/gemini-3.1-flash-image:batch", ["image", "text"]),
                entry("meta-llama/llama-4-maverick:free", ["text"]),
                entry("perplexity/sonar:online", ["text"]),
            ]
        }

    @patch(_HTTP_GET_JSON)
    def test_batch_variants_are_hidden(self, mock_get) -> None:
        mock_get.return_value = self._payload()
        models = _fetch_openrouter_models(_CFG, "text")
        assert "openai/gpt-6-astra" in models
        assert not [m for m in models if m.endswith(":batch")]

    @patch(_HTTP_GET_JSON)
    def test_batch_variants_hidden_for_images_too(self, mock_get) -> None:
        mock_get.return_value = self._payload()
        assert _fetch_openrouter_models(_CFG, "image") == []

    @patch(_HTTP_GET_JSON)
    def test_other_suffixes_are_kept(self, mock_get) -> None:
        mock_get.return_value = self._payload()
        models = _fetch_openrouter_models(_CFG, "text")
        assert "meta-llama/llama-4-maverick:free" in models
        assert "perplexity/sonar:online" in models
