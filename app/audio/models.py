"""Audio metadata and technical information domain models."""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Optional


class AudioFormat(str, Enum):
    MP3 = "MP3"
    FLAC = "FLAC"
    M4A = "M4A"
    MP4 = "MP4"
    OGG = "OGG"
    OPUS = "OPUS"
    WAV = "WAV"
    AIFF = "AIFF"
    WMA = "WMA"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_string(cls, val: str) -> "AudioFormat":
        val_upper = val.upper().strip()
        for member in cls:
            if member.value == val_upper:
                return member
        return cls.UNKNOWN


@dataclass
class MetadataChange:
    """Represents a single metadata field modification for undo history."""
    field_name: str
    old_value: Any
    new_value: Any
    timestamp: float = field(default_factory=time.time)


@dataclass
class AudioMetadata:
    """Unified internal audio metadata model independent of file container."""

    # Core metadata
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    albumartist: Optional[str] = None
    date: Optional[str] = None
    genre: Optional[str] = None
    track_number: Optional[int] = None
    track_total: Optional[int] = None
    disc_number: Optional[int] = None
    disc_total: Optional[int] = None
    composer: Optional[str] = None
    comment: Optional[str] = None
    copyright: Optional[str] = None

    # Lyrics & Cover indicators
    lyrics: Optional[str] = None
    has_lyrics: bool = False
    has_cover: bool = False
    cover_mime: Optional[str] = None
    cover_dimensions: Optional[tuple[int, int]] = None  # (width, height)
    cover_size_bytes: Optional[int] = None

    # Advanced metadata
    grouping: Optional[str] = None
    bpm: Optional[int] = None
    publisher: Optional[str] = None
    conductor: Optional[str] = None
    compilation: Optional[bool] = None
    sort_title: Optional[str] = None
    sort_artist: Optional[str] = None
    sort_album: Optional[str] = None
    sort_album_artist: Optional[str] = None
    isrc: Optional[str] = None

    # Container-specific / unmapped tag frames to preserve on writes
    custom_tags: dict[str, Any] = field(default_factory=dict)

    def clone(self) -> "AudioMetadata":
        """Create a deep copy of this metadata object."""
        return AudioMetadata(
            title=self.title,
            artist=self.artist,
            album=self.album,
            albumartist=self.albumartist,
            date=self.date,
            genre=self.genre,
            track_number=self.track_number,
            track_total=self.track_total,
            disc_number=self.disc_number,
            disc_total=self.disc_total,
            composer=self.composer,
            comment=self.comment,
            copyright=self.copyright,
            lyrics=self.lyrics,
            has_lyrics=self.has_lyrics,
            has_cover=self.has_cover,
            cover_mime=self.cover_mime,
            cover_dimensions=self.cover_dimensions,
            cover_size_bytes=self.cover_size_bytes,
            grouping=self.grouping,
            bpm=self.bpm,
            publisher=self.publisher,
            conductor=self.conductor,
            compilation=self.compilation,
            sort_title=self.sort_title,
            sort_artist=self.sort_artist,
            sort_album=self.sort_album,
            sort_album_artist=self.sort_album_artist,
            isrc=self.isrc,
            custom_tags=dict(self.custom_tags),
        )


@dataclass
class AudioTechnicalInfo:
    """Technical media properties probed from the audio file."""
    format_name: str
    codec_name: str
    mime_type: str
    file_size_bytes: int
    duration_seconds: float
    bitrate_kbps: Optional[int] = None
    bitrate_mode: Optional[str] = None  # CBR, VBR
    sample_rate_hz: Optional[int] = None
    channels: Optional[int] = None
    channel_layout: Optional[str] = None  # Stereo, Mono, 5.1
    bit_depth: Optional[int] = None
    tag_type: str = "Unknown"
    has_cover: bool = False
    cover_dimensions: Optional[tuple[int, int]] = None
    has_lyrics: bool = False

    @property
    def duration_formatted(self) -> str:
        total_seconds = int(self.duration_seconds)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def file_size_mb(self) -> float:
        return round(self.file_size_bytes / (1024 * 1024), 1)
