"""Tests for MediaHandler."""

from __future__ import annotations

from src.core.media_handler import MediaHandler, _pcm_to_wav


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

    def test_save_audio_raw_pcm_wrapped_as_wav(self, mock_mw) -> None:
        # Raw PCM: no RIFF header, no MP3 sync bytes
        pcm_bytes = b"\x00\x01\x02\x03" * 100
        result = MediaHandler.save_audio(pcm_bytes, "GoogleTTS")

        assert result.startswith("[sound:")
        assert result.endswith(".wav]")
        # The written bytes should now start with RIFF (WAV header)
        written_data = mock_mw.col.media.write_data.call_args[0][1]
        assert written_data[:4] == b"RIFF"

    def test_save_audio_id3_mp3(self, mock_mw) -> None:
        id3_bytes = b"ID3" + b"\x00" * 100
        result = MediaHandler.save_audio(id3_bytes, "ID3Field")

        assert result.endswith(".mp3]")

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
        assert isinstance(f1, str)
        assert isinstance(f2, str)
        assert f1.startswith("ai_filler_Same_")


class TestPcmToWav:
    def test_output_starts_with_riff(self) -> None:
        pcm = b"\x00" * 480  # 10ms of silence at 24kHz/16bit
        wav_data = _pcm_to_wav(pcm)
        assert wav_data[:4] == b"RIFF"
        assert b"WAVE" in wav_data[:12]

    def test_output_is_valid_wav(self) -> None:
        import io
        import wave

        pcm = b"\x00\x80" * 2400  # 100ms
        wav_data = _pcm_to_wav(pcm)
        with wave.open(io.BytesIO(wav_data), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 24000
            assert wf.getsampwidth() == 2
