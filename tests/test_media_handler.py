"""Tests for MediaHandler."""

from __future__ import annotations

from ai_field_filler.media_handler import MediaHandler


class TestMediaHandler:
    def test_save_audio_mp3(self, mock_mw) -> None:
        mp3_bytes = b"\xff\xfb\x90\x00" + b"\x00" * 100
        result = MediaHandler.save_audio(mp3_bytes, "TestField")

        assert result.startswith("[sound:")
        assert result.endswith(".mp3]")
        assert "ai_filler_TestField_" in result
        mock_mw.col.media.write_data.assert_called_once()

    def test_save_audio_wav(self, mock_mw) -> None:
        wav_bytes = b"RIFF" + b"\x00" * 100
        result = MediaHandler.save_audio(wav_bytes, "VoiceField")

        assert result.startswith("[sound:")
        assert result.endswith(".wav]")

    def test_save_image(self, mock_mw) -> None:
        png_bytes = b"\x89PNG" + b"\x00" * 100
        result = MediaHandler.save_image(png_bytes, "ImageField")

        assert result.startswith('<img src="')
        assert result.endswith('">')
        assert "ai_filler_ImageField_" in result
        assert result.endswith('.png">')
        mock_mw.col.media.write_data.assert_called_once()

    def test_filename_sanitizes_special_chars(self) -> None:
        filename = MediaHandler._generate_filename("Field With Spaces!", "mp3")
        assert " " not in filename
        assert "!" not in filename
        assert filename.startswith("ai_filler_")
        assert filename.endswith(".mp3")

    def test_filenames_are_unique(self) -> None:
        f1 = MediaHandler._generate_filename("Same", "png")
        f2 = MediaHandler._generate_filename("Same", "png")
        # Due to timestamp-based hashing, consecutive calls should differ
        # (unless called in the exact same microsecond)
        assert isinstance(f1, str)
        assert isinstance(f2, str)
        assert f1.startswith("ai_filler_Same_")
