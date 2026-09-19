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

There is no TTS support: OpenRouter exposes only a handful of audio
models and they use a different request shape.
"""

from __future__ import annotations

import base64
import binascii

from .base import ImageProvider, ProviderError
from .http import http_post_json
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
