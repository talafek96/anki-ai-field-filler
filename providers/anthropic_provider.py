"""Anthropic Claude provider implementation (text generation only)."""

from __future__ import annotations

from .base import ProviderError, TextProvider
from .http import http_post_json

_LABEL = "Anthropic API"


class AnthropicTextProvider(TextProvider):
    """Anthropic Claude text generation."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self._config.base_url}/messages"
        headers = {
            "x-api-key": self._config.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self._config.text_model,
            "max_tokens": self._config.max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        result = http_post_json(url, headers, payload, label=_LABEL)
        return self._extract_text(result)

    @staticmethod
    def _extract_text(result: dict) -> str:
        """Collect the text blocks from a Messages API response.

        Models with extended thinking enabled return ``thinking`` (and
        ``redacted_thinking``) blocks *before* the answer, so indexing
        ``content[0]["text"]`` raises KeyError on exactly the newest models.
        Join every text block instead and ignore the rest.
        """
        blocks = result.get("content")
        if not isinstance(blocks, list):
            raise ProviderError(f"Unexpected Anthropic response format: {result!r:.200}")

        chunks = [
            b["text"]
            for b in blocks
            if isinstance(b, dict) and b.get("type", "text") == "text" and b.get("text")
        ]
        if chunks:
            return "".join(chunks)

        stop = result.get("stop_reason", "unknown")
        if stop == "max_tokens":
            raise ProviderError(
                "The model used its entire token budget on thinking and returned "
                "no text. Raise 'Max tokens' in the provider settings."
            )
        kinds = sorted({b.get("type", "?") for b in blocks if isinstance(b, dict)})
        raise ProviderError(
            f"Anthropic returned no text block (stop_reason: {stop}; "
            f"block types: {', '.join(kinds) or 'none'})."
        )
