"""Tests for embedded lyrics manipulation across formats."""

from pathlib import Path
import shutil
import pytest

from app.audio.metadata_manager import MetadataManager
from app.audio.models import AudioFormat

SAMPLE_LYRICS = """Well I stepped into an avalanche
It covered up my soul
When I am not with you I'm not whole
I have no music in my heart
And no one can heal this soul."""


@pytest.mark.asyncio
async def test_lyrics_lifecycle_mp3(sample_mp3: Path, tmp_path: Path):
    test_file = tmp_path / "lyrics.mp3"
    shutil.copy2(sample_mp3, test_file)
    mgr = MetadataManager()

    # Initially empty
    assert await mgr.read_lyrics(test_file, AudioFormat.MP3) is None

    # Write multiline lyrics
    await mgr.write_lyrics(test_file, SAMPLE_LYRICS, AudioFormat.MP3)
    read_lyrics = await mgr.read_lyrics(test_file, AudioFormat.MP3)
    assert read_lyrics is not None
    assert "stepped into an avalanche" in read_lyrics

    # Verify through AudioMetadata model
    meta = await mgr.read_metadata(test_file, AudioFormat.MP3)
    assert meta.has_lyrics is True
    assert meta.lyrics == SAMPLE_LYRICS

    # Remove lyrics
    await mgr.remove_lyrics(test_file, AudioFormat.MP3)
    assert await mgr.read_lyrics(test_file, AudioFormat.MP3) is None


@pytest.mark.asyncio
async def test_lyrics_lifecycle_flac(sample_flac: Path, tmp_path: Path):
    test_file = tmp_path / "lyrics.flac"
    shutil.copy2(sample_flac, test_file)
    mgr = MetadataManager()

    await mgr.write_lyrics(test_file, SAMPLE_LYRICS, AudioFormat.FLAC)
    read_lyrics = await mgr.read_lyrics(test_file, AudioFormat.FLAC)
    assert read_lyrics == SAMPLE_LYRICS

    await mgr.remove_lyrics(test_file, AudioFormat.FLAC)
    assert await mgr.read_lyrics(test_file, AudioFormat.FLAC) is None


@pytest.mark.asyncio
async def test_lyrics_lifecycle_m4a(sample_m4a: Path, tmp_path: Path):
    test_file = tmp_path / "lyrics.m4a"
    shutil.copy2(sample_m4a, test_file)
    mgr = MetadataManager()

    await mgr.write_lyrics(test_file, SAMPLE_LYRICS, AudioFormat.M4A)
    read_lyrics = await mgr.read_lyrics(test_file, AudioFormat.M4A)
    assert read_lyrics == SAMPLE_LYRICS

    await mgr.remove_lyrics(test_file, AudioFormat.M4A)
    assert await mgr.read_lyrics(test_file, AudioFormat.M4A) is None
