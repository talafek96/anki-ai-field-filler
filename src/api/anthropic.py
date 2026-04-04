"""Anthropic Claude provider implementation (text generation only)."""

from __future__ import annotations

from ..core.interfaces import ProviderError, TextProvider
from ..core.network import http_post_json

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
        try:
            result = http_post_json(url, headers, payload, label=_LABEL)
            return result["content"][0]["text"]
        except (KeyError, IndexError) as e:
            raise ProviderError(f"Unexpected Anthropic response format: {e}") from e

    def chat(self, messages: list[dict[str, str]]) -> str:
        url = f"{self._config.base_url}/messages"
        headers = {
            "x-api-key": self._config.api_key,
            "anthropic-version": "2023-06-01",
        }

        system_msg = ""
        other_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                other_msgs.append(m)

        payload = {
            "model": self._config.text_model,
            "max_tokens": self._config.max_tokens,
            "messages": other_msgs,
        }
        if system_msg:
            payload["system"] = system_msg

        try:
            result = http_post_json(url, headers, payload, label=_LABEL)
            return result["content"][0]["text"]
        except (KeyError, IndexError) as e:
            raise ProviderError(f"Unexpected Anthropic response format: {e}") from e
