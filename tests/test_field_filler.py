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

    def test_rich_type_parsed(self, filler) -> None:
        raw = json.dumps(
            {
                "fields": {
                    "Notes": {
                        "content": "Definition\n\n{{IMAGE: a cat}}\n\n{{AUDIO: hello}}",
                        "type": "rich",
                    }
                }
            }
        )
        result = filler._parse_response(raw)
        assert result["Notes"]["type"] == "rich"
        assert "{{IMAGE: a cat}}" in result["Notes"]["content"]
        assert "{{AUDIO: hello}}" in result["Notes"]["content"]

    def test_text_type_with_flags_parsed(self, filler) -> None:
        raw = json.dumps(
            {
                "fields": {
                    "Meaning": {
                        "content": "To eat\n{{IMAGE: eating food}}",
                        "type": "text",
                    }
                }
            }
        )
        result = filler._parse_response(raw)
        assert result["Meaning"]["type"] == "text"
        assert "{{IMAGE: eating food}}" in result["Meaning"]["content"]


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


class TestHasFlags:
    """Tests for FieldFiller._has_flags."""

    def test_detects_image_flag(self, filler) -> None:
        assert filler._has_flags("text {{IMAGE: a cat}} more text")

    def test_detects_audio_flag(self, filler) -> None:
        assert filler._has_flags("say {{AUDIO: hello}}")

    def test_no_flags(self, filler) -> None:
        assert not filler._has_flags("plain text without any flags")

    def test_partial_flag_not_matched(self, filler) -> None:
        assert not filler._has_flags("{{IMAGE missing colon}}")
        assert not filler._has_flags("{{UNKNOWN: something}}")

    def test_empty_string(self, filler) -> None:
        assert not filler._has_flags("")

    def test_multiple_flags(self, filler) -> None:
        content = "{{IMAGE: cat}} and {{AUDIO: meow}} and {{IMAGE: dog}}"
        assert filler._has_flags(content)


class TestRenderFlags:
    """Tests for FieldFiller._render_flags."""

    def _make_filler(self) -> FieldFiller:
        filler = FieldFiller.__new__(FieldFiller)
        filler._config = MagicMock()
        filler._config.get_active_image_provider.return_value = None
        filler._config.get_active_tts_provider.return_value = None
        return filler

    def test_no_flags_passthrough(self) -> None:
        filler = self._make_filler()
        html, errors = filler._render_flags("plain text\nnewline", "Field")
        assert html == "plain text<br>newline"
        assert errors == []

    def test_image_flag_replaced(self) -> None:
        filler = self._make_filler()
        img_cfg = MagicMock()
        filler._config.get_active_image_provider.return_value = img_cfg

        with patch("ai_field_filler.field_filler.create_image_provider") as mock_factory:
            mock_prov = MagicMock()
            mock_prov.generate_image.return_value = b"\x89PNG_fake"
            mock_factory.return_value = mock_prov

            with patch("ai_field_filler.field_filler.MediaHandler.save_image") as mock_save:
                mock_save.return_value = '<img src="ai_filler_test.png">'
                html, errors = filler._render_flags(
                    "Before\n{{IMAGE: a cute cat}}\nAfter", "TestField"
                )

        assert errors == []
        assert '<img src="ai_filler_test.png">' in html
        assert "Before<br>" in html
        assert "<br>After" in html
        mock_prov.generate_image.assert_called_once_with("a cute cat")

    def test_audio_flag_replaced(self) -> None:
        filler = self._make_filler()
        tts_cfg = MagicMock()
        filler._config.get_active_tts_provider.return_value = tts_cfg

        with patch("ai_field_filler.field_filler.create_tts_provider") as mock_factory:
            mock_prov = MagicMock()
            mock_prov.synthesize.return_value = b"\xff\xfb\x90\x00" + b"\x00" * 50
            mock_factory.return_value = mock_prov

            with patch("ai_field_filler.field_filler.MediaHandler.save_audio") as mock_save:
                mock_save.return_value = "[sound:ai_filler_test.mp3]"
                html, errors = filler._render_flags("Listen: {{AUDIO: konnichiwa}}", "TestField")

        assert errors == []
        assert "[sound:ai_filler_test.mp3]" in html
        assert "Listen: " in html
        mock_prov.synthesize.assert_called_once_with("konnichiwa", context="")

    def test_mixed_flags(self) -> None:
        filler = self._make_filler()
        img_cfg = MagicMock()
        tts_cfg = MagicMock()
        filler._config.get_active_image_provider.return_value = img_cfg
        filler._config.get_active_tts_provider.return_value = tts_cfg

        with (
            patch("ai_field_filler.field_filler.create_image_provider") as mock_img_f,
            patch("ai_field_filler.field_filler.create_tts_provider") as mock_tts_f,
            patch("ai_field_filler.field_filler.MediaHandler.save_image") as mock_save_img,
            patch("ai_field_filler.field_filler.MediaHandler.save_audio") as mock_save_aud,
        ):
            mock_img_prov = MagicMock()
            mock_img_prov.generate_image.return_value = b"PNG"
            mock_img_f.return_value = mock_img_prov
            mock_save_img.return_value = '<img src="pic.png">'

            mock_tts_prov = MagicMock()
            mock_tts_prov.synthesize.return_value = b"\xff\xfb" + b"\x00" * 50
            mock_tts_f.return_value = mock_tts_prov
            mock_save_aud.return_value = "[sound:voice.mp3]"

            content = (
                "Word meaning\n{{IMAGE: illustration}}\nPronunciation:\n{{AUDIO: hello}}\nDone"
            )
            html, errors = filler._render_flags(content, "Rich")

        assert errors == []
        assert '<img src="pic.png">' in html
        assert "[sound:voice.mp3]" in html
        assert "Word meaning" in html
        assert "Done" in html

    def test_image_failure_removes_flag(self) -> None:
        filler = self._make_filler()
        img_cfg = MagicMock()
        filler._config.get_active_image_provider.return_value = img_cfg

        with patch("ai_field_filler.field_filler.create_image_provider") as mock_factory:
            mock_prov = MagicMock()
            mock_prov.generate_image.side_effect = ProviderError("safety filter")
            mock_factory.return_value = mock_prov

            html, errors = filler._render_flags("Before\n{{IMAGE: bad prompt}}\nAfter", "Field")

        assert len(errors) == 1
        assert "safety filter" in errors[0]
        assert "bad prompt" in errors[0]
        # Flag removed, text preserved
        assert "{{IMAGE" not in html
        assert "Before" in html
        assert "After" in html

    def test_audio_failure_removes_flag(self) -> None:
        filler = self._make_filler()
        tts_cfg = MagicMock()
        filler._config.get_active_tts_provider.return_value = tts_cfg

        with patch("ai_field_filler.field_filler.create_tts_provider") as mock_factory:
            mock_prov = MagicMock()
            mock_prov.synthesize.side_effect = ProviderError("TTS error")
            mock_factory.return_value = mock_prov

            html, errors = filler._render_flags("Say {{AUDIO: test}}", "Field")

        assert len(errors) == 1
        assert "TTS error" in errors[0]
        assert "{{AUDIO" not in html
        assert "Say " in html

    def test_no_provider_configured_removes_flag(self) -> None:
        filler = self._make_filler()
        # Providers return None (disabled)
        html, errors = filler._render_flags(
            "See {{IMAGE: something}} and hear {{AUDIO: text}}", "Field"
        )
        assert errors == []
        assert "{{IMAGE" not in html
        assert "{{AUDIO" not in html
        assert "See " in html
        assert " and hear " in html

    def test_empty_flag_payload_removed(self) -> None:
        filler = self._make_filler()
        html, errors = filler._render_flags("Text {{IMAGE:  }} more", "Field")
        assert "{{IMAGE" not in html
        assert "Text " in html
        assert " more" in html

    def test_multiple_image_flags_indexed(self) -> None:
        """Each flag gets a unique part name suffix for file naming."""
        filler = self._make_filler()
        img_cfg = MagicMock()
        filler._config.get_active_image_provider.return_value = img_cfg

        part_names: list[str] = []

        with patch("ai_field_filler.field_filler.create_image_provider") as mock_factory:
            mock_prov = MagicMock()
            mock_prov.generate_image.return_value = b"PNG"
            mock_factory.return_value = mock_prov

            def track_save(img_bytes: bytes, name: str) -> str:
                part_names.append(name)
                return f'<img src="{name}.png">'

            with patch(
                "ai_field_filler.field_filler.MediaHandler.save_image",
                side_effect=track_save,
            ):
                filler._render_flags("{{IMAGE: cat}} and {{IMAGE: dog}}", "Field")

        assert len(part_names) == 2
        assert part_names[0] == "Field_p1"
        assert part_names[1] == "Field_p2"

    def test_partial_failure_keeps_other_flags(self) -> None:
        """One flag fails, others still render."""
        filler = self._make_filler()
        img_cfg = MagicMock()
        filler._config.get_active_image_provider.return_value = img_cfg

        call_count = 0

        with patch("ai_field_filler.field_filler.create_image_provider") as mock_factory:
            mock_prov = MagicMock()

            def generate_side_effect(prompt: str) -> bytes:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ProviderError("blocked")
                return b"PNG"

            mock_prov.generate_image.side_effect = generate_side_effect
            mock_factory.return_value = mock_prov

            with patch(
                "ai_field_filler.field_filler.MediaHandler.save_image",
                return_value='<img src="ok.png">',
            ):
                html, errors = filler._render_flags("{{IMAGE: bad}} middle {{IMAGE: good}}", "F")

        assert len(errors) == 1
        assert "blocked" in errors[0]
        assert '<img src="ok.png">' in html
        assert "middle" in html

    def test_html_content_newlines_not_converted(self) -> None:
        """Content with HTML tags should not have newlines converted to <br>."""
        filler = self._make_filler()
        html, errors = filler._render_flags(
            "<p>Definition</p>\n{{IMAGE: cat}}\n<p>Example</p>", "Field"
        )
        assert errors == []
        # _to_html detects <p> tags and leaves newlines alone
        assert "<br>" not in html
        assert "<p>Definition</p>" in html
        assert "<p>Example</p>" in html

    def test_html_with_br_tags_not_double_converted(self) -> None:
        """Content that already has <br> tags should be left untouched."""
        filler = self._make_filler()
        html, errors = filler._render_flags("Line one<br>{{IMAGE: cat}}<br>Line two", "Field")
        assert errors == []
        assert html == "Line one<br><br>Line two"


class TestRenderRichContent:
    """Tests for FieldFiller._render_rich_content."""

    def _make_filler(self) -> FieldFiller:
        filler = FieldFiller.__new__(FieldFiller)
        filler._config = MagicMock()
        filler._config.get_active_image_provider.return_value = None
        filler._config.get_active_tts_provider.return_value = None
        return filler

    def test_flags_with_legacy_image_prompt(self) -> None:
        """Both inline flags and legacy image_prompt should be processed."""
        filler = self._make_filler()
        img_cfg = MagicMock()
        filler._config.get_active_image_provider.return_value = img_cfg

        with (
            patch("ai_field_filler.field_filler.create_image_provider") as mock_factory,
            patch("ai_field_filler.field_filler.MediaHandler.save_image") as mock_save,
        ):
            mock_prov = MagicMock()
            mock_prov.generate_image.return_value = b"\x89PNG"
            mock_factory.return_value = mock_prov

            call_idx = 0

            def save_side_effect(img_bytes: bytes, name: str) -> str:
                nonlocal call_idx
                call_idx += 1
                return f'<img src="img{call_idx}.png">'

            mock_save.side_effect = save_side_effect

            field_data = {
                "content": "Text\n{{IMAGE: inline pic}}",
                "type": "rich",
                "image_prompt": "appended pic",
            }
            html, errors = filler._render_rich_content(field_data["content"], "Notes", field_data)

        assert errors == []
        assert '<img src="img1.png">' in html  # inline flag
        assert '<img src="img2.png">' in html  # legacy image_prompt
        assert "Text" in html

    def test_legacy_image_prompt_failure_reported(self) -> None:
        """Legacy image_prompt failure should be reported in errors."""
        filler = self._make_filler()
        img_cfg = MagicMock()
        filler._config.get_active_image_provider.return_value = img_cfg

        with patch("ai_field_filler.field_filler.create_image_provider") as mock_factory:
            mock_prov = MagicMock()
            mock_prov.generate_image.side_effect = ProviderError("quota exceeded")
            mock_factory.return_value = mock_prov

            field_data = {
                "content": "Just text",
                "type": "rich",
                "image_prompt": "some image",
            }
            html, errors = filler._render_rich_content(field_data["content"], "Notes", field_data)

        assert len(errors) == 1
        assert "quota exceeded" in errors[0]
        assert "Just text" in html


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
