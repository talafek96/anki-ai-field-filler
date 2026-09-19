"""Media file handler for saving AI-generated audio and images to Anki."""

from __future__ import annotations

import hashlib
import io
import time
import wave

from aqt import mw


def _pcm_to_wav(
    pcm: bytes, *, channels: int = 1, rate: int = 24000, sample_width: int = 2
) -> bytes:
    """Wrap raw PCM audio in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()


class MediaHandler:
    """Saves generated media files to Anki's media folder."""

    @staticmethod
    def audio_bytes_and_ext(audio_bytes: bytes) -> tuple[bytes, str]:
        """Return playable audio bytes and their extension.

        Handles MP3, WAV, and raw PCM (linear16 24 kHz mono, as returned by
        Google Gemini TTS) — raw PCM is wrapped in a WAV container so it plays
        anywhere. Shared by :meth:`save_audio` and the developer tools preview
        so both interpret provider output identically.
        """
        if audio_bytes[:4] == b"RIFF":
            return audio_bytes, "wav"
        if audio_bytes[:3] == b"ID3" or audio_bytes[:2] in (
            b"\xff\xfb",
            b"\xff\xf3",
            b"\xff\xf2",
            b"\xff\xe2",
        ):
            return audio_bytes, "mp3"
        # Assume raw PCM (linear16, 24 kHz, mono) — wrap in WAV
        return _pcm_to_wav(audio_bytes), "wav"

    @staticmethod
    def save_audio(audio_bytes: bytes, field_name: str) -> str:
        """Save audio bytes to Anki's media folder (auto-detects format).

        Handles MP3, WAV, and raw PCM (linear16 24 kHz mono, as returned
        by Google Gemini TTS).  Returns an Anki sound tag like
        [sound:ai_filler_xyz.mp3].
        """
        audio_bytes, ext = MediaHandler.audio_bytes_and_ext(audio_bytes)
        filename = MediaHandler._generate_filename(field_name, ext)
        mw.col.media.write_data(filename, audio_bytes)
        return f"[sound:{filename}]"

    @staticmethod
    def save_image(image_bytes: bytes, field_name: str) -> str:
        """Save image bytes to Anki's media folder (auto-detects format).

        The extension has to follow the actual bytes: OpenAI's image models
        return PNG, but Gemini 3.x image models return JPEG, and writing
        JPEG data to a ``.png`` filename breaks Anki's media check and some
        clients' rendering.

        Returns an HTML img tag like <img src="ai_filler_xyz.png">.
        """
        ext = MediaHandler._sniff_image_ext(image_bytes)
        filename = MediaHandler._generate_filename(field_name, ext)
        mw.col.media.write_data(filename, image_bytes)
        return f'<img src="{filename}">'

    @staticmethod
    def _sniff_image_ext(data: bytes) -> str:
        """Detect image format from its magic bytes, defaulting to png."""
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return "png"
        if data[:3] == b"\xff\xd8\xff":
            return "jpg"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "webp"
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return "gif"
        return "png"

    @staticmethod
    def _generate_filename(field_name: str, extension: str) -> str:
        """Generate a unique filename based on field name and timestamp."""
        safe_name = "".join(c if c.isalnum() else "_" for c in field_name)
        timestamp = str(time.time()).replace(".", "")
        hash_suffix = hashlib.md5(f"{safe_name}{timestamp}".encode()).hexdigest()[:8]
        return f"ai_filler_{safe_name}_{hash_suffix}.{extension}"
