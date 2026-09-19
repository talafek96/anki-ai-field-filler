"""Google Gemini provider implementation (text, TTS, and image generation).

Supports text generation, native image generation (Nano Banana), and
speech synthesis via the Gemini generateContent API.
"""

from __future__ import annotations

import base64
from typing import ClassVar, List

from ..config.config_manager import ProviderConfig
from .base import ImageProvider, ProviderError, TextProvider, TTSProvider
from .http import http_post_json

_LABEL = "Google API"


def _finish_reason_message(finish: str, candidate: dict) -> str:
    """A finishReason-specific, actionable message for an empty response.

    ``finishReason`` is not always a safety block: ``OTHER`` is a catch-all,
    ``MAX_TOKENS`` means the budget was spent (often on a thinking model's
    reasoning) before any output, and only ``SAFETY``/``PROHIBITED_CONTENT``
    are genuine content blocks — so each gets its own guidance instead of
    always blaming safety filters.
    """
    reason = (finish or "unknown").upper()
    if reason in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"):
        blocked = [
            r.get("category", "?") for r in candidate.get("safetyRatings", []) if r.get("blocked")
        ]
        detail = f" Triggered: {', '.join(blocked)}." if blocked else ""
        return (
            f"Google blocked the response for content policy (finishReason: {reason})."
            f"{detail} Try rephrasing the prompt."
        )
    if reason == "MAX_TOKENS":
        return (
            "Google returned no content (finishReason: MAX_TOKENS) — the token budget was "
            "spent before any output, which thinking models can do on their reasoning. "
            "Raise Max tokens or pick a non-thinking model."
        )
    if reason in ("RECITATION", "IMAGE_RECITATION"):
        return (
            "Google blocked the output for reproducing recited/recognizable content "
            f"(finishReason: {reason}) — the image models flag this readily, even for "
            "generic prompts. Make the prompt more original/abstract, or switch to "
            "another image model (e.g. gemini-2.5-flash-image)."
        )
    return (
        f"Google returned no content (finishReason: {reason}). This preview model may be "
        "unstable or unable to fulfil the request — try a different model or rephrase the prompt."
    )


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
            raise ProviderError(_finish_reason_message(finish, candidate))

        return content["parts"]


def _is_system_instruction_error(msg: str) -> bool:
    """Does this error mean the model has no system-instruction support?

    Gemma models and a few preview models reject ``system_instruction``
    with "Developer instruction is not enabled for <model>".
    """
    low = msg.lower()
    return "developer instruction" in low or "system_instruction" in low


class GoogleTextProvider(_GoogleRequestMixin, TextProvider):
    """Google Gemini text generation."""

    # Models known (at runtime) to reject system_instruction; the system
    # prompt gets folded into the user turn for these instead.
    _no_system_instruction: ClassVar[set[str]] = set()

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        model = self._config.text_model
        inline = model in self._no_system_instruction
        try:
            result = self._generate_content(
                model, self._payload(system_prompt, user_prompt, inline)
            )
        except ProviderError as e:
            if "no longer available" in str(e).lower():
                raise ProviderError(
                    f"The model '{model}' has been retired by Google and is no "
                    "longer available. Pick a current model in the AI Field "
                    "Filler settings."
                ) from e
            if inline or not _is_system_instruction_error(str(e)):
                raise
            # Retry with the system prompt folded into the user turn.
            self._no_system_instruction.add(model)
            result = self._generate_content(model, self._payload(system_prompt, user_prompt, True))

        parts = self._extract_parts(result)
        text = self._join_text_parts(parts)
        if not text:
            raise ProviderError("Google API returned empty text in response")
        return text

    def _payload(self, system_prompt: str, user_prompt: str, inline_system: bool) -> dict:
        """Build a generateContent payload.

        When *inline_system* is set the system prompt is prepended to the
        user turn instead of being sent as ``system_instruction``.
        """
        payload: dict = {
            "generationConfig": {
                "maxOutputTokens": self._config.max_tokens,
                "temperature": 0.7,
            },
        }
        if inline_system and system_prompt:
            combined = f"{system_prompt}\n\n{user_prompt}"
            payload["contents"] = [{"parts": [{"text": combined}]}]
        else:
            if system_prompt:
                payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
            payload["contents"] = [{"parts": [{"text": user_prompt}]}]
        return payload

    @staticmethod
    def _join_text_parts(parts: List[dict]) -> str:
        """Concatenate answer text, skipping reasoning parts.

        Gemini 3.x thinking models put ``{"thought": true}`` parts ahead of
        the answer, so ``parts[0]["text"]`` can return the model's internal
        reasoning — or nothing at all.
        """
        return "".join(
            p.get("text", "")
            for p in parts
            if isinstance(p, dict) and not p.get("thought") and p.get("text")
        )


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
