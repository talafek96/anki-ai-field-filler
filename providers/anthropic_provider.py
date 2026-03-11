"""Anthropic Claude provider implementation (text generation only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..config_manager import ProviderConfig
from .base import ProviderError, TextProvider


class AnthropicTextProvider(TextProvider):
    """Anthropic Claude text generation."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self._config.api_url.rstrip('/')}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._config.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self._config.text_model,
            "max_tokens": self._config.max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["content"][0]["text"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise ProviderError(
                f"Anthropic API error {e.code}: {body}"
            ) from e
        except urllib.error.URLError as e:
            raise ProviderError(f"Connection error: {e.reason}") from e
