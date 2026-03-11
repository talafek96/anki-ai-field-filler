"""Media file handler for saving AI-generated audio and images to Anki."""

from __future__ import annotations

import hashlib
import time

from aqt import mw


class MediaHandler:
    """Saves generated media files to Anki's media folder."""

    @staticmethod
    def save_audio(audio_bytes: bytes, field_name: str) -> str:
        """Save audio bytes to Anki's media folder (auto-detects format).

        Returns an Anki sound tag like [sound:ai_filler_xyz.mp3].
        """
        ext = "wav" if audio_bytes[:4] == b"RIFF" else "mp3"
        filename = MediaHandler._generate_filename(field_name, ext)
        mw.col.media.write_data(filename, audio_bytes)
        return f"[sound:{filename}]"

    @staticmethod
    def save_image(image_bytes: bytes, field_name: str) -> str:
        """Save image bytes as a PNG file in Anki's media folder.

        Returns an HTML img tag like <img src="ai_filler_xyz.png">.
        """
        filename = MediaHandler._generate_filename(field_name, "png")
        mw.col.media.write_data(filename, image_bytes)
        return f'<img src="{filename}">'

    @staticmethod
    def _generate_filename(field_name: str, extension: str) -> str:
        """Generate a unique filename based on field name and timestamp."""
        safe_name = "".join(c if c.isalnum() else "_" for c in field_name)
        timestamp = str(time.time()).replace(".", "")
        hash_suffix = hashlib.md5(
            f"{safe_name}{timestamp}".encode()
        ).hexdigest()[:8]
        return f"ai_filler_{safe_name}_{hash_suffix}.{extension}"
