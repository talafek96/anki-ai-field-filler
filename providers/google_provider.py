"""Google Gemini provider implementation (text, TTS, and image generation).

Supports text generation, native image generation (Nano Banana), and
speech synthesis via the Gemini generateContent API.
"""

from __future__ import annotations

import base64

from ..config_manager import ProviderConfig
from .base import ImageProvider, ProviderError, TextProvider, TTSProvider
from .http import http_post_json

_LABEL = "Google API"


class _GoogleRequestMixin:
    """Shared request logic for Google Gemini endpoints."""

    _config: ProviderConfig

    def _generate_content(
        self, model: str, payload: dict, timeout: int = 120
    ) -> dict:
        url = (
            f"{self._config.base_url}/models/{model}"
            f":generateContent?key={self._config.api_key}"
        )
        return http_post_json(url, {}, payload, timeout=timeout, label=_LABEL)


class GoogleTextProvider(_GoogleRequestMixin, TextProvider):
    """Google Gemini text generation."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        model = self._config.text_model
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "maxOutputTokens": self._config.max_tokens,
                "temperature": 0.7,
            },
        }
        try:
            result = self._generate_content(model, payload)
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise ProviderError(
                f"Unexpected Google API response format: {e}"
            ) from e


class GoogleImageProvider(_GoogleRequestMixin, ImageProvider):
    """Google Gemini native image generation (Nano Banana)."""

    def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        model = self._config.image_model or "gemini-2.5-flash-image"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"],
            },
        }
        try:
            result = self._generate_content(model, payload, timeout=180)
            for part in result["candidates"][0]["content"]["parts"]:
                if "inlineData" in part:
                    return base64.b64decode(part["inlineData"]["data"])
            raise ProviderError("No image data in Google API response")
        except (KeyError, IndexError) as e:
            raise ProviderError(
                f"Unexpected Google API response format: {e}"
            ) from e


class GoogleTTSProvider(_GoogleRequestMixin, TTSProvider):
    """Google Gemini native speech synthesis."""

    def synthesize(self, text: str, language: str = "", voice: str = "") -> bytes:
        model = self._config.tts_model or "gemini-2.5-flash-preview-tts"
        voice_name = voice or self._config.tts_voice or "Kore"
        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice_name,
                        }
                    }
                },
            },
        }
        try:
            result = self._generate_content(model, payload)
            for part in result["candidates"][0]["content"]["parts"]:
                if "inlineData" in part:
                    return base64.b64decode(part["inlineData"]["data"])
            raise ProviderError("No audio data in Google API response")
        except (KeyError, IndexError) as e:
            raise ProviderError(
                f"Unexpected Google API response format: {e}"
            ) from e
