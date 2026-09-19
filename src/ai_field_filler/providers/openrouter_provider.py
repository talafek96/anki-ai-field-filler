"""OpenRouter provider implementation (text and image generation).

OpenRouter is a single OpenAI-compatible gateway in front of every major
vendor, which makes it the most robust option when providers change their
APIs: it normalises request parameters per model server-side, so a request
carrying ``temperature`` succeeds even against models whose native API
rejects it.

Two differences from the plain OpenAI provider:

* Models are namespaced (``anthropic/claude-sonnet-5``), and the
  ``/models`` endpoint reports real capability metadata — the only one of
  our providers that does — so models are classified from
  ``architecture.output_modalities`` rather than guessed from the id.
* Image generation runs through ``/chat/completions`` with
  ``modalities: ["image", "text"]``, returning data URIs in
  ``message.images``, not through a separate ``/images`` endpoint.

Speech works too, but only over a streamed request — see
:class:`OpenRouterTTSProvider`.
"""

from __future__ import annotations

import base64
import binascii
from typing import Iterator

from .base import ImageProvider, ProviderError, TTSProvider
from .http import http_post_json, http_post_sse
from .openai_provider import OpenAITextProvider

_LABEL = "OpenRouter API"

# Sent for OpenRouter's public leaderboards; both are optional but
# identify the addon rather than leaving the request anonymous.
_REFERER = "https://github.com/talafek96/anki-ai-field-filler"
_TITLE = "Anki AI Field Filler"


def _openrouter_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": _REFERER,
        "X-Title": _TITLE,
    }


def _decode_data_uri(url: str) -> bytes:
    """Decode a ``data:image/...;base64,...`` URI into raw bytes."""
    if not url.startswith("data:"):
        raise ProviderError(
            "OpenRouter returned an image URL rather than inline data, "
            "which this addon cannot save."
        )
    _, _, payload = url.partition(",")
    if not payload:
        raise ProviderError("OpenRouter returned an empty image payload.")
    try:
        return base64.b64decode(payload)
    except (binascii.Error, ValueError) as e:
        raise ProviderError(f"Could not decode OpenRouter image data: {e}") from e


class OpenRouterTextProvider(OpenAITextProvider):
    """OpenRouter text generation.

    Reuses the OpenAI chat/completions path — including its parameter
    negotiation — and only swaps in OpenRouter's headers.  The inherited
    ``/responses`` fallback never triggers here, because OpenRouter does
    not emit the OpenAI-specific errors that would activate it.
    """

    _label = _LABEL

    def _auth_headers(self) -> dict:
        return _openrouter_headers(self._config.api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            return super().generate(system_prompt, user_prompt)
        except ProviderError as e:
            # OpenRouter lists models whose upstream providers are all
            # offline; the raw message doesn't suggest what to do about it.
            if "no endpoints found" in str(e).lower():
                raise ProviderError(
                    f"No provider is currently serving '{self._config.text_model}' "
                    "on OpenRouter. Pick a different model.",
                    detail=e.detail,
                ) from e
            raise


class OpenRouterTTSProvider(TTSProvider):
    """OpenRouter speech synthesis via a streamed chat completion.

    OpenRouter has no ``/audio/speech`` endpoint and no dedicated TTS
    models; speech comes from the ``gpt-audio`` chat models with an audio
    modality, and only when ``stream`` is set — a non-streamed request is
    rejected with "Audio output requires stream: true".  The audio arrives
    as base64 fragments spread across ``delta.audio.data`` in the event
    frames, which are concatenated before decoding.

    ``pcm16`` is the only format the streaming path accepts (wav, mp3 and
    opus are all refused), so this returns raw 24 kHz mono PCM and relies
    on :class:`~ai_field_filler.core.media_handler.MediaHandler` to add the WAV
    header, exactly as it already does for Google's TTS.
    """

    _DEFAULT_MODEL = "openai/gpt-audio-mini"
    _DEFAULT_VOICE = "alloy"

    def synthesize(
        self, text: str, language: str = "", voice: str = "", context: str = ""
    ) -> bytes:
        model = self._config.tts_model or self._DEFAULT_MODEL
        # The API rejects an empty or unknown voice, so never send a blank.
        voice_name = voice or self._config.tts_voice or self._DEFAULT_VOICE

        prompt_parts = []
        if context:
            prompt_parts.append(
                "Use the following context to determine the correct "
                "language, pronunciation, intonation, and speaking style:\n" + context
            )
        prompt_parts.append("Read the following text aloud exactly as written:\n" + text)

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "\n\n".join(prompt_parts)}],
            "modalities": ["text", "audio"],
            "audio": {"voice": voice_name, "format": "pcm16"},
            "stream": True,
        }
        url = f"{self._config.base_url}/chat/completions"
        events = http_post_sse(
            url,
            _openrouter_headers(self._config.api_key),
            payload,
            timeout=180,
            label=_LABEL,
        )
        return self._collect_audio(events)

    @staticmethod
    def _collect_audio(events: Iterator[dict]) -> bytes:
        """Concatenate the base64 audio fragments from the event stream."""
        fragments: list = []
        for event in events:
            error = event.get("error")
            if isinstance(error, dict):
                # Errors can arrive mid-stream rather than as an HTTP status.
                message = error.get("message") or "unknown error"
                raise ProviderError(f"{_LABEL} error: {message}")
            for choice in event.get("choices") or []:
                audio = (choice.get("delta") or {}).get("audio")
                if isinstance(audio, dict) and audio.get("data"):
                    fragments.append(audio["data"])

        if not fragments:
            raise ProviderError(
                "No audio data in OpenRouter response. The selected model may "
                "not support speech output."
            )
        try:
            return base64.b64decode("".join(fragments))
        except (binascii.Error, ValueError) as e:
            raise ProviderError(f"Could not decode OpenRouter audio data: {e}") from e


class OpenRouterImageProvider(ImageProvider):
    """OpenRouter image generation via the chat/completions endpoint."""

    def generate_image(self, prompt: str, size: str = "1024x1024") -> bytes:
        url = f"{self._config.base_url}/chat/completions"
        payload = {
            "model": self._config.image_model or "google/gemini-2.5-flash-image",
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
        }
        result = http_post_json(
            url,
            _openrouter_headers(self._config.api_key),
            payload,
            timeout=180,
            label=_LABEL,
        )
        return self._extract_image(result)

    @staticmethod
    def _extract_image(result: dict) -> bytes:
        try:
            message = result["choices"][0]["message"]
        except (KeyError, IndexError) as e:
            raise ProviderError(f"Unexpected OpenRouter response format: {e}") from e

        for image in message.get("images") or []:
            url = (image.get("image_url") or {}).get("url", "")
            if url:
                return _decode_data_uri(url)

        refusal = message.get("refusal")
        if refusal:
            raise ProviderError(f"OpenRouter refused the image request: {refusal}")
        raise ProviderError(
            "No image data in OpenRouter response. The selected model may not support image output."
        )
