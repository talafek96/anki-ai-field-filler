"""OpenAI provider implementation (text, TTS, image).

Also compatible with any OpenAI-compatible API (Azure OpenAI, OpenRouter,
local LLMs, etc.) by changing the api_url in config.

Newer OpenAI models keep changing which request parameters and which
endpoint they accept, so :class:`OpenAITextProvider` negotiates those
quirks at runtime instead of hard-coding a model list.  See
``PITFALLS.md`` for the empirical failure matrix this is based on.
"""

from __future__ import annotations

import base64
from typing import Dict, Set

from ..config_manager import ProviderConfig
from .base import ImageProvider, ProviderError, TextProvider, TTSProvider
from .http import http_post_json, http_post_raw

_LABEL = "OpenAI API"

# ---------------------------------------------------------------------------
# Runtime-learned model quirks
# ---------------------------------------------------------------------------

# Maps model id -> set of quirk flags learned from previous API errors, so a
# model only pays the cost of a rejected request once per Anki session.
#   "no_temperature"  - rejects the temperature parameter (reasoning models)
#   "legacy_tokens"   - wants max_tokens instead of max_completion_tokens
#   "responses_api"   - only served by /v1/responses, not /v1/chat/completions
_MODEL_QUIRKS: Dict[str, Set[str]] = {}


def _quirks(model: str) -> Set[str]:
    return _MODEL_QUIRKS.setdefault(model, set())


def _is_temperature_error(msg: str) -> bool:
    """Does this error say the model rejects the temperature parameter?

    Covers all three phrasings OpenAI currently returns:
      - "Unsupported value: 'temperature' does not support 0.7 ..."
      - "Unsupported parameter: 'temperature' is not supported with ..."
      - "Model incompatible request argument supplied: temperature"
    """
    return "temperature" in msg and ("unsupported" in msg.lower() or "incompatible" in msg.lower())


def _is_responses_api_error(msg: str) -> bool:
    """Does this error mean the model must go through /v1/responses?"""
    low = msg.lower()
    return (
        "only supported in v1/responses" in low
        or "not a chat model" in low
        or "v1/responses" in low
    )


def _is_deprecated_error(msg: str) -> bool:
    return "has been deprecated" in msg.lower()


def _is_max_tokens_error(msg: str) -> bool:
    low = msg.lower()
    return "max_completion_tokens" in low and (
        "unsupported" in low or "not supported" in low or "unknown" in low
    )


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
    """OpenAI / OpenAI-compatible text generation.

    Handles three families of endpoint in one interface:
      - ``/chat/completions`` for the GPT-3.5/4/4.1/4o/5.x chat models
      - ``/responses`` for the ``*-pro`` and ``o*-pro`` reasoning models,
        which are not served by chat/completions at all
      - reasoning models that reject ``temperature``
    """

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        model = self._config.text_model
        if "responses_api" in _quirks(model):
            return self._generate_responses(system_prompt, user_prompt)
        try:
            return self._generate_chat(system_prompt, user_prompt)
        except ProviderError as e:
            msg = str(e)
            if _is_deprecated_error(msg):
                raise ProviderError(
                    f"The model '{model}' has been deprecated and removed by OpenAI. "
                    "Pick a current model in the AI Field Filler settings."
                ) from e
            if _is_responses_api_error(msg):
                _quirks(model).add("responses_api")
                return self._generate_responses(system_prompt, user_prompt)
            raise

    # -- chat/completions -------------------------------------------------

    def _generate_chat(self, system_prompt: str, user_prompt: str) -> str:
        model = self._config.text_model
        url = f"{self._config.base_url}/chat/completions"
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        quirks = _quirks(model)
        if "legacy_tokens" in quirks:
            payload["max_tokens"] = self._config.max_tokens
        else:
            payload["max_completion_tokens"] = self._config.max_tokens
        if "no_temperature" not in quirks:
            payload["temperature"] = 0.7

        try:
            result = self._request(url, payload)
        except ProviderError as e:
            msg = str(e)
            retry = False
            # Reasoning models only accept the default temperature.
            if "temperature" in payload and _is_temperature_error(msg):
                quirks.add("no_temperature")
                payload.pop("temperature")
                retry = True
            # Older models/endpoints want the legacy max_tokens name.
            if "max_completion_tokens" in payload and _is_max_tokens_error(msg):
                quirks.add("legacy_tokens")
                payload["max_tokens"] = payload.pop("max_completion_tokens")
                retry = True
            if not retry:
                raise
            result = self._request(url, payload)

        return self._extract_chat_text(result)

    @staticmethod
    def _extract_chat_text(result: dict) -> str:
        try:
            choice = result["choices"][0]
        except (KeyError, IndexError) as e:
            raise ProviderError(f"Unexpected OpenAI response format: {e}") from e
        message = choice.get("message") or {}
        content = message.get("content")
        if not content:
            finish = choice.get("finishReason") or choice.get("finish_reason")
            if finish == "length":
                raise ProviderError(
                    "The model used its entire token budget on reasoning and "
                    "returned no text. Raise 'Max tokens' in the provider "
                    "settings, or pick a non-reasoning model."
                )
            raise ProviderError(f"OpenAI returned an empty response (finish_reason: {finish}).")
        return content

    # -- responses --------------------------------------------------------

    def _generate_responses(self, system_prompt: str, user_prompt: str) -> str:
        """Call /v1/responses, used by the *-pro reasoning models."""
        url = f"{self._config.base_url}/responses"
        payload = {
            "model": self._config.text_model,
            "instructions": system_prompt,
            "input": user_prompt,
            "max_output_tokens": self._config.max_tokens,
        }
        result = self._request(url, payload, timeout=600)
        return self._extract_responses_text(result)

    @staticmethod
    def _extract_responses_text(result: dict) -> str:
        """Pull assistant text out of a /v1/responses payload.

        The output array interleaves reasoning items with message items, so
        we collect every ``output_text`` part rather than indexing [0].
        """
        direct = result.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct

        chunks = []
        for item in result.get("output", []) or []:
            if item.get("type") != "message":
                continue  # skip reasoning / tool-call items
            for part in item.get("content", []) or []:
                if part.get("type") in ("output_text", "text"):
                    text = part.get("text", "")
                    if text:
                        chunks.append(text)
        if chunks:
            return "".join(chunks)

        status = result.get("status", "unknown")
        if result.get("incomplete_details"):
            reason = result["incomplete_details"].get("reason", "unknown")
            raise ProviderError(
                f"The model returned no text (incomplete: {reason}). "
                "Raise 'Max tokens' in the provider settings."
            )
        raise ProviderError(f"OpenAI returned no text output (status: {status}).")


class OpenAITTSProvider(_OpenAIRequestMixin, TTSProvider):
    """OpenAI text-to-speech."""

    def synthesize(
        self, text: str, language: str = "", voice: str = "", context: str = ""
    ) -> bytes:
        url = f"{self._config.base_url}/audio/speech"
        voice = voice or self._config.tts_voice or "alloy"
        payload = {
            "model": self._config.tts_model or "tts-1",
            "input": text,
            "voice": voice,
        }
        return self._request_raw(url, payload)


class OpenAIImageProvider(_OpenAIRequestMixin, ImageProvider):
    """OpenAI image generation (GPT Image and DALL-E)."""

    # gpt-image-* models use a different API shape than dall-e-*:
    #   - No response_format param (b64_json is always returned)
    #   - Uses output_format instead for the file type
    _GPT_IMAGE_PREFIXES = ("gpt-image", "chatgpt-image")

    def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        url = f"{self._config.base_url}/images/generations"
        model = self._config.image_model or "dall-e-3"
        is_gpt_image = any(model.startswith(p) for p in self._GPT_IMAGE_PREFIXES)

        payload: dict = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": size,
        }
        if is_gpt_image:
            payload["output_format"] = "png"
        else:
            payload["response_format"] = "b64_json"

        try:
            result = self._request(url, payload, timeout=180)
        except ProviderError as e:
            # Fall back to output_format for models that reject response_format
            if "response_format" in payload and "response_format" in str(e):
                payload.pop("response_format")
                payload["output_format"] = "png"
                result = self._request(url, payload, timeout=180)
            else:
                raise
        try:
            b64_data = result["data"][0]["b64_json"]
        except (KeyError, IndexError) as e:
            raise ProviderError(f"Unexpected OpenAI image response format: {e}") from e
        return base64.b64decode(b64_data)
