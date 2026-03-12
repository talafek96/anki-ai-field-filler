"""Tests for response parsing, HTML conversion, and retry logic in FieldFiller."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from ai_field_filler.field_filler import FieldFiller
from ai_field_filler.providers.base import ProviderError


class TestParseResponse:
    """Tests for FieldFiller._parse_response."""

    def test_clean_json(self, filler) -> None:
        raw = json.dumps(
            {
                "fields": {
                    "Meaning": {"content": "hello", "type": "text"},
                    "Audio": None,
                }
            }
        )
        result = filler._parse_response(raw)
        assert result["Meaning"]["content"] == "hello"
        assert result["Audio"] is None

    def test_json_with_markdown_fences(self, filler) -> None:
        raw = '```json\n{"fields": {"Word": {"content": "test", "type": "text"}}}\n```'
        result = filler._parse_response(raw)
        assert result["Word"]["content"] == "test"

    def test_json_with_only_opening_fence(self, filler) -> None:
        raw = '```\n{"fields": {"A": {"content": "x", "type": "text"}}}\n```'
        result = filler._parse_response(raw)
        assert result["A"]["content"] == "x"

    def test_json_embedded_in_text(self, filler) -> None:
        raw = 'Here is the result:\n{"fields": {"B": {"content": "y", "type": "text"}}}\nDone!'
        result = filler._parse_response(raw)
        assert result["B"]["content"] == "y"

    def test_flat_json_without_fields_wrapper(self, filler) -> None:
        raw = json.dumps({"Word": {"content": "flat", "type": "text"}})
        result = filler._parse_response(raw)
        assert result["Word"]["content"] == "flat"

    def test_completely_invalid_json_raises(self, filler) -> None:
        with pytest.raises(ProviderError, match="Could not find JSON"):
            filler._parse_response("This is not json at all")

    def test_empty_response_raises(self, filler) -> None:
        with pytest.raises(ProviderError):
            filler._parse_response("")

    def test_html_response_raises(self, filler) -> None:
        with pytest.raises(ProviderError):
            filler._parse_response("<!DOCTYPE html><html><body>Error</body></html>")

    def test_null_fields_preserved(self, filler) -> None:
        raw = json.dumps(
            {
                "fields": {
                    "A": {"content": "val", "type": "text"},
                    "B": None,
                    "C": {"content": "img prompt", "type": "image"},
                }
            }
        )
        result = filler._parse_response(raw)
        assert result["A"] is not None
        assert result["B"] is None
        assert result["C"]["type"] == "image"

    def test_image_prompt_field(self, filler) -> None:
        raw = json.dumps(
            {
                "fields": {
                    "Meaning": {
                        "content": "definition",
                        "type": "text",
                        "image_prompt": "a picture of something",
                    }
                }
            }
        )
        result = filler._parse_response(raw)
        assert result["Meaning"]["image_prompt"] == "a picture of something"


class TestToHtml:
    """Tests for FieldFiller._to_html."""

    def test_newlines_converted(self) -> None:
        assert FieldFiller._to_html("line1\nline2") == "line1<br>line2"

    def test_multiple_newlines(self) -> None:
        assert FieldFiller._to_html("a\n\nb") == "a<br><br>b"

    def test_already_html_untouched(self) -> None:
        html = "word<br>definition"
        assert FieldFiller._to_html(html) == html

    def test_html_with_p_tags_untouched(self) -> None:
        html = "<p>paragraph</p>"
        assert FieldFiller._to_html(html) == html

    def test_html_with_div_untouched(self) -> None:
        html = "<div>content</div>"
        assert FieldFiller._to_html(html) == html

    def test_empty_string(self) -> None:
        assert FieldFiller._to_html("") == ""

    def test_none_passthrough(self) -> None:
        assert FieldFiller._to_html(None) is None

    def test_no_newlines_unchanged(self) -> None:
        assert FieldFiller._to_html("just text") == "just text"


class TestGenerateAndParse:
    """Tests for FieldFiller._generate_and_parse retry logic."""

    def _make_filler(self):
        filler = FieldFiller.__new__(FieldFiller)
        filler._config = MagicMock()
        return filler

    @patch("ai_field_filler.field_filler.create_text_provider")
    def test_succeeds_first_try(self, mock_create, filler) -> None:
        filler._config = MagicMock()
        mock_provider = MagicMock()
        mock_provider.generate.return_value = json.dumps(
            {"fields": {"A": {"content": "ok", "type": "text"}}}
        )
        mock_create.return_value = mock_provider
        result = filler._generate_and_parse("sys", "usr")
        assert result["A"]["content"] == "ok"
        assert mock_provider.generate.call_count == 1

    @patch("ai_field_filler.field_filler.create_text_provider")
    def test_retries_on_bad_json_then_succeeds(self, mock_create, filler) -> None:
        filler._config = MagicMock()
        mock_provider = MagicMock()
        # First call returns truncated JSON, second returns valid
        mock_provider.generate.side_effect = [
            '{"fields":{"A":{"content":"val"',
            json.dumps({"fields": {"A": {"content": "val", "type": "text"}}}),
        ]
        mock_create.return_value = mock_provider
        result = filler._generate_and_parse("sys", "usr")
        assert result["A"]["content"] == "val"
        assert mock_provider.generate.call_count == 2

    @patch("ai_field_filler.field_filler.create_text_provider")
    def test_raises_after_all_retries_fail(self, mock_create, filler) -> None:
        filler._config = MagicMock()
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "not json at all"
        mock_create.return_value = mock_provider
        with pytest.raises(ProviderError):
            filler._generate_and_parse("sys", "usr")
        assert mock_provider.generate.call_count == 2
