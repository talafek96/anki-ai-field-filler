"""OpenAI provider implementation (text, TTS, image).

Also compatible with any OpenAI-compatible API (Azure OpenAI, local LLMs, etc.)
by changing the api_url in config.
"""

from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.request

from ..config_manager import ProviderConfig
from .base import ImageProvider, ProviderError, TextProvider, TTSProvider

# Use the system certificate store on Windows; fall back to default context
try:
    _ssl_ctx = ssl.create_default_context()
except ssl.SSLError:
    _ssl_ctx = None


class _OpenAIRequestMixin:
    """Shared HTTP request logic for OpenAI endpoints."""

    _config: ProviderConfig

    def _request(self, url: str, payload: dict, timeout: int = 120) -> dict:
        """Make a JSON request to an OpenAI-compatible endpoint."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._config.api_key}",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(
                req, timeout=timeout, context=_ssl_ctx
            ) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise ProviderError(
                f"OpenAI API error {e.code}: {body}"
            ) from e
        except urllib.error.URLError as e:
            raise ProviderError(f"Connection error: {e.reason}") from e

        if not raw.strip():
            raise ProviderError("Empty response from API")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ProviderError(
                f"Invalid JSON response from API: {e}\n"
                f"Response was: {raw[:300]}"
            ) from e

    def _request_raw(self, url: str, payload: dict, timeout: int = 120) -> bytes:
        """Make a JSON request and return raw response bytes."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._config.api_key}",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(
                req, timeout=timeout, context=_ssl_ctx
            ) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise ProviderError(
                f"OpenAI API error {e.code}: {body}"
            ) from e
        except urllib.error.URLError as e:
            raise ProviderError(f"Connection error: {e.reason}") from e


class OpenAITextProvider(_OpenAIRequestMixin, TextProvider):
    """OpenAI / OpenAI-compatible text generation."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self._config.api_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self._config.text_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self._config.max_tokens,
            "temperature": 0.7,
        }
        result = self._request(url, payload)
        return result["choices"][0]["message"]["content"]


class OpenAITTSProvider(_OpenAIRequestMixin, TTSProvider):
    """OpenAI text-to-speech."""

    def synthesize(self, text: str, language: str = "", voice: str = "") -> bytes:
        url = f"{self._config.api_url.rstrip('/')}/audio/speech"
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
        url = f"{self._config.api_url.rstrip('/')}/images/generations"
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
