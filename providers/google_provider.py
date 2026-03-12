"""Google Gemini provider implementation (text, TTS, and image generation).

Supports text generation, native image generation (Nano Banana), and
speech synthesis via the Gemini generateContent API.
"""

from __future__ import annotations

import base64
from typing import List

from ..config_manager import ProviderConfig
from .base import ImageProvider, ProviderError, TextProvider, TTSProvider
from .http import http_post_json

_LABEL = "Google API"


class _GoogleRequestMixin:
    """Shared request logic for Google Gemini endpoints."""

    _config: ProviderConfig

    def _generate_content(self, model: str, payload: dict, timeout: int = 120) -> dict:
        url = f"{self._config.base_url}/models/{model}:generateContent?key={self._config.api_key}"
        return http_post_json(url, {}, payload, timeout=timeout, label=_LABEL)

    @staticmethod
    def _extract_parts(result: dict) -> List[dict]:
        """Extract parts from the first candidate, with clear error messages."""
        candidates = result.get("candidates")
        if not candidates:
            # Check for prompt-level blocking
            feedback = result.get("promptFeedback", {})
            block_reason = feedback.get("blockReason", "unknown")
            raise ProviderError(
                f"Google API returned no candidates (prompt blocked: {block_reason})"
            )

        candidate = candidates[0]
        content = candidate.get("content")
        if not content or "parts" not in content:
            finish = candidate.get("finishReason", "unknown")
            raise ProviderError(
                f"Google API returned no content (finishReason: {finish}). "
                "The response may have been blocked by safety filters."
            )

        return content["parts"]


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
        result = self._generate_content(model, payload)
        parts = self._extract_parts(result)
        text = parts[0].get("text", "")
        if not text:
            raise ProviderError("Google API returned empty text in response")
        return text


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
        result = self._generate_content(model, payload, timeout=180)
        parts = self._extract_parts(result)
        for part in parts:
            if "inlineData" in part:
                return base64.b64decode(part["inlineData"]["data"])
        raise ProviderError("No image data in Google API response")


class GoogleTTSProvider(_GoogleRequestMixin, TTSProvider):
    """Google Gemini native speech synthesis.

    The Gemini TTS models do NOT support ``system_instruction``.  All
    pronunciation / style guidance must be embedded directly in the
    ``contents`` text, following the prompting structure described in
    https://ai.google.dev/gemini-api/docs/speech-generation.
    """

    def synthesize(
        self, text: str, language: str = "", voice: str = "", context: str = ""
    ) -> bytes:
        model = self._config.tts_model or "gemini-2.5-flash-preview-tts"
        voice_name = voice or self._config.tts_voice or "Kore"

        # Build the prompt text.  The TTS model treats the entire contents
        # as direction + transcript, so we prepend any context as Director's
        # Notes and mark the actual text as the Transcript.
        prompt_parts: list[str] = []
        if context:
            prompt_parts.append(
                "Use the following context to determine the correct "
                "language, pronunciation, intonation, and speaking style:\n" + context
            )
        prompt_parts.append("Read the following text aloud exactly as written:\n" + text)
        prompt = "\n\n".join(prompt_parts)

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
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
        result = self._generate_content(model, payload)
        parts = self._extract_parts(result)
        for part in parts:
            if "inlineData" in part:
                return base64.b64decode(part["inlineData"]["data"])
        raise ProviderError("No audio data in Google API response")
