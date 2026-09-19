"""AI provider factory and public API."""

from __future__ import annotations

from typing import List, Optional, Tuple

from ..config_manager import ProviderConfig
from .base import ImageProvider, ProviderError, TextProvider, TTSProvider
from .http import http_get_json


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
    elif config.provider_type == "openrouter":
        from .openrouter_provider import OpenRouterTextProvider

        return OpenRouterTextProvider(config)
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
    elif config.provider_type == "openrouter":
        from .openrouter_provider import OpenRouterImageProvider

        return OpenRouterImageProvider(config)
    raise ProviderError(f"No image support for provider: {config.provider_type}")


def test_provider_connection(config: ProviderConfig) -> Tuple[bool, str, Optional[str]]:
    """Test connection to a provider.

    Returns ``(success, message, detail)``, where *detail* is the raw API
    response body when one is available, for the error dialog's details
    pane.
    """
    try:
        provider = create_text_provider(config)
        provider.generate(
            "Reply with exactly the word OK and nothing else.",
            "Test connection.",
        )
        return True, "Connection successful!", None
    except ProviderError as e:
        return False, str(e), e.detail
    except Exception as e:
        return False, f"Unexpected error: {e}", None


# ---------------------------------------------------------------------------
# Dynamic model listing
# ---------------------------------------------------------------------------


def fetch_available_models(config: ProviderConfig, capability: str = "text") -> List[str]:
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
        return _fetch_anthropic_models(config, capability)
    elif config.provider_type == "google":
        return _fetch_google_models(config, capability)
    elif config.provider_type == "openrouter":
        return _fetch_openrouter_models(config, capability)
    return []


def _fetch_openai_models(config: ProviderConfig, capability: str) -> List[str]:
    """Fetch models from an OpenAI-compatible /models endpoint."""
    url = f"{config.base_url}/models"
    headers = {"Authorization": f"Bearer {config.api_key}"}
    data = http_get_json(url, headers, label="OpenAI")
    all_ids = [m["id"] for m in data.get("data", [])]
    classified: dict[str, list[str]] = {"text": [], "tts": [], "image": []}
    for mid in all_ids:
        cap = _classify_openai_model(mid)
        if cap in classified:
            classified[cap].append(mid)
    return sorted(classified.get(capability, []))


def _fetch_anthropic_models(config: ProviderConfig, capability: str = "text") -> List[str]:
    """Fetch models from the Anthropic /models endpoint.

    Anthropic ships text models only — no TTS or image generation — so
    every other capability returns an empty list rather than offering
    Claude models that can only fail when selected.
    """
    if capability != "text":
        return []
    url = f"{config.base_url}/models?limit=100"
    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
    }
    data = http_get_json(url, headers, label="Anthropic")
    return sorted(m["id"] for m in data.get("data", []))


# OpenRouter model-id suffixes that cannot serve a synchronous request.
# ``:batch`` variants are half-price asynchronous jobs; calling one through
# chat/completions returns "This model is only available through the Batch
# API. Use the /api/v1/batches endpoint instead". Other suffixes OpenRouter
# uses (``:free``, ``:nitro``, ``:online``, ``:thinking``, …) work normally
# and must stay listed.
_OPENROUTER_SKIP_SUFFIXES = (":batch",)

# Description signals for code edit-apply models (Morph, Relace).  They are
# ordinary text models by every metadata field, but reject the system+user
# pair this addon always sends: "Multi-turn conversations are not supported".
# They expect a single <instruction>/<code> payload instead, so they can
# never fill a field.  Verified to match these three models and nothing else
# across OpenRouter's full catalogue.
_OPENROUTER_NON_CHAT_SIGNALS = (
    "apply model",
    "code-patching",
    "patching llm",
    "merges ai-suggested edits",
)


def _fetch_openrouter_models(config: ProviderConfig, capability: str) -> List[str]:
    """Fetch models from OpenRouter's /models endpoint.

    OpenRouter is the only provider that publishes real capability
    metadata, so this classifies on ``architecture.output_modalities``
    instead of guessing from the model id.  TTS is not supported: the few
    audio models there use a different request shape.
    """
    if capability not in ("text", "image"):
        return []
    url = f"{config.base_url}/models"
    data = http_get_json(url, {"Authorization": f"Bearer {config.api_key}"}, label="OpenRouter")

    models = []
    for m in data.get("data", []):
        model_id = m.get("id")
        if not model_id:
            continue
        if any(model_id.endswith(suffix) for suffix in _OPENROUTER_SKIP_SUFFIXES):
            continue
        description = (m.get("description") or "").lower()
        if any(signal in description for signal in _OPENROUTER_NON_CHAT_SIGNALS):
            continue
        modalities = (m.get("architecture") or {}).get("output_modalities") or []
        if capability == "image":
            if "image" in modalities:
                models.append(model_id)
        # Models that emit images or audio are not chat models, even though
        # they also list "text": the audio ones (gpt-audio, lyria music
        # generation) reject a plain chat request.
        elif "text" in modalities and not {"image", "audio"} & set(modalities):
            models.append(model_id)
    return sorted(models)


# OpenAI model ID substrings that indicate non-text-chat categories.
# Order matters: checked top-to-bottom, first match wins.
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
    # Legacy completions-only models: rejected by /chat/completions with
    # "This is not a chat model ... Did you mean to use v1/completions?"
    "davinci",
    "babbage",
    "-instruct",
    # Served only by their own endpoints, not chat/completions or responses.
    "deep-research",
    "-search-api",
    "search-preview",
    "gpt-live",
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


def _fetch_google_models(config: ProviderConfig, capability: str = "text") -> List[str]:
    """Fetch models from the Google Gemini /models endpoint."""
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
    image_signals = ("image generation", "image editing", "imagen", "nano banana", "native image")
    if any(s in searchable for s in image_signals):
        return "image"

    # TTS / speech-generation models
    tts_signals = (
        "text-to-speech",
        "text to speech",
        "tts",
        "speech generation",
        "speech synthesis",
    )
    if any(s in searchable for s in tts_signals):
        return "tts"

    # Models that advertise generateContent but reject a plain text chat
    # request — music generation, robotics, speech-to-text, computer use,
    # and the models served only by the Interactions API.
    non_chat_signals = (
        "lyria",
        "music",
        "robotics",
        "transcribe",
        "computer-use",
        "computer use",
        "deep-research",
        "deep research",
        "antigravity",
        "-omni",
        "veo",
        "embedding",
    )
    if any(s in searchable for s in non_chat_signals):
        return None

    # Everything else that supports generateContent is a text model
    if "generateContent" in methods:
        return "text"

    return None


__all__ = [
    "create_text_provider",
    "create_tts_provider",
    "create_image_provider",
    "test_provider_connection",
    "fetch_available_models",
    "_classify_openai_model",
    "_classify_google_model",
]
