"""Filename sanitization and template-based generator."""

import re
from typing import Optional
from app.audio.models import AudioMetadata

RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class FilenameService:
    """Provides secure filename sanitization and template formatting."""

    @staticmethod
    def sanitize(filename: str, expected_ext: str) -> str:
        """
        Sanitize user-provided filename:
        - Strips path traversal sequences (../, ..\\)
        - Removes null bytes and ASCII control characters
        - Removes path separators (/ and \\)
        - Trims leading/trailing periods and spaces
        - Enforces expected file extension
        - Protects against Windows reserved device names
        - Enforces maximum length
        """
        if not expected_ext.startswith("."):
            expected_ext = f".{expected_ext}"
        expected_ext = expected_ext.lower()

        # Remove null bytes and control chars (0x00 to 0x1F and 0x7F)
        cleaned = re.sub(r"[\x00-\x1f\x7f]", "", filename)

        # Remove path separators and traversal
        cleaned = cleaned.replace("/", "_").replace("\\", "_").replace("..", "_")

        # Strip illegal characters for cross-platform filesystems: < > : " / \ | ? *
        cleaned = re.sub(r'[<>:"/\\|?*]', "_", cleaned)

        # Collapse multiple underscores/spaces
        cleaned = re.sub(r"_+", "_", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Strip user-typed extension if present
        if cleaned.lower().endswith(expected_ext):
            base_name = cleaned[:-len(expected_ext)].strip("._ ")
        else:
            # Strip whatever extension they might have typed
            base_name = re.sub(r"\.[a-zA-Z0-9]{1,6}$", "", cleaned).strip("._ ")

        base_name = base_name.strip("._ ")

        if not base_name:
            base_name = "audio"

        # Check reserved names
        if base_name.upper() in RESERVED_NAMES:
            base_name = f"{base_name}_file"

        # Cap base_name length to 150 characters to avoid filesystem limits
        if len(base_name) > 150:
            base_name = base_name[:150].rstrip(". ")

        return f"{base_name}{expected_ext}"

    @classmethod
    def generate_from_metadata(
        cls,
        metadata: AudioMetadata,
        expected_ext: str,
        template: str = "{track:02} - {title}",
        fallback_name: str = "audio",
    ) -> str:
        """
        Generate a sanitized filename using a template string and AudioMetadata.
        Supported placeholders:
        - {track} or {track:02}
        - {title}
        - {artist}
        - {album}
        - {albumartist}
        - {year}
        """
        track_num = metadata.track_number or 0
        title = (metadata.title or "").strip() or fallback_name
        artist = (metadata.artist or "").strip() or "Unknown Artist"
        album = (metadata.album or "").strip() or "Unknown Album"
        albumartist = (metadata.albumartist or metadata.artist or "").strip() or "Unknown Artist"
        year = (metadata.date or "").strip()[:4] or "0000"

        # Safe formatting dictionary
        context = {
            "track": track_num,
            "title": title,
            "artist": artist,
            "album": album,
            "albumartist": albumartist,
            "year": year,
        }

        try:
            rendered = template.format(**context)
        except Exception:
            # Fallback simple template if custom template formatting threw KeyError/ValueError
            rendered = f"{track_num:02d} - {title}" if track_num > 0 else title

        return cls.sanitize(rendered, expected_ext)
