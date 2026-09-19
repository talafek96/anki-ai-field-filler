"""Shared HTTP helpers for all AI providers.

Consolidates the duplicated request / error-handling / JSON-parsing
logic that was previously copy-pasted across every provider and the
model-fetching functions.

All request helpers automatically retry on transient server errors
(429, 500, 502, 503, 504) using exponential backoff with jitter.
"""

from __future__ import annotations

import ast
import json
import random
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, Optional

from .base import ProviderError

# ---------------------------------------------------------------------------
# Shared SSL context
# ---------------------------------------------------------------------------

try:
    _ssl_ctx: Optional[ssl.SSLContext] = ssl.create_default_context()
except ssl.SSLError:
    _ssl_ctx = None

# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds
_MAX_DELAY = 30.0  # seconds

# Some API providers (e.g. xAI/Grok) sit behind Cloudflare, which
# rejects the default ``Python-urllib/3.x`` User-Agent with a 403
# (error 1010).  A benign, descriptive UA avoids that.
_USER_AGENT = "AnkiAIFieldFiller/1.0"


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
    headers = {"User-Agent": _USER_AGENT, **headers, "Content-Type": "application/json"}
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
    headers = {"User-Agent": _USER_AGENT, **headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers)
    return _urlopen_bytes(req, timeout=timeout, label=label)


def http_post_sse(
    url: str,
    headers: Dict[str, str],
    payload: dict,
    *,
    timeout: int = 180,
    label: str = "API",
) -> Iterator[dict]:
    """POST JSON and iterate over the server-sent events that come back.

    Needed for endpoints that only stream — OpenRouter refuses audio
    output unless ``stream`` is set, so a TTS reply arrives as a sequence
    of ``data:`` frames instead of one document.

    Yields each frame's parsed JSON object, stopping at ``[DONE]``.
    Non-JSON frames (keep-alive comments) are skipped.  The connection is
    opened eagerly so HTTP errors raise from this call rather than from
    the first iteration; unlike the other helpers there is no retry once
    bytes are flowing, because a stream cannot be resumed part-way.
    """
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "User-Agent": _USER_AGENT,
        **headers,
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    req = urllib.request.Request(url, data=data, headers=headers)
    response = _urlopen_stream(req, timeout=timeout, label=label)
    return _iter_sse(response)


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
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, **(headers or {})})
    raw = _urlopen_with_errors(req, timeout=timeout, label=label)
    return _parse_json(raw, label)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


# Gateway messages that say nothing on their own; the real reason is in
# ``error.metadata`` instead.
_GENERIC_ERROR_MESSAGES = ("provider returned error",)


def _loads_lenient(text: str) -> object:
    """Parse a payload that is JSON, or a Python repr of a dict.

    Some gateways forward the upstream error after it has been
    ``str()``-ed, producing ``{'message': "...", 'code': 400}`` with
    single quotes, which ``json.loads`` rejects.  Falling back to
    ``literal_eval`` keeps those messages readable instead of dumping a
    dict literal at the user.  ``literal_eval`` only builds constants,
    so it cannot execute anything.
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return None


def _upstream_message(metadata: dict) -> str:
    """Pull the upstream provider's own wording out of ``error.metadata``.

    OpenRouter wraps the real failure in ``metadata.raw`` — sometimes a JSON
    document, sometimes a bare sentence — while ``error.message`` stays a
    generic "Provider returned error".  Without this, an end-of-life model
    and a malformed request are indistinguishable to the user.
    """
    raw = metadata.get("raw")
    message = ""
    if isinstance(raw, str):
        parsed_raw = _loads_lenient(raw)
        if isinstance(parsed_raw, dict):
            message = str(
                parsed_raw.get("message") or parsed_raw.get("msg") or parsed_raw.get("error") or ""
            )
        else:
            message = raw
    elif isinstance(raw, dict):
        message = str(raw.get("message") or raw.get("msg") or "")

    message = " ".join(message.split())
    provider = metadata.get("provider_name")
    if message and provider:
        return f"{provider}: {message}"
    if message:
        return message
    # No raw payload, but the gateway may still suggest a remedy.
    return " ".join(str(metadata.get("remedy_hint") or "").split())


def _http_error(label: str, code: int, body: str) -> ProviderError:
    """Build a ProviderError with a one-line summary and the full body.

    OpenAI, Anthropic and Google all nest the useful sentence at
    ``error.message``; everything around it is noise in a message box.  The
    untouched body is kept as ``detail`` so the error dialog can show it
    pretty-printed on demand.
    """
    summary = ""
    detail = body
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if isinstance(parsed, dict):
        detail = json.dumps(parsed, indent=2, ensure_ascii=False)
        err = parsed.get("error")
        if isinstance(err, dict):
            summary = str(err.get("message") or err.get("type") or "")
            metadata = err.get("metadata")
            if isinstance(metadata, dict):
                upstream = _upstream_message(metadata)
                if upstream and summary.strip().lower() in _GENERIC_ERROR_MESSAGES:
                    summary = upstream
                elif upstream and upstream not in summary:
                    summary = f"{summary} — {upstream}"
        elif isinstance(err, str):
            summary = err
        if not summary:
            summary = str(parsed.get("message") or "")

    summary = " ".join(summary.split())
    if not summary:
        summary = " ".join(body.split())[:300]
    return ProviderError(f"{label} error {code}: {summary}", detail=detail)


def _urlopen_stream(
    req: urllib.request.Request,
    *,
    timeout: int,
    label: str,
) -> Any:
    """Open a streaming response, retrying transient errors before reading.

    Retrying is only safe here because nothing has been consumed yet.
    """
    last_exc: Optional[ProviderError] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                wait = _retry_after(e) if e.code == 429 else None
                time.sleep(wait if wait is not None else _backoff_delay(attempt))
                last_exc = _http_error(label, e.code, body)
                continue
            raise _http_error(label, e.code, body) from e
        except urllib.error.URLError as e:
            raise ProviderError(f"Connection error: {e.reason}") from e
    raise last_exc  # type: ignore[misc]


def _iter_sse(response: Any) -> Iterator[dict]:
    """Yield parsed JSON objects from an event-stream response."""
    try:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            # Blank separators and ``:`` comments are keep-alives.
            if not line or line.startswith(":") or not line.startswith("data:"):
                continue
            frame = line[len("data:") :].strip()
            if frame == "[DONE]":
                return
            try:
                parsed = json.loads(frame)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                yield parsed
    finally:
        response.close()


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff with jitter: ``base * 2^attempt + jitter``."""
    delay = min(_MAX_DELAY, _BASE_DELAY * (2**attempt))
    return delay + random.uniform(0, 1)


def _retry_after(error: urllib.error.HTTPError) -> Optional[float]:
    """Extract ``Retry-After`` header value (seconds) if present."""
    val = error.headers.get("Retry-After") if error.headers else None
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _urlopen_with_errors(
    req: urllib.request.Request,
    *,
    timeout: int,
    label: str,
) -> str:
    """Execute the request and return the decoded body as a string.

    Retries up to ``_MAX_RETRIES`` times on transient HTTP errors
    (429/5xx) with exponential backoff.
    """
    last_exc: Optional[ProviderError] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                wait = _retry_after(e) if e.code == 429 else None
                time.sleep(wait if wait is not None else _backoff_delay(attempt))
                # urllib re-reads req.data on each call, so the
                # Request object is safe to reuse.
                last_exc = _http_error(label, e.code, body)
                continue
            raise _http_error(label, e.code, body) from e
        except urllib.error.URLError as e:
            raise ProviderError(f"Connection error: {e.reason}") from e
    raise last_exc  # type: ignore[misc]


def _urlopen_bytes(
    req: urllib.request.Request,
    *,
    timeout: int,
    label: str,
) -> bytes:
    """Execute the request and return raw bytes.

    Retries up to ``_MAX_RETRIES`` times on transient HTTP errors
    (429/5xx) with exponential backoff.
    """
    last_exc: Optional[ProviderError] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                wait = _retry_after(e) if e.code == 429 else None
                time.sleep(wait if wait is not None else _backoff_delay(attempt))
                last_exc = _http_error(label, e.code, body)
                continue
            raise _http_error(label, e.code, body) from e
        except urllib.error.URLError as e:
            raise ProviderError(f"Connection error: {e.reason}") from e
    raise last_exc  # type: ignore[misc]


def _parse_json(raw: str, label: str) -> dict:
    """Parse a JSON string, raising ProviderError on failure."""
    if not raw.strip():
        raise ProviderError(f"Empty response from {label}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProviderError(f"Invalid JSON from {label}: {e}\nResponse was: {raw[:300]}") from e
