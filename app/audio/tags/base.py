"""Abstract base class for audio tag adapters."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple
from app.audio.models import AudioFormat, AudioMetadata


class BaseTagAdapter(ABC):
    """Base interface for reading and writing audio metadata across various container formats."""

    @abstractmethod
    def can_handle(self, audio_format: AudioFormat) -> bool:
        """Return True if this adapter supports the given audio format."""
        pass

    @abstractmethod
    def read_metadata(self, file_path: Path) -> AudioMetadata:
        """Extract unified AudioMetadata from file."""
        pass

    @abstractmethod
    def write_metadata(self, file_path: Path, metadata: AudioMetadata) -> None:
        """Write modified AudioMetadata to file, preserving unrelated tags."""
        pass

    @abstractmethod
    def extract_cover(self, file_path: Path, target_path: Path) -> Optional[Tuple[int, int]]:
        """Extract embedded cover artwork if present. Return (width, height) or None."""
        pass

    @abstractmethod
    def embed_cover(self, file_path: Path, image_path: Path) -> bool:
        """Embed an image file into the audio file's tag structure."""
        pass

    @abstractmethod
    def remove_cover(self, file_path: Path) -> bool:
        """Remove embedded cover art from the audio file."""
        pass

    @abstractmethod
    def read_lyrics(self, file_path: Path) -> Optional[str]:
        """Read embedded lyrics if present."""
        pass

    @abstractmethod
    def write_lyrics(self, file_path: Path, lyrics: str) -> None:
        """Write or update embedded lyrics in the audio file."""
        pass

    @abstractmethod
    def remove_lyrics(self, file_path: Path) -> bool:
        """Remove embedded lyrics from the audio file."""
        pass
