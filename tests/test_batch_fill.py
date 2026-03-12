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
    BatchResult,
)

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

    @patch(_HTTP_URLOPEN)
    @patch("ai_field_filler.field_filler.mw")
    def test_error_collected_not_fatal(self, mock_mw: MagicMock, mock_urlopen: MagicMock) -> None:
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
        """Progress callback is called for each note."""
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

        assert len(progress_calls) == 2
        assert progress_calls[0].completed == 1
        assert progress_calls[1].completed == 2
        assert progress_calls[1].total == 2
        assert progress_calls[1].eta_seconds >= 0


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
        assert r.failures == []
        assert r.dry_run is False
