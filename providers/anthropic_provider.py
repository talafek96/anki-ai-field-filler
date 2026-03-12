"""Anthropic Claude provider implementation (text generation only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..config_manager import ProviderConfig
from .base import ProviderError, TextProvider
from .openai_provider import _ssl_ctx


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
            with urllib.request.urlopen(
                req, timeout=120, context=_ssl_ctx
            ) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise ProviderError(
                f"Anthropic API error {e.code}: {body}"
            ) from e
        except urllib.error.URLError as e:
            raise ProviderError(f"Connection error: {e.reason}") from e

        if not raw.strip():
            raise ProviderError("Empty response from Anthropic API")
        try:
            result = json.loads(raw)
            return result["content"][0]["text"]
        except json.JSONDecodeError as e:
            raise ProviderError(
                f"Invalid JSON from Anthropic API: {e}\n"
                f"Response was: {raw[:300]}"
            ) from e
        except (KeyError, IndexError) as e:
            raise ProviderError(
                f"Unexpected Anthropic response format: {e}"
            ) from e
