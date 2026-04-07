"""Media file handler for saving AI-generated audio and images to Anki."""

from __future__ import annotations

import hashlib
import io
import time
import wave

from aqt import mw


def _pcm_to_wav(pcm: bytes, *, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> bytes:
    """Wrap raw PCM audio in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()


class Media:
    """Saves generated media files to Anki's media folder."""

    @staticmethod
    def save_audio(audio_bytes: bytes, field_name: str) -> str:
        """Save audio bytes to Anki's media folder (auto-detects format).

        Handles MP3, WAV, and raw PCM (linear16 24 kHz mono, as returned
        by Google Gemini TTS).  Returns an Anki sound tag like
        [sound:ai_filler_xyz.mp3].
        """
        if audio_bytes[:4] == b"RIFF":
            ext = "wav"
        elif audio_bytes[:3] == b"ID3" or audio_bytes[:2] in (
            b"\xff\xfb",
            b"\xff\xf3",
            b"\xff\xf2",
            b"\xff\xe2",
        ):
            ext = "mp3"
        else:
            # Assume raw PCM (linear16, 24 kHz, mono) — wrap in WAV
            audio_bytes = _pcm_to_wav(audio_bytes)
            ext = "wav"

        filename = Media._generate_filename(field_name, ext)
        mw.col.media.write_data(filename, audio_bytes)
        return f"[sound:{filename}]"

    @staticmethod
    def save_image(image_bytes: bytes, field_name: str) -> str:
        """Save image bytes as a PNG file in Anki's media folder.

        Returns an HTML img tag like <img src="ai_filler_xyz.png">.
        """
        filename = Media._generate_filename(field_name, "png")
        mw.col.media.write_data(filename, image_bytes)
        return f'<img src="{filename}">'

    @staticmethod
    def _generate_filename(field_name: str, extension: str) -> str:
        """Generate a unique filename based on field name and timestamp."""
        safe_name = "".join(c if c.isalnum() else "_" for c in field_name)
        timestamp = str(time.time()).replace(".", "")
        hash_suffix = hashlib.md5(f"{safe_name}{timestamp}".encode()).hexdigest()[:8]
        return f"ai_filler_{safe_name}_{hash_suffix}.{extension}"
