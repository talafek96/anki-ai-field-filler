"""Google Gemini provider implementation (text generation only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..config_manager import ProviderConfig
from .base import ProviderError, TextProvider


class GoogleTextProvider(TextProvider):
    """Google Gemini text generation."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        model = self._config.text_model
        base = self._config.api_url.rstrip("/")
        url = f"{base}/models/{model}:generateContent?key={self._config.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "maxOutputTokens": self._config.max_tokens,
                "temperature": 0.7,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise ProviderError(
                f"Google API error {e.code}: {body}"
            ) from e
        except urllib.error.URLError as e:
            raise ProviderError(f"Connection error: {e.reason}") from e
        except (KeyError, IndexError) as e:
            raise ProviderError(
                f"Unexpected Google API response format: {e}"
            ) from e
