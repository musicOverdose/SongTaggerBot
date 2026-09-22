"""Tests for MetadataManager across audio formats (MP3, FLAC, M4A, OGG, OPUS, WAV)."""

from pathlib import Path
import shutil
import pytest

from app.audio.format_detector import FormatDetector
from app.audio.metadata_manager import MetadataManager
from app.audio.models import AudioFormat, AudioMetadata


@pytest.mark.asyncio
async def test_mp3_metadata_read_write(sample_mp3: Path, tmp_path: Path):
    test_file = tmp_path / "song.mp3"
    shutil.copy2(sample_mp3, test_file)

    mgr = MetadataManager()

    # Initial read
    initial_meta = await mgr.read_metadata(test_file, AudioFormat.MP3)
    assert initial_meta is not None

    # Write core and advanced tags
    new_meta = AudioMetadata(
        title="Avalanche",
        artist="Nick Cave",
        album="B-Sides & Rarities",
        albumartist="Nick Cave & The Bad Seeds",
        date="2026",
        genre="Rock",
        track_number=5,
        track_total=12,
        disc_number=1,
        disc_total=2,
        composer="Leonard Cohen",
        comment="Recorded for Black Sails",
        copyright="2026 Mute Records",
        grouping="Soundtracks",
        bpm=120,
        publisher="Mute",
        conductor="Warren Ellis",
        isrc="GBAYE0000001",
        sort_title="Avalanche",
        sort_artist="Cave, Nick",
        sort_album="B-Sides & Rarities",
    )
    ok = await mgr.write_metadata(test_file, new_meta, AudioFormat.MP3)
    assert ok is True

    # Read back and verify
    read_back = await mgr.read_metadata(test_file, AudioFormat.MP3)
    assert read_back.title == "Avalanche"
    assert read_back.artist == "Nick Cave"
    assert read_back.album == "B-Sides & Rarities"
    assert read_back.albumartist == "Nick Cave & The Bad Seeds"
    assert read_back.date == "2026"
    assert read_back.genre == "Rock"
    assert read_back.track_number == 5
    assert read_back.track_total == 12
    assert read_back.disc_number == 1
    assert read_back.disc_total == 2
    assert read_back.composer == "Leonard Cohen"
    assert read_back.comment == "Recorded for Black Sails"
    assert read_back.copyright == "2026 Mute Records"
    assert read_back.grouping == "Soundtracks"
    assert read_back.bpm == 120
    assert read_back.publisher == "Mute"
    assert read_back.conductor == "Warren Ellis"
    assert read_back.isrc == "GBAYE0000001"

    # Test that updating one field preserves other fields
    read_back.title = "Avalanche (Updated)"
    await mgr.write_metadata(test_file, read_back, AudioFormat.MP3)

    verified = await mgr.read_metadata(test_file, AudioFormat.MP3)
    assert verified.title == "Avalanche (Updated)"
    assert verified.artist == "Nick Cave"
    assert verified.album == "B-Sides & Rarities"
    assert verified.bpm == 120


@pytest.mark.asyncio
async def test_flac_metadata_read_write(sample_flac: Path, tmp_path: Path):
    test_file = tmp_path / "song.flac"
    shutil.copy2(sample_flac, test_file)

    mgr = MetadataManager()
    new_meta = AudioMetadata(
        title="High Water Everywhere",
        artist="Charley Patton",
        album="Founder of the Delta Blues",
        date="1929",
        genre="Blues",
        track_number=1,
        track_total=14,
        comment="Paramount 12909",
        composer="Charley Patton",
    )
    ok = await mgr.write_metadata(test_file, new_meta, AudioFormat.FLAC)
    assert ok is True

    read_back = await mgr.read_metadata(test_file, AudioFormat.FLAC)
    assert read_back.title == "High Water Everywhere"
    assert read_back.artist == "Charley Patton"
    assert read_back.album == "Founder of the Delta Blues"
    assert read_back.date == "1929"
    assert read_back.genre == "Blues"
    assert read_back.track_number == 1
    assert read_back.track_total == 14
    assert read_back.comment == "Paramount 12909"
    assert read_back.composer == "Charley Patton"


@pytest.mark.asyncio
async def test_m4a_metadata_read_write(sample_m4a: Path, tmp_path: Path):
    test_file = tmp_path / "song.m4a"
    shutil.copy2(sample_m4a, test_file)

    mgr = MetadataManager()
    new_meta = AudioMetadata(
        title="Midnight City",
        artist="M83",
        album="Hurry Up, We're Dreaming",
        albumartist="M83",
        date="2011",
        genre="Electronic",
        track_number=2,
        track_total=22,
        disc_number=1,
        disc_total=2,
        composer="Anthony Gonzalez",
        bpm=105,
    )
    ok = await mgr.write_metadata(test_file, new_meta, AudioFormat.M4A)
    assert ok is True

    read_back = await mgr.read_metadata(test_file, AudioFormat.M4A)
    assert read_back.title == "Midnight City"
    assert read_back.artist == "M83"
    assert read_back.album == "Hurry Up, We're Dreaming"
    assert read_back.date == "2011"
    assert read_back.track_number == 2
    assert read_back.track_total == 22
    assert read_back.bpm == 105


@pytest.mark.asyncio
async def test_ogg_opus_wav_metadata(sample_ogg: Path, sample_opus: Path, sample_wav: Path, tmp_path: Path):
    mgr = MetadataManager()

    # OGG
    ogg_file = tmp_path / "song.ogg"
    shutil.copy2(sample_ogg, ogg_file)
    await mgr.write_metadata(ogg_file, AudioMetadata(title="Ogg Title", artist="Ogg Artist"), AudioFormat.OGG)
    ogg_read = await mgr.read_metadata(ogg_file, AudioFormat.OGG)
    assert ogg_read.title == "Ogg Title"
    assert ogg_read.artist == "Ogg Artist"

    # OPUS
    opus_file = tmp_path / "song.opus"
    shutil.copy2(sample_opus, opus_file)
    await mgr.write_metadata(opus_file, AudioMetadata(title="Opus Title", artist="Opus Artist"), AudioFormat.OPUS)
    opus_read = await mgr.read_metadata(opus_file, AudioFormat.OPUS)
    assert opus_read.title == "Opus Title"
    assert opus_read.artist == "Opus Artist"

    # WAV
    wav_file = tmp_path / "song.wav"
    shutil.copy2(sample_wav, wav_file)
    await mgr.write_metadata(wav_file, AudioMetadata(title="Wav Title", artist="Wav Artist"), AudioFormat.WAV)
    wav_read = await mgr.read_metadata(wav_file, AudioFormat.WAV)
    assert wav_read.title == "Wav Title"
    assert wav_read.artist == "Wav Artist"


def test_format_detector(sample_mp3: Path, sample_flac: Path, sample_m4a: Path):
    fmt_mp3, ext_mp3, mime_mp3 = FormatDetector.detect_format(sample_mp3)
    assert fmt_mp3 == AudioFormat.MP3
    assert ext_mp3 == ".mp3"

    fmt_flac, ext_flac, mime_flac = FormatDetector.detect_format(sample_flac)
    assert fmt_flac == AudioFormat.FLAC
    assert ext_flac == ".flac"

    fmt_m4a, ext_m4a, mime_m4a = FormatDetector.detect_format(sample_m4a)
    assert fmt_m4a in (AudioFormat.M4A, AudioFormat.MP4)
