"""Shared HTTP helpers for all AI providers.

Consolidates the duplicated request / error-handling / JSON-parsing
logic that was previously copy-pasted across every provider and the
model-fetching functions.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .base import ProviderError

# ---------------------------------------------------------------------------
# Shared SSL context
# ---------------------------------------------------------------------------

try:
    _ssl_ctx: Optional[ssl.SSLContext] = ssl.create_default_context()
except ssl.SSLError:
    _ssl_ctx = None


# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------

def http_post_json(
    url: str,
    headers: Dict[str, str],
    payload: dict,
    *,
    timeout: int = 120,
    label: str = "API",
) -> dict:
    """POST JSON and return the parsed response dict.

    Raises :class:`ProviderError` on HTTP errors, connection failures,
    empty responses, or invalid JSON.
    """
    data = json.dumps(payload).encode("utf-8")
    headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers)
    raw = _urlopen_with_errors(req, timeout=timeout, label=label)
    return _parse_json(raw, label)


def http_post_raw(
    url: str,
    headers: Dict[str, str],
    payload: dict,
    *,
    timeout: int = 120,
    label: str = "API",
) -> bytes:
    """POST JSON and return the raw response bytes (e.g. audio data).

    Raises :class:`ProviderError` on HTTP or connection errors.
    """
    data = json.dumps(payload).encode("utf-8")
    headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers)
    return _urlopen_bytes(req, timeout=timeout, label=label)


def http_get_json(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    *,
    timeout: int = 30,
    label: str = "API",
) -> dict:
    """GET a URL and return the parsed JSON response dict.

    Raises :class:`ProviderError` on HTTP errors, connection failures,
    empty responses, or invalid JSON.
    """
    req = urllib.request.Request(url, headers=headers or {})
    raw = _urlopen_with_errors(req, timeout=timeout, label=label)
    return _parse_json(raw, label)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _urlopen_with_errors(
    req: urllib.request.Request,
    *,
    timeout: int,
    label: str,
) -> str:
    """Execute the request and return the decoded body as a string."""
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ProviderError(f"{label} error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Connection error: {e.reason}") from e


def _urlopen_bytes(
    req: urllib.request.Request,
    *,
    timeout: int,
    label: str,
) -> bytes:
    """Execute the request and return raw bytes."""
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ProviderError(f"{label} error {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Connection error: {e.reason}") from e


def _parse_json(raw: str, label: str) -> dict:
    """Parse a JSON string, raising ProviderError on failure."""
    if not raw.strip():
        raise ProviderError(f"Empty response from {label}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProviderError(
            f"Invalid JSON from {label}: {e}\nResponse was: {raw[:300]}"
        ) from e
