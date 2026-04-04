"""Tests for providers/http.py shared HTTP helpers."""

from __future__ import annotations

import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from src.core.interfaces import ProviderError
from src.core.network import (
    _RETRYABLE_STATUS_CODES,
    _backoff_delay,
    _parse_json,
    _retry_after,
    http_get_json,
    http_post_json,
    http_post_raw,
)


class TestParseJson:
    def test_valid_json(self) -> None:
        assert _parse_json('{"key": "value"}', "test") == {"key": "value"}

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ProviderError, match="Empty response"):
            _parse_json("", "test")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ProviderError, match="Empty response"):
            _parse_json("   \n  ", "test")

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ProviderError, match="Invalid JSON"):
            _parse_json("not json", "test")

    def test_label_in_error_message(self) -> None:
        with pytest.raises(ProviderError, match="MyProvider"):
            _parse_json("", "MyProvider")


class TestHttpPostJson:
    def test_success(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = b'{"result": "ok"}'
        result = http_post_json(
            "https://api.test/v1/endpoint",
            {"Authorization": "Bearer test"},
            {"model": "gpt-4o"},
            label="Test",
        )
        assert result == {"result": "ok"}
        mock_urlopen.assert_called_once()

    def test_http_error(self, mock_urlopen) -> None:
        error = urllib.error.HTTPError(
            "https://api.test",
            401,
            "Unauthorized",
            {},
            BytesIO(b'{"error": "invalid key"}'),
        )
        mock_urlopen.side_effect = error
        with pytest.raises(ProviderError, match="401"):
            http_post_json("https://api.test", {}, {}, label="Test")

    def test_url_error(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        with pytest.raises(ProviderError, match="Connection error"):
            http_post_json("https://api.test", {}, {}, label="Test")

    def test_empty_response(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = b""
        with pytest.raises(ProviderError, match="Empty response"):
            http_post_json("https://api.test", {}, {}, label="Test")

    def test_invalid_json_response(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = b"not json"
        with pytest.raises(ProviderError, match="Invalid JSON"):
            http_post_json("https://api.test", {}, {}, label="Test")

    def test_content_type_header_set(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = b'{"ok": true}'
        http_post_json("https://api.test", {"X-Custom": "val"}, {}, label="Test")
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_header("Content-type") == "application/json"
        assert req.get_header("X-custom") == "val"


class TestHttpPostRaw:
    def test_returns_bytes(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = b"\xff\xfb\x90audio-data"
        result = http_post_raw(
            "https://api.test/audio",
            {},
            {"input": "hello"},
            label="Test",
        )
        assert result == b"\xff\xfb\x90audio-data"

    def test_http_error_non_retryable(self, mock_urlopen) -> None:
        error = urllib.error.HTTPError(
            "https://api.test",
            401,
            "Unauthorized",
            {},
            BytesIO(b"bad key"),
        )
        mock_urlopen.side_effect = error
        with pytest.raises(ProviderError, match="401"):
            http_post_raw("https://api.test", {}, {}, label="Test")
        # Non-retryable → single attempt
        assert mock_urlopen.call_count == 1


class TestHttpGetJson:
    def test_success(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = b'{"data": []}'
        result = http_get_json("https://api.test/models", label="Test")
        assert result == {"data": []}

    def test_with_headers(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = None
        mock_urlopen.return_value.read.return_value = b'{"data": []}'
        http_get_json(
            "https://api.test/models",
            {"Authorization": "Bearer key"},
            label="Test",
        )
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_header("Authorization") == "Bearer key"

    def test_http_error(self, mock_urlopen) -> None:
        error = urllib.error.HTTPError(
            "https://api.test",
            403,
            "Forbidden",
            {},
            BytesIO(b"access denied"),
        )
        mock_urlopen.side_effect = error
        with pytest.raises(ProviderError, match="403"):
            http_get_json("https://api.test", label="Test")


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


def _make_http_error(code: int, body: bytes = b"error", headers=None):
    """Create an HTTPError with a fresh readable body stream."""
    return urllib.error.HTTPError("https://api.test", code, "err", headers or {}, BytesIO(body))


class TestBackoffDelay:
    def test_increases_with_attempt(self) -> None:
        d0 = _backoff_delay(0)
        d2 = _backoff_delay(2)
        # attempt-2 base is 4× attempt-0 base, so even with jitter the
        # minimum of attempt-2 (4.0) should exceed the base of attempt-0 (1.0).
        assert d0 >= 1.0
        assert d2 >= 4.0

    def test_capped_at_max(self) -> None:
        d = _backoff_delay(100)
        # max delay 30 s + up to 1 s jitter
        assert d <= 31.0


class TestRetryAfter:
    def test_extracts_numeric_header(self) -> None:
        err = _make_http_error(429)
        err.headers = MagicMock()
        err.headers.get.return_value = "5"
        assert _retry_after(err) == 5.0

    def test_returns_none_when_missing(self) -> None:
        err = _make_http_error(429)
        err.headers = MagicMock()
        err.headers.get.return_value = None
        assert _retry_after(err) is None

    def test_returns_none_for_non_numeric(self) -> None:
        err = _make_http_error(429)
        err.headers = MagicMock()
        err.headers.get.return_value = "Wed, 01 Jan 2025 00:00:00 GMT"
        assert _retry_after(err) is None


class TestRetryOnTransientErrors:
    """Verify that retryable status codes trigger retries and others don't."""

    @patch("src.core.network.time.sleep")
    def test_500_retried_then_succeeds(self, mock_sleep, mock_urlopen) -> None:
        """A single 500 followed by success should work."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__.return_value = mock_resp

        mock_urlopen.side_effect = [
            _make_http_error(500, b"server error"),
            mock_resp,
        ]
        result = http_post_json("https://api.test", {}, {}, label="Test")
        assert result == {"ok": True}
        assert mock_urlopen.call_count == 2
        mock_sleep.assert_called_once()

    @patch("src.core.network.time.sleep")
    def test_500_exhausts_retries(self, mock_sleep, mock_urlopen) -> None:
        """All attempts fail with 500 → ProviderError raised."""
        mock_urlopen.side_effect = [_make_http_error(500, b"fail") for _ in range(4)]
        with pytest.raises(ProviderError, match="500"):
            http_post_json("https://api.test", {}, {}, label="Test")
        # 1 initial + 3 retries = 4 total attempts
        assert mock_urlopen.call_count == 4
        assert mock_sleep.call_count == 3

    @patch("src.core.network.time.sleep")
    def test_429_uses_retry_after_header(self, mock_sleep, mock_urlopen) -> None:
        headers = MagicMock()
        headers.get.return_value = "3"
        err = urllib.error.HTTPError(
            "https://api.test", 429, "Rate limited", headers, BytesIO(b"slow down")
        )
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__.return_value = mock_resp

        mock_urlopen.side_effect = [err, mock_resp]
        result = http_post_json("https://api.test", {}, {}, label="Test")
        assert result == {"ok": True}
        mock_sleep.assert_called_once_with(3.0)

    @patch("src.core.network.time.sleep")
    def test_401_not_retried(self, mock_sleep, mock_urlopen) -> None:
        mock_urlopen.side_effect = _make_http_error(401, b"bad key")
        with pytest.raises(ProviderError, match="401"):
            http_post_json("https://api.test", {}, {}, label="Test")
        assert mock_urlopen.call_count == 1
        mock_sleep.assert_not_called()

    @patch("src.core.network.time.sleep")
    def test_raw_bytes_retried(self, mock_sleep, mock_urlopen) -> None:
        """http_post_raw also retries on 502."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"\x00audio"
        mock_resp.__enter__.return_value = mock_resp

        mock_urlopen.side_effect = [
            _make_http_error(502, b"bad gateway"),
            mock_resp,
        ]
        result = http_post_raw("https://api.test", {}, {}, label="Test")
        assert result == b"\x00audio"
        assert mock_urlopen.call_count == 2

    @patch("src.core.network.time.sleep")
    def test_get_json_retried(self, mock_sleep, mock_urlopen) -> None:
        """http_get_json also retries on 503."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"models": []}'
        mock_resp.__enter__.return_value = mock_resp

        mock_urlopen.side_effect = [
            _make_http_error(503, b"unavailable"),
            mock_resp,
        ]
        result = http_get_json("https://api.test/models", label="Test")
        assert result == {"models": []}
        assert mock_urlopen.call_count == 2

    def test_retryable_codes_complete(self) -> None:
        assert _RETRYABLE_STATUS_CODES == {429, 500, 502, 503, 504}
