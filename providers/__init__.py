"""AI provider factory and public API."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import List, Tuple

from ..config_manager import ProviderConfig
from .base import ImageProvider, ProviderError, TextProvider, TTSProvider


def create_text_provider(config: ProviderConfig) -> TextProvider:
    """Create a text provider from config."""
    if config.provider_type == "openai":
        from .openai_provider import OpenAITextProvider

        return OpenAITextProvider(config)
    elif config.provider_type == "anthropic":
        from .anthropic_provider import AnthropicTextProvider

        return AnthropicTextProvider(config)
    elif config.provider_type == "google":
        from .google_provider import GoogleTextProvider

        return GoogleTextProvider(config)
    raise ProviderError(f"Unknown text provider: {config.provider_type}")


def create_tts_provider(config: ProviderConfig) -> TTSProvider:
    """Create a TTS provider from config."""
    if config.provider_type == "openai":
        from .openai_provider import OpenAITTSProvider

        return OpenAITTSProvider(config)
    elif config.provider_type == "google":
        from .google_provider import GoogleTTSProvider

        return GoogleTTSProvider(config)
    raise ProviderError(f"No TTS support for provider: {config.provider_type}")


def create_image_provider(config: ProviderConfig) -> ImageProvider:
    """Create an image provider from config."""
    if config.provider_type == "openai":
        from .openai_provider import OpenAIImageProvider

        return OpenAIImageProvider(config)
    elif config.provider_type == "google":
        from .google_provider import GoogleImageProvider

        return GoogleImageProvider(config)
    raise ProviderError(f"No image support for provider: {config.provider_type}")


def test_provider_connection(config: ProviderConfig) -> Tuple[bool, str]:
    """Test connection to a provider. Returns (success, message)."""
    try:
        provider = create_text_provider(config)
        provider.generate(
            "Reply with exactly the word OK and nothing else.",
            "Test connection.",
        )
        return True, "Connection successful!"
    except ProviderError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"


# ---------------------------------------------------------------------------
# Dynamic model listing
# ---------------------------------------------------------------------------

def fetch_available_models(
    config: ProviderConfig, capability: str = "text"
) -> List[str]:
    """Fetch available models from a provider's API.

    Args:
        config: Provider configuration with API URL and key.
        capability: One of "text", "tts", "image".

    Returns:
        Sorted list of model ID strings.
    """
    if config.provider_type == "openai":
        return _fetch_openai_models(config, capability)
    elif config.provider_type == "anthropic":
        return _fetch_anthropic_models(config)
    elif config.provider_type == "google":
        return _fetch_google_models(config, capability)
    return []


def _fetch_openai_models(
    config: ProviderConfig, capability: str
) -> List[str]:
    """Fetch models from an OpenAI-compatible /models endpoint."""
    url = f"{config.api_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {config.api_key}"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ProviderError(f"API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Connection error: {e.reason}") from e

    all_ids = [m["id"] for m in data.get("data", [])]

    if capability == "text":
        prefixes = ("gpt-", "o1", "o3", "o4", "chatgpt")
        return sorted(m for m in all_ids if any(m.startswith(p) for p in prefixes))
    elif capability == "tts":
        return sorted(m for m in all_ids if "tts" in m.lower())
    elif capability == "image":
        return sorted(m for m in all_ids if "dall-e" in m.lower())
    return sorted(all_ids)


def _fetch_anthropic_models(config: ProviderConfig) -> List[str]:
    """Fetch models from the Anthropic /models endpoint."""
    url = f"{config.api_url.rstrip('/')}/models?limit=100"
    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ProviderError(f"API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Connection error: {e.reason}") from e

    return sorted(m["id"] for m in data.get("data", []))


def _fetch_google_models(
    config: ProviderConfig, capability: str = "text"
) -> List[str]:
    """Fetch models from the Google Gemini /models endpoint."""
    base = config.api_url.rstrip("/")
    url = f"{base}/models?key={config.api_key}&pageSize=1000"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ProviderError(f"API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Connection error: {e.reason}") from e

    models = []
    for m in data.get("models", []):
        name = m.get("name", "")
        if "/" in name:
            name = name.split("/", 1)[1]
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
        nl = name.lower()
        if capability == "image" and "image" in nl:
            models.append(name)
        elif capability == "tts" and ("tts" in nl or "flash" in nl):
            models.append(name)
        elif capability == "text" and "image" not in nl and "tts" not in nl:
            models.append(name)
    return sorted(models)
