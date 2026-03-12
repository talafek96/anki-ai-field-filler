"""OpenAI provider implementation (text, TTS, image).

Also compatible with any OpenAI-compatible API (Azure OpenAI, local LLMs, etc.)
by changing the api_url in config.
"""

from __future__ import annotations

import base64

from ..config_manager import ProviderConfig
from .base import ImageProvider, ProviderError, TextProvider, TTSProvider
from .http import http_post_json, http_post_raw

_LABEL = "OpenAI API"


class _OpenAIRequestMixin:
    """Shared helpers for OpenAI endpoints."""

    _config: ProviderConfig

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._config.api_key}"}

    def _request(self, url: str, payload: dict, timeout: int = 120) -> dict:
        """Make a JSON request to an OpenAI-compatible endpoint."""
        return http_post_json(
            url,
            self._auth_headers(),
            payload,
            timeout=timeout,
            label=_LABEL,
        )

    def _request_raw(self, url: str, payload: dict, timeout: int = 120) -> bytes:
        """Make a JSON request and return raw response bytes."""
        return http_post_raw(
            url,
            self._auth_headers(),
            payload,
            timeout=timeout,
            label=_LABEL,
        )


class OpenAITextProvider(_OpenAIRequestMixin, TextProvider):
    """OpenAI / OpenAI-compatible text generation."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self._config.base_url}/chat/completions"
        payload = {
            "model": self._config.text_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_completion_tokens": self._config.max_tokens,
            "temperature": 0.7,
        }
        try:
            result = self._request(url, payload)
        except ProviderError as e:
            # Fall back to legacy max_tokens for older models/endpoints
            if "max_completion_tokens" in str(e) and "unsupported" in str(e).lower():
                payload.pop("max_completion_tokens")
                payload["max_tokens"] = self._config.max_tokens
                result = self._request(url, payload)
            else:
                raise
        return result["choices"][0]["message"]["content"]


class OpenAITTSProvider(_OpenAIRequestMixin, TTSProvider):
    """OpenAI text-to-speech."""

    def synthesize(self, text: str, language: str = "", voice: str = "") -> bytes:
        url = f"{self._config.base_url}/audio/speech"
        voice = voice or self._config.tts_voice or "alloy"
        payload = {
            "model": self._config.tts_model or "tts-1",
            "input": text,
            "voice": voice,
        }
        return self._request_raw(url, payload)


class OpenAIImageProvider(_OpenAIRequestMixin, ImageProvider):
    """OpenAI DALL-E image generation."""

    def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        url = f"{self._config.base_url}/images/generations"
        payload = {
            "model": self._config.image_model or "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        }
        result = self._request(url, payload, timeout=180)
        b64_data = result["data"][0]["b64_json"]
        return base64.b64decode(b64_data)
