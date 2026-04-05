"""AI provider factory and model classification utilities."""

from __future__ import annotations

from typing import List, Tuple

from .config import ProviderConfig
from .interfaces import ImageProvider, ProviderError, TextProvider, TTSProvider
from .network import http_get_json


def create_text_provider(config: ProviderConfig) -> TextProvider:
    """Create a text provider from config."""
    if config.provider_type == "openai":
        from ..api.openai import OpenAITextProvider

        return OpenAITextProvider(config)
    elif config.provider_type == "vercel":
        from ..api.vercel import VercelAIGatewayProvider

        return VercelAIGatewayProvider(config)
    elif config.provider_type == "anthropic":
        from ..api.anthropic import AnthropicTextProvider

        return AnthropicTextProvider(config)
    elif config.provider_type == "google":
        from ..api.google import GoogleTextProvider

        return GoogleTextProvider(config)
    raise ProviderError(f"Unknown text provider: {config.provider_type}")


def create_tts_provider(config: ProviderConfig) -> TTSProvider:
    """Create a TTS provider from config."""
    if config.provider_type == "openai":
        from ..api.openai import OpenAITTSProvider

        return OpenAITTSProvider(config)
    elif config.provider_type == "vercel":
        from ..api.vercel import VercelAIGatewayProvider

        return VercelAIGatewayProvider(config)
    elif config.provider_type == "google":
        from ..api.google import GoogleTTSProvider

        return GoogleTTSProvider(config)
    raise ProviderError(f"No TTS support for provider: {config.provider_type}")


def create_image_provider(config: ProviderConfig) -> ImageProvider:
    """Create an image provider from config."""
    if config.provider_type == "openai":
        from ..api.openai import OpenAIImageProvider

        return OpenAIImageProvider(config)
    elif config.provider_type == "vercel":
        from ..api.vercel import VercelAIGatewayProvider

        return VercelAIGatewayProvider(config)
    elif config.provider_type == "google":
        from ..api.google import GoogleImageProvider

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


def fetch_available_models(
    config: ProviderConfig, capability: str = "text"
) -> List[str]:
    """Fetch available models from a provider's API."""
    if config.provider_type in ("openai", "vercel"):
        return _fetch_openai_models(config, capability)
    elif config.provider_type == "anthropic":
        return _fetch_anthropic_models(config)
    elif config.provider_type == "google":
        return _fetch_google_models(config, capability)
    return []


def _fetch_openai_models(config: ProviderConfig, capability: str) -> List[str]:
    """Fetch models from an OpenAI-compatible /models endpoint."""
    url = f"{config.base_url}/models"
    headers = {"Authorization": f"Bearer {config.api_key}"}
    try:
        data = http_get_json(url, headers, label="OpenAI")
    except Exception as e:
        # Vercel or other gateways might have different structures or require different headers
        if "404" in str(e) and "vercel" in config.base_url.lower():
            # If standard /models fails on Vercel, it might be using a different path
            # or the user needs to configure providers in the dashboard.
            raise ProviderError(
                f"Vercel AI Gateway '/models' endpoint not found (404). "
                "Ensure your gateway is correctly configured in the Vercel dashboard."
            ) from e
        raise

    all_ids = [m["id"] for m in data.get("data", [])]
    classified: dict[str, list[str]] = {"text": [], "tts": [], "image": []}
    for mid in all_ids:
        cap = _classify_openai_model(mid)
        if cap in classified:
            classified[cap].append(mid)
    return sorted(classified.get(capability, []))


def _fetch_anthropic_models(config: ProviderConfig) -> List[str]:
    """Fetch models from the Anthropic /models endpoint."""
    url = f"{config.base_url}/models?limit=100"
    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
    }
    data = http_get_json(url, headers, label="Anthropic")
    return sorted(m["id"] for m in data.get("data", []))


# OpenAI model classification logic
_OPENAI_IMAGE_SIGNALS = ("image", "dall-e")
_OPENAI_TTS_SIGNALS = ("tts",)
_OPENAI_SKIP_SIGNALS = (
    "whisper",
    "transcrib",
    "embedding",
    "moderation",
    "realtime",
    "audio",
    "sora",
    "codex",
)


def _classify_openai_model(model_id: str) -> str | None:
    ml = model_id.lower()
    if any(s in ml for s in _OPENAI_IMAGE_SIGNALS):
        return "image"
    if any(s in ml for s in _OPENAI_TTS_SIGNALS):
        return "tts"
    if any(s in ml for s in _OPENAI_SKIP_SIGNALS):
        return None
    return "text"


def _fetch_google_models(config: ProviderConfig, capability: str = "text") -> List[str]:
    url = f"{config.base_url}/models?key={config.api_key}&pageSize=1000"
    data = http_get_json(url, label="Google")
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
    desc = model.get("description", "").lower()
    display = model.get("displayName", "").lower()
    name = model.get("name", "").lower()
    searchable = f"{desc} {display} {name}"

    if any(
        s in searchable
        for s in ("image generation", "image editing", "imagen", "nano banana")
    ):
        return "image"
    if any(s in searchable for s in ("text-to-speech", "tts", "speech synthesis")):
        return "tts"
    if "generateContent" in methods:
        return "text"
    return None
