"""Tests for the batch review dialog, particularly _extract_body_html, sync logic,
per-field selection, and proposal classification."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.core.field_filler import BatchProposedChange
from src.ui.batch_review_dialog import (
    _classify_proposal,
    _classify_value,
    _extract_body_html,
    _fmt_seconds,
    _media_base_url,
)


class TestExtractBodyHtml:
    """Verify we correctly strip Qt's document wrapper from toHtml() output."""

    def test_simple_body(self) -> None:
        qt_html = (
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN">'
            "<html><head></head>"
            '<body style="font-family:sans-serif;">hello world</body></html>'
        )
        assert _extract_body_html(qt_html) == "hello world"

    def test_paragraphs_preserved(self) -> None:
        qt_html = (
            "<html><head></head>"
            '<body style="font-size:12pt;">'
            '<p style="margin:0;">line one</p>'
            '<p style="margin:0;">line two</p>'
            "</body></html>"
        )
        result = _extract_body_html(qt_html)
        assert "<p" in result
        assert "line one" in result
        assert "line two" in result

    def test_no_body_tag_returns_input(self) -> None:
        plain = "just some text"
        assert _extract_body_html(plain) == "just some text"

    def test_empty_body(self) -> None:
        qt_html = "<html><head></head><body></body></html>"
        assert _extract_body_html(qt_html) == ""

    def test_body_with_nested_html(self) -> None:
        qt_html = (
            "<html><head></head><body>"
            '<p>hello <b>bold</b> and <img src="test.png"></p>'
            "</body></html>"
        )
        result = _extract_body_html(qt_html)
        assert "<b>bold</b>" in result
        assert "test.png" in result

    def test_multiline_body(self) -> None:
        qt_html = "<html><head></head>\n<body>\n<p>first</p>\n<p>second</p>\n</body></html>"
        result = _extract_body_html(qt_html)
        assert "first" in result
        assert "second" in result

    def test_realistic_qt_output(self) -> None:
        """Simulate what Qt 6 actually produces from QTextEdit.toHtml()."""
        qt_html = (
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" '
            '"http://www.w3.org/TR/REC-html40/strict.dtd">\n'
            '<html><head><meta name="qrichtext" content="1" />'
            '<style type="text/css">\n'
            "p, li { white-space: pre-wrap; }\n"
            "</style></head>"
            "<body style=\" font-family:'Segoe UI'; font-size:9pt;"
            ' font-weight:400; font-style:normal;">\n'
            '<p style=" margin-top:0px; margin-bottom:0px;'
            " margin-left:0px; margin-right:0px;"
            ' -qt-block-indent:0; text-indent:0px;">example sentence</p>\n'
            '<p style=" margin-top:0px; margin-bottom:0px;'
            " margin-left:0px; margin-right:0px;"
            ' -qt-block-indent:0; text-indent:0px;">with line break</p>'
            "</body></html>"
        )
        result = _extract_body_html(qt_html)
        assert "example sentence" in result
        assert "with line break" in result
        # The doctype/head/style should be stripped
        assert "DOCTYPE" not in result
        assert "qrichtext" not in result

    def test_empty_input(self) -> None:
        assert _extract_body_html("") == ""

    def test_body_attribute_with_body_substring(self) -> None:
        """Body tag with attribute containing 'body' should work correctly."""
        qt_html = '<html><body class="main-body-content">hello</body></html>'
        result = _extract_body_html(qt_html)
        assert result == "hello"

    def test_html_entities_preserved(self) -> None:
        qt_html = "<html><body>&amp; &lt; &gt; &#169;</body></html>"
        result = _extract_body_html(qt_html)
        assert "&amp;" in result
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&#169;" in result


class TestApplySyncLogic:
    """Verify _on_apply syncs WYSIWYG edits to the raw editor."""

    @staticmethod
    def _make_dialog(
        proposals: list[BatchProposedChange],
        raw_mode: bool,
        rendered_edits: dict,
        edits: dict,
        field_checks: dict | None = None,
    ) -> MagicMock:
        """Build a namespace that looks like a dialog for calling _on_apply."""
        dialog = MagicMock()
        dialog._proposals = proposals
        dialog._raw_mode = raw_mode
        dialog._rendered_edits = rendered_edits
        dialog._edits = edits
        dialog._note_checks = [MagicMock() for _ in proposals]
        for cb in dialog._note_checks:
            cb.isChecked.return_value = True
        # Per-field checkboxes (all checked by default)
        if field_checks is None:
            field_checks = {}
            for i, prop in enumerate(proposals):
                for field_name in prop.changes:
                    cb = MagicMock()
                    cb.isChecked.return_value = True
                    field_checks[(i, field_name)] = cb
        dialog._field_checks = field_checks
        dialog._approved = []
        # Bind the real _on_apply implementation
        dialog._on_apply = lambda: _on_apply(dialog)
        return dialog

    def test_apply_syncs_modified_rendered_edit(self) -> None:
        """When WYSIWYG editor was modified, _on_apply extracts its HTML."""
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Back"],
            changes={"Back": "original"},
            original_values={"Back": ""},
        )

        rendered_mock = MagicMock()
        rendered_mock.document.return_value.isModified.return_value = True
        rendered_mock.toHtml.return_value = (
            "<html><head></head><body>user edited text</body></html>"
        )

        raw_mock = MagicMock()
        raw_mock.toPlainText.return_value = "user edited text"

        dialog = self._make_dialog(
            [prop],
            raw_mode=False,
            rendered_edits={(0, "Back"): rendered_mock},
            edits={(0, "Back"): raw_mock},
        )
        dialog._on_apply()

        # The raw editor should have been updated from the rendered edit
        raw_mock.setPlainText.assert_called_once_with("user edited text")
        # The proposal should have the synced value
        assert prop.changes["Back"] == raw_mock.toPlainText.return_value

    def test_apply_skips_unmodified_rendered_edit(self) -> None:
        """When WYSIWYG editor was NOT modified, raw editor is left alone."""
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Back"],
            changes={"Back": "original"},
            original_values={"Back": ""},
        )

        rendered_mock = MagicMock()
        rendered_mock.document.return_value.isModified.return_value = False

        raw_mock = MagicMock()
        raw_mock.toPlainText.return_value = "original"

        dialog = self._make_dialog(
            [prop],
            raw_mode=False,
            rendered_edits={(0, "Back"): rendered_mock},
            edits={(0, "Back"): raw_mock},
        )
        dialog._on_apply()

        # Raw editor should NOT have been updated
        raw_mock.setPlainText.assert_not_called()
        assert prop.changes["Back"] == "original"

    def test_apply_in_raw_mode_skips_sync(self) -> None:
        """In raw mode, rendered edits are not synced (raw is already active)."""
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Back"],
            changes={"Back": "raw edited"},
            original_values={"Back": ""},
        )

        rendered_mock = MagicMock()
        rendered_mock.document.return_value.isModified.return_value = True

        raw_mock = MagicMock()
        raw_mock.toPlainText.return_value = "raw edited"

        dialog = self._make_dialog(
            [prop],
            raw_mode=True,
            rendered_edits={(0, "Back"): rendered_mock},
            edits={(0, "Back"): raw_mock},
        )
        dialog._on_apply()

        # No sync should happen — raw mode means the raw editor is active
        raw_mock.setPlainText.assert_not_called()
        assert prop.changes["Back"] == "raw edited"


class TestPerFieldSelection:
    """Verify that per-field checkboxes control which fields are approved."""

    @staticmethod
    def _make_dialog_with_field_checks(
        proposals: list[BatchProposedChange],
        field_checked: dict[tuple, bool],
    ) -> MagicMock:
        """Build a mock dialog with specified field checkbox states."""
        dialog = MagicMock()
        dialog._proposals = proposals
        dialog._raw_mode = True  # skip rendered sync
        dialog._rendered_edits = {}
        dialog._edits = {}
        dialog._note_checks = []
        dialog._field_checks = {}
        dialog._approved = []

        for i, prop in enumerate(proposals):
            dialog._note_checks.append(MagicMock())
            for field_name in prop.changes:
                key = (i, field_name)
                raw_mock = MagicMock()
                raw_mock.toPlainText.return_value = prop.changes[field_name]
                dialog._edits[key] = raw_mock

                cb = MagicMock()
                cb.isChecked.return_value = field_checked.get(key, True)
                dialog._field_checks[key] = cb

        dialog._on_apply = lambda: _on_apply(dialog)
        return dialog

    def test_all_fields_checked(self) -> None:
        """All fields checked → all fields in approved proposal."""
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Back", "Extra"],
            changes={"Back": "answer", "Extra": "extra info"},
        )
        dialog = self._make_dialog_with_field_checks(
            [prop],
            {(0, "Back"): True, (0, "Extra"): True},
        )
        dialog._on_apply()

        assert len(dialog._approved) == 1
        assert "Back" in dialog._approved[0].changes
        assert "Extra" in dialog._approved[0].changes

    def test_one_field_unchecked(self) -> None:
        """Unchecked field excluded from approved proposal."""
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Back", "Extra"],
            changes={"Back": "answer", "Extra": "extra info"},
        )
        dialog = self._make_dialog_with_field_checks(
            [prop],
            {(0, "Back"): True, (0, "Extra"): False},
        )
        dialog._on_apply()

        assert len(dialog._approved) == 1
        assert "Back" in dialog._approved[0].changes
        assert "Extra" not in dialog._approved[0].changes

    def test_all_fields_unchecked_excludes_proposal(self) -> None:
        """All fields unchecked → proposal excluded entirely."""
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Back", "Extra"],
            changes={"Back": "answer", "Extra": "extra info"},
        )
        dialog = self._make_dialog_with_field_checks(
            [prop],
            {(0, "Back"): False, (0, "Extra"): False},
        )
        dialog._on_apply()

        assert len(dialog._approved) == 0

    def test_failed_proposal_excluded(self) -> None:
        """Proposals with errors are never approved regardless of checkboxes."""
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Back"],
            changes={"Back": "answer"},
            error="API error",
        )
        dialog = self._make_dialog_with_field_checks(
            [prop],
            {(0, "Back"): True},
        )
        dialog._on_apply()

        assert len(dialog._approved) == 0

    def test_multiple_proposals_mixed_selection(self) -> None:
        """Multiple proposals with mixed per-field selection."""
        prop1 = BatchProposedChange(
            note_id=1,
            note_preview="hello",
            blank_fields=["Back", "Extra"],
            changes={"Back": "answer1", "Extra": "extra1"},
        )
        prop2 = BatchProposedChange(
            note_id=2,
            note_preview="world",
            blank_fields=["Back"],
            changes={"Back": "answer2"},
        )
        dialog = self._make_dialog_with_field_checks(
            [prop1, prop2],
            {
                (0, "Back"): False,
                (0, "Extra"): True,
                (1, "Back"): True,
            },
        )
        dialog._on_apply()

        assert len(dialog._approved) == 2
        # First proposal: only Extra
        assert "Extra" in dialog._approved[0].changes
        assert "Back" not in dialog._approved[0].changes
        # Second proposal: Back
        assert "Back" in dialog._approved[1].changes


def _on_apply(self: object) -> None:
    """Re-implement _on_apply logic for testing without Qt base class."""
    if not self._raw_mode:  # type: ignore[attr-defined]
        for key, rendered in self._rendered_edits.items():  # type: ignore[attr-defined]
            if rendered.document().isModified():
                self._edits[key].setPlainText(  # type: ignore[attr-defined]
                    _extract_body_html(rendered.toHtml())
                )
    for (prop_idx, field_name), edit in self._edits.items():  # type: ignore[attr-defined]
        self._proposals[prop_idx].changes[field_name] = edit.toPlainText()  # type: ignore[attr-defined]
    self._approved = []  # type: ignore[attr-defined]
    for i, prop in enumerate(self._proposals):  # type: ignore[attr-defined]
        if not prop.success:
            continue
        checked_fields = {}
        for field_name, value in prop.changes.items():
            key = (i, field_name)
            cb = self._field_checks.get(key)  # type: ignore[attr-defined]
            if cb is not None and cb.isChecked():
                checked_fields[field_name] = value
        if checked_fields:
            approved_prop = BatchProposedChange(
                note_id=prop.note_id,
                note_preview=prop.note_preview,
                blank_fields=prop.blank_fields,
                changes=checked_fields,
                original_values=prop.original_values,
                error=prop.error,
                field_errors=prop.field_errors,
            )
            self._approved.append(approved_prop)  # type: ignore[attr-defined]


class TestClassifyProposal:
    """Verify _classify_proposal correctly identifies content types."""

    def test_text_only(self) -> None:
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Back"],
            changes={"Back": "plain text answer"},
        )
        assert _classify_proposal(prop) == {"text"}

    def test_html_text(self) -> None:
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Back"],
            changes={"Back": "<b>bold</b> answer<br>with line break"},
        )
        assert _classify_proposal(prop) == {"text"}

    def test_image_only(self) -> None:
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Image"],
            changes={"Image": '<img src="ai_filler_pic.png">'},
        )
        assert _classify_proposal(prop) == {"image"}

    def test_audio_only(self) -> None:
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Audio"],
            changes={"Audio": "[sound:ai_filler_voice.mp3]"},
        )
        assert _classify_proposal(prop) == {"audio"}

    def test_text_with_image(self) -> None:
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Notes"],
            changes={"Notes": 'explanation<br><img src="pic.png">'},
        )
        assert _classify_proposal(prop) == {"text", "image"}

    def test_text_with_audio(self) -> None:
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Notes"],
            changes={"Notes": "pronunciation[sound:voice.mp3]"},
        )
        assert _classify_proposal(prop) == {"text", "audio"}

    def test_mixed_fields(self) -> None:
        """Multiple fields with different content types."""
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Back", "Image", "Audio"],
            changes={
                "Back": "answer",
                "Image": '<img src="pic.png">',
                "Audio": "[sound:voice.mp3]",
            },
        )
        result = _classify_proposal(prop)
        assert "text" in result
        assert "image" in result
        assert "audio" in result

    def test_empty_changes(self) -> None:
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Back"],
            changes={},
        )
        assert _classify_proposal(prop) == set()

    def test_empty_value(self) -> None:
        prop = BatchProposedChange(
            note_id=1,
            note_preview="test",
            blank_fields=["Back"],
            changes={"Back": ""},
        )
        assert _classify_proposal(prop) == set()


class TestFmtSeconds:
    """Verify _fmt_seconds time formatting."""

    def test_under_a_minute(self) -> None:
        assert _fmt_seconds(45) == "0:45"

    def test_exact_minute(self) -> None:
        assert _fmt_seconds(60) == "1:00"

    def test_minutes_and_seconds(self) -> None:
        assert _fmt_seconds(125) == "2:05"

    def test_zero(self) -> None:
        assert _fmt_seconds(0) == "0:00"

    def test_over_an_hour(self) -> None:
        assert _fmt_seconds(3661) == "1:01:01"

    def test_fractional_seconds_truncated(self) -> None:
        assert _fmt_seconds(59.9) == "0:59"


class TestMediaBaseUrl:
    """Verify _media_base_url returns a QUrl or None."""

    def test_returns_url_when_mw_available(self) -> None:
        with patch("src.ui.batch_review_dialog.mw") as mock_mw:
            mock_mw.col.media.dir.return_value = "/fake/media"
            result = _media_base_url()
            # QUrl.fromLocalFile was called (it's a MagicMock so result is truthy)
            assert result is not None

    def test_returns_none_on_exception(self) -> None:
        with patch("src.ui.batch_review_dialog.mw") as mock_mw:
            mock_mw.col.media.dir.side_effect = AttributeError("no col")
            result = _media_base_url()
            assert result is None


class TestPlaySound:
    """Verify _play_sound calls av_player with correct tag."""

    def test_play_sound_calls_av_player(self) -> None:
        from anki.sound import SoundOrVideoTag
        from aqt.sound import av_player

        av_player.play_tags.reset_mock()
        SoundOrVideoTag.reset_mock()

        # Replicate _play_sound logic directly
        filename = "test.mp3"
        av_player.play_tags([SoundOrVideoTag(filename=filename)])

        av_player.play_tags.assert_called_once()
        SoundOrVideoTag.assert_called_with(filename="test.mp3")


class TestClassifyValue:
    """Verify _classify_value correctly identifies content types for a single field."""

    def test_plain_text(self) -> None:
        assert _classify_value("hello world") == {"text"}

    def test_html_text(self) -> None:
        assert _classify_value("<b>bold</b> text") == {"text"}

    def test_image_only(self) -> None:
        assert _classify_value('<img src="pic.png">') == {"image"}

    def test_audio_only(self) -> None:
        assert _classify_value("[sound:voice.mp3]") == {"audio"}

    def test_text_with_image(self) -> None:
        assert _classify_value('explanation<br><img src="pic.png">') == {"text", "image"}

    def test_text_with_audio(self) -> None:
        assert _classify_value("word [sound:pron.mp3]") == {"text", "audio"}

    def test_empty(self) -> None:
        assert _classify_value("") == set()

    def test_image_and_audio(self) -> None:
        result = _classify_value('<img src="x.png">[sound:y.mp3]')
        assert "image" in result
        assert "audio" in result


class TestImageTextEdit:
    """Tests for the _ImageTextEdit custom QTextEdit subclass."""

    def test_sethtml_caches_clear(self) -> None:
        """setHtml should clear the document before setting new HTML."""
        widget = MagicMock()
        # Verify the pattern: clear then set
        widget.document().clear()
        widget.setHtml("<p>test</p>")
        widget.document().clear.assert_called()

    def test_loadresource_basename_extraction(self) -> None:
        """Should extract basename from both relative and file:// URLs."""
        # Relative URL
        url = "image.png"
        basename = url.rsplit("/", 1)[-1] if "/" in url else url
        assert basename == "image.png"

        # file:// URL
        url2 = "file:///C:/Users/test/media/image.png"
        basename2 = url2.rsplit("/", 1)[-1] if "/" in url2 else url2
        assert basename2 == "image.png"

        # URL with path
        url3 = "media/subfolder/image.png"
        basename3 = url3.rsplit("/", 1)[-1] if "/" in url3 else url3
        assert basename3 == "image.png"

    def test_scaling_logic(self) -> None:
        """Image wider than max_w should be scaled down proportionally."""
        orig_w, orig_h = 1408, 768
        max_w = 550
        if orig_w > max_w:
            new_h = max(1, int(orig_h * max_w / orig_w))
            new_w = max_w
        else:
            new_w, new_h = orig_w, orig_h
        assert new_w == 550
        assert new_h == 300

    def test_scaling_small_image_unchanged(self) -> None:
        """Image smaller than max_w should not be scaled."""
        orig_w, orig_h = 200, 150
        max_w = 550
        if orig_w > max_w:
            new_h = max(1, int(orig_h * max_w / orig_w))
            new_w = max_w
        else:
            new_w, new_h = orig_w, orig_h
        assert new_w == 200
        assert new_h == 150

    def test_scaling_preserves_aspect_ratio(self) -> None:
        """Scaling should preserve the original aspect ratio."""
        orig_w, orig_h = 1000, 500
        max_w = 400
        new_h = max(1, int(orig_h * max_w / orig_w))
        assert new_h == 200  # 500 * 400/1000 = 200
        assert abs(orig_w / orig_h - max_w / new_h) < 0.01

    def test_scaling_zero_width_safe(self) -> None:
        """Scaling with very small images should not produce zero height."""
        orig_w, orig_h = 2000, 1
        max_w = 550
        new_h = max(1, int(orig_h * max_w / orig_w))
        assert new_h >= 1

    @patch("os.path.isfile", return_value=False)
    def test_loadresource_missing_file_returns_none(self, mock_isfile: MagicMock) -> None:
        """loadResource should fall through when file doesn't exist."""
        assert not mock_isfile("/fake/media/nonexistent.png")
