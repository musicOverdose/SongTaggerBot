"""Unified Metadata Manager coordinating format-specific adapters."""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple

from app.audio.format_detector import FormatDetector
from app.audio.models import AudioFormat, AudioMetadata
from app.audio.tags.asf_adapter import ASFAdapter
from app.audio.tags.base import BaseTagAdapter
from app.audio.tags.id3_adapter import ID3Adapter
from app.audio.tags.mp4_adapter import MP4Adapter
from app.audio.tags.vorbis_adapter import VorbisAdapter

logger = logging.getLogger(__name__)


class MetadataManager:
    """Orchestrates metadata reading and writing across all supported formats."""

    def __init__(self):
        self._adapters: list[BaseTagAdapter] = [
            ID3Adapter(),
            VorbisAdapter(),
            MP4Adapter(),
            ASFAdapter(),
        ]

    def get_adapter(self, audio_format: AudioFormat) -> Optional[BaseTagAdapter]:
        for adapter in self._adapters:
            if adapter.can_handle(audio_format):
                return adapter
        return None

    def read_metadata_sync(self, file_path: Path, audio_format: Optional[AudioFormat] = None) -> AudioMetadata:
        if audio_format is None:
            audio_format, _, _ = FormatDetector.detect_format(file_path)

        adapter = self.get_adapter(audio_format)
        if adapter is None:
            logger.warning(f"No tag adapter found for format {audio_format} ({file_path})")
            return AudioMetadata()

        try:
            return adapter.read_metadata(file_path)
        except Exception as e:
            logger.error(f"Error reading metadata from {file_path}: {e}")
            return AudioMetadata()

    async def read_metadata(self, file_path: Path, audio_format: Optional[AudioFormat] = None) -> AudioMetadata:
        return await asyncio.to_thread(self.read_metadata_sync, file_path, audio_format)

    def write_metadata_sync(self, file_path: Path, metadata: AudioMetadata, audio_format: Optional[AudioFormat] = None) -> bool:
        if audio_format is None:
            audio_format, _, _ = FormatDetector.detect_format(file_path)

        adapter = self.get_adapter(audio_format)
        if adapter is None:
            logger.error(f"Cannot write metadata: unsupported format {audio_format}")
            return False

        try:
            adapter.write_metadata(file_path, metadata)
            return True
        except Exception as e:
            logger.error(f"Error writing metadata to {file_path}: {e}", exc_info=True)
            return False

    async def write_metadata(self, file_path: Path, metadata: AudioMetadata, audio_format: Optional[AudioFormat] = None) -> bool:
        return await asyncio.to_thread(self.write_metadata_sync, file_path, metadata, audio_format)

    def extract_cover_sync(self, file_path: Path, target_path: Path, audio_format: Optional[AudioFormat] = None) -> Optional[Tuple[int, int]]:
        if audio_format is None:
            audio_format, _, _ = FormatDetector.detect_format(file_path)

        adapter = self.get_adapter(audio_format)
        if adapter is None:
            return None

        try:
            return adapter.extract_cover(file_path, target_path)
        except Exception as e:
            logger.error(f"Error extracting cover from {file_path}: {e}")
            return None

    async def extract_cover(self, file_path: Path, target_path: Path, audio_format: Optional[AudioFormat] = None) -> Optional[Tuple[int, int]]:
        return await asyncio.to_thread(self.extract_cover_sync, file_path, target_path, audio_format)

    def embed_cover_sync(self, file_path: Path, image_path: Path, audio_format: Optional[AudioFormat] = None) -> bool:
        if audio_format is None:
            audio_format, _, _ = FormatDetector.detect_format(file_path)

        adapter = self.get_adapter(audio_format)
        if adapter is None:
            return False

        try:
            return adapter.embed_cover(file_path, image_path)
        except Exception as e:
            logger.error(f"Error embedding cover into {file_path}: {e}")
            return False

    async def embed_cover(self, file_path: Path, image_path: Path, audio_format: Optional[AudioFormat] = None) -> bool:
        return await asyncio.to_thread(self.embed_cover_sync, file_path, image_path, audio_format)

    def remove_cover_sync(self, file_path: Path, audio_format: Optional[AudioFormat] = None) -> bool:
        if audio_format is None:
            audio_format, _, _ = FormatDetector.detect_format(file_path)

        adapter = self.get_adapter(audio_format)
        if adapter is None:
            return False

        try:
            return adapter.remove_cover(file_path)
        except Exception as e:
            logger.error(f"Error removing cover from {file_path}: {e}")
            return False

    async def remove_cover(self, file_path: Path, audio_format: Optional[AudioFormat] = None) -> bool:
        return await asyncio.to_thread(self.remove_cover_sync, file_path, audio_format)

    def read_lyrics_sync(self, file_path: Path, audio_format: Optional[AudioFormat] = None) -> Optional[str]:
        if audio_format is None:
            audio_format, _, _ = FormatDetector.detect_format(file_path)

        adapter = self.get_adapter(audio_format)
        if adapter is None:
            return None

        try:
            return adapter.read_lyrics(file_path)
        except Exception as e:
            logger.error(f"Error reading lyrics from {file_path}: {e}")
            return None

    async def read_lyrics(self, file_path: Path, audio_format: Optional[AudioFormat] = None) -> Optional[str]:
        return await asyncio.to_thread(self.read_lyrics_sync, file_path, audio_format)

    def write_lyrics_sync(self, file_path: Path, lyrics: str, audio_format: Optional[AudioFormat] = None) -> bool:
        if audio_format is None:
            audio_format, _, _ = FormatDetector.detect_format(file_path)

        adapter = self.get_adapter(audio_format)
        if adapter is None:
            return False

        try:
            adapter.write_lyrics(file_path, lyrics)
            return True
        except Exception as e:
            logger.error(f"Error writing lyrics to {file_path}: {e}")
            return False

    async def write_lyrics(self, file_path: Path, lyrics: str, audio_format: Optional[AudioFormat] = None) -> bool:
        return await asyncio.to_thread(self.write_lyrics_sync, file_path, lyrics, audio_format)

    def remove_lyrics_sync(self, file_path: Path, audio_format: Optional[AudioFormat] = None) -> bool:
        if audio_format is None:
            audio_format, _, _ = FormatDetector.detect_format(file_path)

        adapter = self.get_adapter(audio_format)
        if adapter is None:
            return False

        try:
            return adapter.remove_lyrics(file_path)
        except Exception as e:
            logger.error(f"Error removing lyrics from {file_path}: {e}")
            return False

    async def remove_lyrics(self, file_path: Path, audio_format: Optional[AudioFormat] = None) -> bool:
        return await asyncio.to_thread(self.remove_lyrics_sync, file_path, audio_format)
