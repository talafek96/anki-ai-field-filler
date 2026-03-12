"""Tests for providers/http.py shared HTTP helpers."""

from __future__ import annotations

import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from ai_field_filler.providers.base import ProviderError
from ai_field_filler.providers.http import (
    _parse_json,
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


def _mock_urlopen(response_data: str | bytes, status: int = 200):
    """Create a mock for urllib.request.urlopen."""
    mock_resp = MagicMock()
    if isinstance(response_data, str):
        response_data = response_data.encode("utf-8")
    mock_resp.read.return_value = response_data
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestHttpPostJson:
    @patch("ai_field_filler.providers.http.urllib.request.urlopen")
    def test_success(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen('{"result": "ok"}')
        result = http_post_json(
            "https://api.test/v1/endpoint",
            {"Authorization": "Bearer test"},
            {"model": "gpt-4o"},
            label="Test",
        )
        assert result == {"result": "ok"}
        mock_urlopen.assert_called_once()

    @patch("ai_field_filler.providers.http.urllib.request.urlopen")
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

    @patch("ai_field_filler.providers.http.urllib.request.urlopen")
    def test_url_error(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        with pytest.raises(ProviderError, match="Connection error"):
            http_post_json("https://api.test", {}, {}, label="Test")

    @patch("ai_field_filler.providers.http.urllib.request.urlopen")
    def test_empty_response(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen("")
        with pytest.raises(ProviderError, match="Empty response"):
            http_post_json("https://api.test", {}, {}, label="Test")

    @patch("ai_field_filler.providers.http.urllib.request.urlopen")
    def test_invalid_json_response(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen("not json")
        with pytest.raises(ProviderError, match="Invalid JSON"):
            http_post_json("https://api.test", {}, {}, label="Test")

    @patch("ai_field_filler.providers.http.urllib.request.urlopen")
    def test_content_type_header_set(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen('{"ok": true}')
        http_post_json("https://api.test", {"X-Custom": "val"}, {}, label="Test")
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_header("Content-type") == "application/json"
        assert req.get_header("X-custom") == "val"


class TestHttpPostRaw:
    @patch("ai_field_filler.providers.http.urllib.request.urlopen")
    def test_returns_bytes(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen(b"\xff\xfb\x90audio-data")
        result = http_post_raw(
            "https://api.test/audio",
            {},
            {"input": "hello"},
            label="Test",
        )
        assert result == b"\xff\xfb\x90audio-data"

    @patch("ai_field_filler.providers.http.urllib.request.urlopen")
    def test_http_error(self, mock_urlopen) -> None:
        error = urllib.error.HTTPError(
            "https://api.test",
            500,
            "Server Error",
            {},
            BytesIO(b"internal error"),
        )
        mock_urlopen.side_effect = error
        with pytest.raises(ProviderError, match="500"):
            http_post_raw("https://api.test", {}, {}, label="Test")


class TestHttpGetJson:
    @patch("ai_field_filler.providers.http.urllib.request.urlopen")
    def test_success(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen('{"data": []}')
        result = http_get_json("https://api.test/models", label="Test")
        assert result == {"data": []}

    @patch("ai_field_filler.providers.http.urllib.request.urlopen")
    def test_with_headers(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _mock_urlopen('{"data": []}')
        http_get_json(
            "https://api.test/models",
            {"Authorization": "Bearer key"},
            label="Test",
        )
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_header("Authorization") == "Bearer key"

    @patch("ai_field_filler.providers.http.urllib.request.urlopen")
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
