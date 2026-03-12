"""AI provider factory and public API."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import List, Tuple

from ..config_manager import ProviderConfig
from .base import ImageProvider, ProviderError, TextProvider, TTSProvider

# Shared SSL context — import from openai_provider to stay DRY
from .openai_provider import _ssl_ctx


def _safe_json(raw: str, label: str) -> dict:
    """Parse JSON from a response, raising ProviderError on failure."""
    if not raw.strip():
        raise ProviderError(f"Empty response from {label}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProviderError(
            f"Invalid JSON from {label}: {e}\nResponse was: {raw[:300]}"
        ) from e


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
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ProviderError(f"API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Connection error: {e.reason}") from e

    data = _safe_json(raw, "OpenAI")
    all_ids = [m["id"] for m in data.get("data", [])]
    classified: dict[str, list[str]] = {"text": [], "tts": [], "image": []}
    for mid in all_ids:
        cap = _classify_openai_model(mid)
        if cap in classified:
            classified[cap].append(mid)
    return sorted(classified.get(capability, []))


def _fetch_anthropic_models(config: ProviderConfig) -> List[str]:
    """Fetch models from the Anthropic /models endpoint."""
    url = f"{config.api_url.rstrip('/')}/models?limit=100"
    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ProviderError(f"API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Connection error: {e.reason}") from e

    data = _safe_json(raw, "Anthropic")
    return sorted(m["id"] for m in data.get("data", []))


# OpenAI model ID substrings that indicate non-text-chat categories.
# Order matters: checked top-to-bottom, first match wins.
_OPENAI_IMAGE_SIGNALS = ("image", "dall-e")
_OPENAI_TTS_SIGNALS = ("tts",)
_OPENAI_SKIP_SIGNALS = (
    "whisper", "transcrib", "embedding", "moderation",
    "realtime", "audio", "sora", "codex",
)


def _classify_openai_model(model_id: str) -> str | None:
    """Classify an OpenAI model ID as 'text', 'tts', 'image', or None.

    The OpenAI /models API has no capability metadata, so we classify
    by exclusion: identify image / TTS / non-chat models first, then
    treat everything remaining as a text-chat model.
    """
    ml = model_id.lower()
    if any(s in ml for s in _OPENAI_IMAGE_SIGNALS):
        return "image"
    if any(s in ml for s in _OPENAI_TTS_SIGNALS):
        return "tts"
    if any(s in ml for s in _OPENAI_SKIP_SIGNALS):
        return None
    return "text"


def _fetch_google_models(
    config: ProviderConfig, capability: str = "text"
) -> List[str]:
    """Fetch models from the Google Gemini /models endpoint."""
    base = config.api_url.rstrip("/")
    url = f"{base}/models?key={config.api_key}&pageSize=1000"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ProviderError(f"API error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Connection error: {e.reason}") from e

    data = _safe_json(raw, "Google")
    models = []
    for m in data.get("models", []):
        name = m.get("name", "")
        if "/" in name:
            name = name.split("/", 1)[1]
        methods = m.get("supportedGenerationMethods", [])
        cap = _classify_google_model(m, methods)
        if cap == capability:
            models.append(name)
    return sorted(models)


def _classify_google_model(model: dict, methods: List[str]) -> str | None:
    """Classify a Google model as 'text', 'tts', 'image', or None.

    Uses description and displayName (the most reliable metadata the
    API exposes) with model name as a fallback.  Returns None for
    models that don't support generateContent or don't match any
    category we care about (e.g. embeddings, video, robotics).
    """
    desc = model.get("description", "").lower()
    display = model.get("displayName", "").lower()
    name = model.get("name", "").lower()
    searchable = f"{desc} {display} {name}"

    # Image generation models (Nano Banana, Imagen, …)
    image_signals = ("image generation", "image editing",
                     "imagen", "nano banana", "native image")
    if any(s in searchable for s in image_signals):
        return "image"

    # TTS / speech-generation models
    tts_signals = ("text-to-speech", "text to speech", "tts",
                   "speech generation", "speech synthesis")
    if any(s in searchable for s in tts_signals):
        return "tts"

    # Everything else that supports generateContent is a text model
    if "generateContent" in methods:
        return "text"

    return None
