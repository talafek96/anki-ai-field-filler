"""Vercel AI Gateway provider implementation.

Uses Vercel's OpenAI-compatible gateway middleware for unified LLM access.
"""

from __future__ import annotations

from ..core.config import ProviderConfig
from .openai import OpenAIImageProvider, OpenAITextProvider, OpenAITTSProvider


class VercelAIGatewayProvider(
    OpenAITextProvider, OpenAITTSProvider, OpenAIImageProvider
):
    """Vercel AI Gateway provider implementation (OpenAI-compatible)."""

    def __init__(self, config: ProviderConfig) -> None:
        if not config.api_url:
            config.api_url = "https://gateway.vercel.ai/v1"
        super().__init__(config)
