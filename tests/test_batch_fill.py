"""Tests for batch fill logic."""

from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

from ai_field_filler.config_manager import ProviderConfig
from ai_field_filler.field_filler import (
    BatchFiller,
    BatchNoteItem,
    BatchProgress,
    BatchProposedChange,
    BatchResult,
)
from ai_field_filler.providers.base import ProviderError

_HTTP_URLOPEN = "ai_field_filler.providers.http.urllib.request.urlopen"

_FAKE_PROVIDER_CFG = ProviderConfig(
    provider_type="openai",
    api_url="https://fake.test/v1",
    api_key="test-key",
    text_model="gpt-4o",
    max_tokens=4096,
)


def _chat_response(fields_json: dict) -> str:
    """Wrap field data in an OpenAI chat completion response."""
    inner = json.dumps({"fields": fields_json})
    return json.dumps({"choices": [{"message": {"content": inner}}]})


def _mock_urlopen(response_data: str | bytes):
    mock_resp = MagicMock()
    if isinstance(response_data, str):
        response_data = response_data.encode("utf-8")
    mock_resp.read.return_value = response_data
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_mock_note(nid: int, fields: dict[str, str], note_type: str = "Basic"):
    """Create a mock note object."""
    note = MagicMock()
    note.id = nid
    note.note_type.return_value = {"name": note_type}
    note.keys.return_value = list(fields.keys())
    note.__getitem__ = lambda self, k: fields[k]
    note.__setitem__ = lambda self, k, v: fields.__setitem__(k, v)
    note.__contains__ = lambda self, k: k in fields
    return note, fields


def _make_batch_filler(mock_mw: MagicMock) -> BatchFiller:
    """Create a BatchFiller with mocked config."""
    filler = BatchFiller()
    mock_config = MagicMock()
    mock_config.get_field_instructions.return_value = {}
    mock_config.get_active_text_provider.return_value = _FAKE_PROVIDER_CFG
    mock_config.get_active_tts_provider.return_value = None
    mock_config.get_active_image_provider.return_value = None
    filler._config = mock_config
    filler._filler._config = mock_config
    return filler


def _make_errors(n: int) -> list:
    """Create n distinct HTTPError objects."""
    return [
        urllib.error.HTTPError("https://api.test", 500, "err", {}, BytesIO(b"err"))
        for _ in range(n)
    ]


class TestBatchFiller:
    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_basic_batch(self, mock_mw: MagicMock, mock_urlopen: MagicMock) -> None:
        """Process two notes, both succeed."""
        fields1 = {"Front": "hello", "Back": ""}
        fields2 = {"Front": "world", "Back": ""}
        note1, _ = _make_mock_note(1, fields1)
        note2, _ = _make_mock_note(2, fields2)

        mock_mw.col.get_note.side_effect = [note1, note2]

        response = _chat_response({"Back": {"content": "answer", "type": "text"}})
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        items = [BatchNoteItem(note_id=1), BatchNoteItem(note_id=2)]
        result = filler.run(items, target_fields=["Back"])

        assert result.total == 2
        assert result.succeeded == 2
        assert result.failed == 0
        assert result.elapsed_seconds > 0

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_skips_already_filled(self, mock_mw: MagicMock, mock_urlopen: MagicMock) -> None:
        """Notes with no blank target fields are skipped."""
        fields = {"Front": "hello", "Back": "already filled"}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        filler = _make_batch_filler(mock_mw)
        result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Back"])

        assert result.skipped == 1
        assert result.succeeded == 0
        mock_urlopen.assert_not_called()

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_dry_run(self, mock_mw: MagicMock, mock_urlopen: MagicMock) -> None:
        """Dry run doesn't call the AI."""
        fields = {"Front": "hello", "Back": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        filler = _make_batch_filler(mock_mw)
        result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Back"], dry_run=True)

        assert result.dry_run is True
        assert result.succeeded == 1
        mock_urlopen.assert_not_called()

    @patch("ai_field_filler.providers.http.time.sleep")
    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_error_collected_not_fatal(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock, _mock_sleep: MagicMock
    ) -> None:
        """Errors are collected without crashing the batch."""
        fields = {"Front": "hello", "Back": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        # Enough errors for all retries
        mock_urlopen.side_effect = _make_errors(10)

        filler = _make_batch_filler(mock_mw)
        result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Back"])

        assert result.failed == 1
        assert result.succeeded == 0
        assert len(result.failures) == 1
        assert result.failures[0].note_id == 1
        assert "500" in result.failures[0].error

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_cancellation(self, mock_mw: MagicMock, mock_urlopen: MagicMock) -> None:
        """Cancellation stops after the current note completes."""
        fields = {"Front": "hello", "Back": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response({"Back": {"content": "x", "type": "text"}})
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)

        def cancel_after_first(p: BatchProgress) -> None:
            if p.completed == 1:
                filler.cancel()

        items = [BatchNoteItem(note_id=i) for i in range(5)]
        result = filler.run(items, target_fields=["Back"], on_progress=cancel_after_first)

        assert result.succeeded == 1
        assert result.skipped == 4

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_progress_callback(self, mock_mw: MagicMock, mock_urlopen: MagicMock) -> None:
        """Progress callback is called before and after each note."""
        fields1 = {"Front": "hello", "Back": ""}
        fields2 = {"Front": "world", "Back": ""}
        note1, _ = _make_mock_note(1, fields1)
        note2, _ = _make_mock_note(2, fields2)
        mock_mw.col.get_note.side_effect = [note1, note2]

        response = _chat_response({"Back": {"content": "x", "type": "text"}})
        mock_urlopen.return_value = _mock_urlopen(response)

        progress_calls: list[BatchProgress] = []
        filler = _make_batch_filler(mock_mw)
        filler.run(
            [BatchNoteItem(note_id=1), BatchNoteItem(note_id=2)],
            target_fields=["Back"],
            on_progress=progress_calls.append,
        )

        # 4 calls: "starting" + "done" for each of the 2 notes
        assert len(progress_calls) == 4
        # Before note 1
        assert progress_calls[0].completed == 0
        assert progress_calls[0].current_note_preview == "hello"
        # After note 1
        assert progress_calls[1].completed == 1
        # Before note 2
        assert progress_calls[2].completed == 1
        assert progress_calls[2].current_note_preview == "world"
        # After note 2
        assert progress_calls[3].completed == 2
        assert progress_calls[3].total == 2
        assert progress_calls[3].eta_seconds >= 0


class TestBatchDataclasses:
    def test_batch_note_item_defaults(self) -> None:
        item = BatchNoteItem(note_id=42)
        assert item.note_id == 42
        assert item.deck_name is None

    def test_batch_note_item_with_deck(self) -> None:
        item = BatchNoteItem(note_id=42, deck_name="Japanese")
        assert item.deck_name == "Japanese"

    def test_batch_result_defaults(self) -> None:
        r = BatchResult()
        assert r.total == 0
        assert r.succeeded == 0
        assert r.failed == 0
        assert r.skipped == 0
        assert r.elapsed_seconds == 0.0
        assert r.failures == []
        assert r.dry_run is False


class TestFilledFieldsNotOverwritten:
    """Verify that already-filled fields are never sent to the AI."""

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_partial_fill_only_targets_blank(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """Expression is filled, Back is blank — only Back is targeted."""
        fields = {"Expression": "hello", "Meaning": "world", "Back": ""}
        note, raw = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response({"Back": {"content": "answer", "type": "text"}})
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        result = filler.run(
            [BatchNoteItem(note_id=1)],
            target_fields=["Expression", "Meaning", "Back"],
        )

        assert result.succeeded == 1
        # Only Back should appear in proposals — Expression and Meaning were filled
        prop = result.proposals[0]
        assert "Back" in prop.blank_fields
        assert "Expression" not in prop.blank_fields
        assert "Meaning" not in prop.blank_fields
        # Original values must be untouched
        assert raw["Expression"] == "hello"
        assert raw["Meaning"] == "world"

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_all_fields_filled_skips_note(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """When every target field is already filled, the note is skipped."""
        fields = {"Front": "hello", "Back": "world"}
        note, raw = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        filler = _make_batch_filler(mock_mw)
        result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Front", "Back"])

        assert result.skipped == 1
        assert result.succeeded == 0
        mock_urlopen.assert_not_called()
        assert raw["Front"] == "hello"
        assert raw["Back"] == "world"


class TestDryRunProposals:
    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_dry_run_shows_blank_fields_per_note(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """Dry run proposals list which fields would be targeted."""
        fields = {"Front": "hello", "Back": "", "Extra": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        filler = _make_batch_filler(mock_mw)
        result = filler.run(
            [BatchNoteItem(note_id=1)],
            target_fields=["Front", "Back", "Extra"],
            dry_run=True,
        )

        assert len(result.proposals) == 1
        prop = result.proposals[0]
        assert prop.blank_fields == ["Back", "Extra"]
        assert prop.changes == {}  # no AI was called
        assert prop.original_values == {"Back": "", "Extra": ""}
        mock_urlopen.assert_not_called()


class TestProposalsAndApply:
    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_proposals_populated_without_writing(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """Real run populates proposals but doesn't write to notes."""
        fields = {"Front": "hello", "Back": ""}
        note, raw = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response({"Back": {"content": "generated", "type": "text"}})
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Back"])

        assert result.succeeded == 1
        assert len(result.proposals) == 1
        prop = result.proposals[0]
        assert prop.changes == {"Back": "generated"}
        assert prop.original_values == {"Back": ""}
        # Note was NOT modified (no flush called yet)
        assert raw["Back"] == ""
        note.flush.assert_not_called()

    @patch("ai_field_filler.field_filler.mw")
    def test_apply_proposals_writes_to_notes(self, mock_mw: MagicMock) -> None:
        """apply_proposals writes approved changes and flushes."""
        fields = {"Front": "hello", "Back": ""}
        note, raw = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        prop = BatchProposedChange(
            note_id=1,
            note_preview="hello",
            blank_fields=["Back"],
            changes={"Back": "new content"},
        )

        filler = BatchFiller()
        applied = filler.apply_proposals([prop])

        assert applied == 1
        assert raw["Back"] == "new content"
        note.flush.assert_called_once()

    @patch("ai_field_filler.field_filler.mw")
    def test_apply_skips_failed_proposals(self, mock_mw: MagicMock) -> None:
        """Proposals with errors are not applied."""
        prop = BatchProposedChange(
            note_id=1,
            note_preview="hello",
            blank_fields=["Back"],
            error="API error",
        )

        filler = BatchFiller()
        applied = filler.apply_proposals([prop])

        assert applied == 0
        mock_mw.col.get_note.assert_not_called()

    @patch("ai_field_filler.field_filler.mw")
    def test_apply_edited_proposal(self, mock_mw: MagicMock) -> None:
        """Proposals with user-edited values apply the edited content."""
        fields = {"Front": "hello", "Back": ""}
        note, raw = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        prop = BatchProposedChange(
            note_id=1,
            note_preview="hello",
            blank_fields=["Back"],
            changes={"Back": "ai generated"},
            original_values={"Back": ""},
        )
        # Simulate user editing the value in the review dialog
        prop.changes["Back"] = "user edited value"

        filler = BatchFiller()
        applied = filler.apply_proposals([prop])

        assert applied == 1
        assert raw["Back"] == "user edited value"
        note.flush.assert_called_once()


class TestPartialFieldFailure:
    """Image/audio failures should not lose successfully generated text fields."""

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_image_failure_keeps_text_fields(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """When image generation fails, text fields are still returned."""
        fields = {"Front": "hello", "Back": "", "Image": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response(
            {
                "Back": {"content": "answer text", "type": "text"},
                "Image": {"content": "a cute cat", "type": "image"},
            }
        )
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        # Enable image provider so the code actually tries to generate
        img_cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://fake.test/v1",
            api_key="test-key",
            text_model="gpt-4o",
            max_tokens=4096,
            image_model="dall-e-3",
        )
        filler._config.get_active_image_provider.return_value = img_cfg

        # Make the image provider raise an error
        with patch("ai_field_filler.field_filler.create_image_provider") as mock_img_factory:
            mock_img_prov = MagicMock()
            mock_img_prov.generate_image.side_effect = ProviderError("safety filter block")
            mock_img_factory.return_value = mock_img_prov

            result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Back", "Image"])

        # Note should still succeed (partial)
        assert result.succeeded == 1
        assert result.failed == 0
        prop = result.proposals[0]
        assert prop.success is True
        # Text field was kept
        assert "Back" in prop.changes
        assert prop.changes["Back"] == "answer text"
        # Image field failed
        assert "Image" not in prop.changes
        assert "Image" in prop.field_errors
        assert "safety filter block" in prop.field_errors["Image"]
        assert "a cute cat" in prop.field_errors["Image"]

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_all_fields_fail_still_succeeds_with_field_errors(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """Even if all fields fail in _render_fields, the note is not marked as error."""
        fields = {"Front": "hello", "Image": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response({"Image": {"content": "a sunset", "type": "image"}})
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        img_cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://fake.test/v1",
            api_key="test-key",
            text_model="gpt-4o",
            max_tokens=4096,
            image_model="dall-e-3",
        )
        filler._config.get_active_image_provider.return_value = img_cfg

        with patch("ai_field_filler.field_filler.create_image_provider") as mock_img_factory:
            mock_img_prov = MagicMock()
            mock_img_prov.generate_image.side_effect = ProviderError("blocked")
            mock_img_factory.return_value = mock_img_prov

            result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Image"])

        assert result.succeeded == 1
        prop = result.proposals[0]
        assert prop.success is True
        assert prop.changes == {}
        assert "Image" in prop.field_errors

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_inline_image_failure_keeps_text(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """Text field with inline image_prompt: text kept, image skipped."""
        fields = {"Front": "hello", "Definition": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response(
            {
                "Definition": {
                    "content": "a friendly greeting",
                    "type": "text",
                    "image_prompt": "waving hand",
                }
            }
        )
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        img_cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://fake.test/v1",
            api_key="test-key",
            text_model="gpt-4o",
            max_tokens=4096,
            image_model="dall-e-3",
        )
        filler._config.get_active_image_provider.return_value = img_cfg

        with patch("ai_field_filler.field_filler.create_image_provider") as mock_img_factory:
            mock_img_prov = MagicMock()
            mock_img_prov.generate_image.side_effect = ProviderError("content policy")
            mock_img_factory.return_value = mock_img_prov

            result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Definition"])

        prop = result.proposals[0]
        assert prop.success is True
        # Text content preserved without inline image
        assert "Definition" in prop.changes
        assert "a friendly greeting" in prop.changes["Definition"]
        assert "<img" not in prop.changes["Definition"]
        # Warning about the inline image
        assert "Definition" in prop.field_errors
        assert "inline image failed" in prop.field_errors["Definition"]
        assert "waving hand" in prop.field_errors["Definition"]


class TestRichFieldBatch:
    """Integration tests for rich/flag-based fields through the batch pipeline."""

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_rich_field_text_only_flags(self, mock_mw: MagicMock, mock_urlopen: MagicMock) -> None:
        """Rich field with no providers configured — flags removed, text kept."""
        fields = {"Front": "hello", "Notes": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response(
            {
                "Notes": {
                    "content": "Meaning\n\n{{IMAGE: a cat}}\n\nMore text",
                    "type": "rich",
                }
            }
        )
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Notes"])

        assert result.succeeded == 1
        prop = result.proposals[0]
        assert prop.success is True
        assert "Notes" in prop.changes
        html = prop.changes["Notes"]
        # Flags removed (no provider), text and newlines rendered
        assert "{{IMAGE" not in html
        assert "Meaning" in html
        assert "More text" in html
        assert "<br>" in html

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_rich_field_with_image_provider(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """Rich field with image flag — image generated and inlined."""
        fields = {"Front": "hello", "Notes": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response(
            {
                "Notes": {
                    "content": "Definition\n{{IMAGE: illustration}}\nEnd",
                    "type": "rich",
                }
            }
        )
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        img_cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://fake.test/v1",
            api_key="test-key",
            text_model="gpt-4o",
            max_tokens=4096,
            image_model="dall-e-3",
        )
        filler._config.get_active_image_provider.return_value = img_cfg

        with (
            patch("ai_field_filler.field_filler.create_image_provider") as mock_img_factory,
            patch("ai_field_filler.field_filler.MediaHandler.save_image") as mock_save,
        ):
            mock_img_prov = MagicMock()
            mock_img_prov.generate_image.return_value = b"\x89PNG"
            mock_img_factory.return_value = mock_img_prov
            mock_save.return_value = '<img src="ai_filler_pic.png">'

            result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Notes"])

        prop = result.proposals[0]
        assert prop.success is True
        html = prop.changes["Notes"]
        assert '<img src="ai_filler_pic.png">' in html
        assert "Definition" in html
        assert "End" in html
        mock_img_prov.generate_image.assert_called_once_with("illustration")

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_text_field_with_flags_processed(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """A text field that contains flags should still process them."""
        fields = {"Front": "hello", "Back": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response(
            {
                "Back": {
                    "content": "Answer\n{{IMAGE: diagram}}",
                    "type": "text",
                }
            }
        )
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        img_cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://fake.test/v1",
            api_key="test-key",
            text_model="gpt-4o",
            max_tokens=4096,
            image_model="dall-e-3",
        )
        filler._config.get_active_image_provider.return_value = img_cfg

        with (
            patch("ai_field_filler.field_filler.create_image_provider") as mock_img_factory,
            patch("ai_field_filler.field_filler.MediaHandler.save_image") as mock_save,
        ):
            mock_img_prov = MagicMock()
            mock_img_prov.generate_image.return_value = b"\x89PNG"
            mock_img_factory.return_value = mock_img_prov
            mock_save.return_value = '<img src="inline.png">'

            result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Back"])

        prop = result.proposals[0]
        html = prop.changes["Back"]
        assert '<img src="inline.png">' in html
        assert "Answer" in html
        assert "{{IMAGE" not in html

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_rich_field_flag_failure_keeps_text(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """When a flag's media generation fails, text is kept and error reported."""
        fields = {"Front": "hello", "Notes": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response(
            {
                "Notes": {
                    "content": "Intro\n{{IMAGE: bad prompt}}\nConclusion",
                    "type": "rich",
                }
            }
        )
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        img_cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://fake.test/v1",
            api_key="test-key",
            text_model="gpt-4o",
            max_tokens=4096,
            image_model="dall-e-3",
        )
        filler._config.get_active_image_provider.return_value = img_cfg

        with patch("ai_field_filler.field_filler.create_image_provider") as mock_img_factory:
            mock_img_prov = MagicMock()
            mock_img_prov.generate_image.side_effect = ProviderError("content policy")
            mock_img_factory.return_value = mock_img_prov

            result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Notes"])

        prop = result.proposals[0]
        assert prop.success is True
        html = prop.changes["Notes"]
        # Text kept, flag removed
        assert "Intro" in html
        assert "Conclusion" in html
        assert "{{IMAGE" not in html
        # Error recorded
        assert "Notes" in prop.field_errors
        assert "content policy" in prop.field_errors["Notes"]

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_plain_text_without_flags_unchanged(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """Regular text fields without flags work exactly as before."""
        fields = {"Front": "hello", "Back": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response({"Back": {"content": "plain answer", "type": "text"}})
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Back"])

        prop = result.proposals[0]
        assert prop.changes == {"Back": "plain answer"}
        assert prop.field_errors == {}

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_rich_with_audio_flag(self, mock_mw: MagicMock, mock_urlopen: MagicMock) -> None:
        """Rich field with audio flag — TTS generated inline."""
        fields = {"Front": "hello", "Notes": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response(
            {
                "Notes": {
                    "content": "Pronunciation:\n{{AUDIO: konnichiwa}}",
                    "type": "rich",
                }
            }
        )
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        tts_cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://fake.test/v1",
            api_key="test-key",
            text_model="gpt-4o",
            max_tokens=4096,
            tts_model="tts-1",
            tts_voice="alloy",
        )
        filler._config.get_active_tts_provider.return_value = tts_cfg

        with (
            patch("ai_field_filler.field_filler.create_tts_provider") as mock_tts_factory,
            patch("ai_field_filler.field_filler.MediaHandler.save_audio") as mock_save,
        ):
            mock_tts_prov = MagicMock()
            mock_tts_prov.synthesize.return_value = b"\xff\xfb" + b"\x00" * 50
            mock_tts_factory.return_value = mock_tts_prov
            mock_save.return_value = "[sound:ai_filler_voice.mp3]"

            result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Notes"])

        prop = result.proposals[0]
        html = prop.changes["Notes"]
        assert "[sound:ai_filler_voice.mp3]" in html
        assert "Pronunciation:" in html
        assert "{{AUDIO" not in html

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_multiple_flag_errors_all_preserved(
        self, mock_mw: MagicMock, mock_urlopen: MagicMock
    ) -> None:
        """When multiple flags fail, all errors should be reported (not just the last)."""
        fields = {"Front": "hello", "Notes": ""}
        note, _ = _make_mock_note(1, fields)
        mock_mw.col.get_note.return_value = note

        response = _chat_response(
            {
                "Notes": {
                    "content": "Start\n{{IMAGE: bad pic}}\nMiddle\n{{AUDIO: bad speech}}\nEnd",
                    "type": "rich",
                }
            }
        )
        mock_urlopen.return_value = _mock_urlopen(response)

        filler = _make_batch_filler(mock_mw)
        img_cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://fake.test/v1",
            api_key="test-key",
            text_model="gpt-4o",
            max_tokens=4096,
            image_model="dall-e-3",
        )
        tts_cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://fake.test/v1",
            api_key="test-key",
            text_model="gpt-4o",
            max_tokens=4096,
            tts_model="tts-1",
            tts_voice="alloy",
        )
        filler._config.get_active_image_provider.return_value = img_cfg
        filler._config.get_active_tts_provider.return_value = tts_cfg

        with (
            patch("ai_field_filler.field_filler.create_image_provider") as mock_img_factory,
            patch("ai_field_filler.field_filler.create_tts_provider") as mock_tts_factory,
        ):
            mock_img_prov = MagicMock()
            mock_img_prov.generate_image.side_effect = ProviderError("image policy")
            mock_img_factory.return_value = mock_img_prov

            mock_tts_prov = MagicMock()
            mock_tts_prov.synthesize.side_effect = ProviderError("TTS quota")
            mock_tts_factory.return_value = mock_tts_prov

            result = filler.run([BatchNoteItem(note_id=1)], target_fields=["Notes"])

        prop = result.proposals[0]
        assert prop.success is True
        html = prop.changes["Notes"]
        # Text preserved, flags removed
        assert "Start" in html
        assert "Middle" in html
        assert "End" in html
        assert "{{IMAGE" not in html
        assert "{{AUDIO" not in html
        # Both errors reported in the same field_errors entry
        assert "Notes" in prop.field_errors
        error_str = prop.field_errors["Notes"]
        assert "image policy" in error_str
        assert "TTS quota" in error_str
