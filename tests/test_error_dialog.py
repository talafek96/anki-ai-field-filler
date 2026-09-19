"""Tests for the error dialog's payload formatting."""

from __future__ import annotations

from ai_field_filler.ui.error_dialog import _prettify


class TestPrettify:
    def test_pretty_prints_a_json_document(self) -> None:
        assert _prettify('{"error":{"code":400}}') == ('{\n  "error": {\n    "code": 400\n  }\n}')

    def test_pretty_prints_json_embedded_in_a_message(self) -> None:
        out = _prettify('OpenAI API error 400: {"error":{"code":400}}')
        assert out.startswith("OpenAI API error 400: {")
        assert '\n  "error"' in out

    def test_leaves_plain_text_untouched(self) -> None:
        assert _prettify("Connection error: timed out") == "Connection error: timed out"

    def test_leaves_malformed_json_untouched(self) -> None:
        text = 'broken {"error": '
        assert _prettify(text) == text

    def test_preserves_non_ascii(self) -> None:
        assert "שלום" in _prettify('{"msg": "שלום"}')

    def test_empty_string(self) -> None:
        assert _prettify("") == ""
