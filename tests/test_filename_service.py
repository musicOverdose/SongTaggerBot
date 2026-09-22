"""Tests for FilenameService: path traversal protection, sanitization, and template generation."""

from app.audio.models import AudioMetadata
from app.services.filename_service import FilenameService


def test_filename_sanitization():
    # Path traversal attempts
    assert FilenameService.sanitize("../../etc/passwd", ".mp3") == "etc_passwd.mp3"
    assert FilenameService.sanitize("..\\..\\windows\\system32", ".mp3") == "windows_system32.mp3"
    assert FilenameService.sanitize("../../../secret.flac", ".flac") == "secret.flac"

    # Control chars and null bytes
    assert FilenameService.sanitize("track\x00\x1f\x7fname", ".mp3") == "trackname.mp3"

    # Forward/backward slashes and invalid chars
    assert FilenameService.sanitize("AC/DC: Back in Black *?", ".mp3") == "AC_DC_ Back in Black.mp3"

    # User typed existing extension or different extension
    assert FilenameService.sanitize("my_song.mp3", ".mp3") == "my_song.mp3"
    assert FilenameService.sanitize("my_song.wav", ".mp3") == "my_song.mp3"  # Does not change audio format!

    # Reserved Windows device names
    assert FilenameService.sanitize("CON", ".mp3") == "CON_file.mp3"
    assert FilenameService.sanitize("NUL", ".flac") == "NUL_file.flac"

    # Empty string
    assert FilenameService.sanitize("", ".mp3") == "audio.mp3"

    # Very long name
    long_name = "a" * 300
    sanitized = FilenameService.sanitize(long_name, ".mp3")
    assert len(sanitized) <= 155
    assert sanitized.endswith(".mp3")


def test_filename_template_generation():
    meta = AudioMetadata(
        title="Avalanche",
        artist="Nick Cave",
        album="B-Sides",
        track_number=5,
        date="2026",
    )

    # Default template: {track:02} - {title}
    res1 = FilenameService.generate_from_metadata(meta, ".mp3", "{track:02} - {title}")
    assert res1 == "05 - Avalanche.mp3"

    # Template: {artist} - {title}
    res2 = FilenameService.generate_from_metadata(meta, ".mp3", "{artist} - {title}")
    assert res2 == "Nick Cave - Avalanche.mp3"

    # Template: {album} - {track:02} - {title}
    res3 = FilenameService.generate_from_metadata(meta, ".flac", "{album} - {track:02} - {title}")
    assert res3 == "B-Sides - 05 - Avalanche.flac"

    # Missing fields fallback safely
    empty_meta = AudioMetadata()
    res4 = FilenameService.generate_from_metadata(empty_meta, ".mp3", "{track:02} - {title}")
    assert res4 == "00 - audio.mp3"
