"""Tests for CoverManager: validation, embedding, extraction, removal, and thumbnail generation."""

from pathlib import Path
import shutil
from PIL import Image
import pytest

from app.audio.cover_manager import CoverManager, MAX_THUMBNAIL_BYTES, MAX_THUMBNAIL_DIMENSION
from app.audio.metadata_manager import MetadataManager
from app.audio.models import AudioFormat


@pytest.mark.asyncio
async def test_image_validation(sample_jpeg: Path, sample_png: Path, sample_webp: Path, tmp_path: Path):
    # JPEG
    ok, fmt, dims, size = await CoverManager.validate_image(sample_jpeg)
    assert ok is True
    assert fmt == "JPEG"
    assert dims == (600, 600)
    assert size > 0

    # PNG
    ok, fmt, dims, size = await CoverManager.validate_image(sample_png)
    assert ok is True
    assert fmt == "PNG"
    assert dims == (500, 500)

    # WebP
    ok, fmt, dims, size = await CoverManager.validate_image(sample_webp)
    assert ok is True
    assert fmt == "WEBP"
    assert dims == (400, 400)

    # Corrupt / Non-image file
    fake_img = tmp_path / "fake.jpg"
    fake_img.write_text("not an image")
    ok, fmt, dims, size = await CoverManager.validate_image(fake_img)
    assert ok is False


@pytest.mark.asyncio
async def test_telegram_thumbnail_constraints(sample_jpeg: Path, tmp_path: Path):
    # Large 2000x2000 image
    large_img_path = tmp_path / "large_cover.jpg"
    large_img = Image.new("RGB", (2000, 2000), color=(100, 150, 200))
    large_img.save(large_img_path, format="JPEG", quality=98)

    thumb_target = tmp_path / "thumb.jpg"
    success = await CoverManager.generate_telegram_thumbnail(large_img_path, thumb_target)
    assert success is True
    assert thumb_target.exists()

    # Verify constraints: <= 320x320 and <= 200 KB
    file_size = thumb_target.stat().st_size
    assert file_size <= MAX_THUMBNAIL_BYTES, f"Thumbnail size {file_size} exceeds {MAX_THUMBNAIL_BYTES} bytes"

    with Image.open(thumb_target) as img:
        assert img.format == "JPEG"
        w, h = img.size
        assert w <= MAX_THUMBNAIL_DIMENSION
        assert h <= MAX_THUMBNAIL_DIMENSION


@pytest.mark.asyncio
async def test_cover_embedding_extraction_removal(
    sample_mp3: Path,
    sample_flac: Path,
    sample_m4a: Path,
    sample_jpeg: Path,
    tmp_path: Path,
):
    mgr = MetadataManager()

    # 1. Test MP3
    mp3_file = tmp_path / "test_cover.mp3"
    shutil.copy2(sample_mp3, mp3_file)

    # Embed
    embed_ok = await mgr.embed_cover(mp3_file, sample_jpeg, AudioFormat.MP3)
    assert embed_ok is True

    # Extract
    extracted_path = tmp_path / "extracted_mp3.jpg"
    dim = await mgr.extract_cover(mp3_file, extracted_path, AudioFormat.MP3)
    assert dim is not None
    assert extracted_path.exists()
    assert dim == (600, 600)

    # Verify metadata model reflects cover
    meta = await mgr.read_metadata(mp3_file, AudioFormat.MP3)
    assert meta.has_cover is True

    # Remove
    remove_ok = await mgr.remove_cover(mp3_file, AudioFormat.MP3)
    assert remove_ok is True
    meta_after = await mgr.read_metadata(mp3_file, AudioFormat.MP3)
    assert meta_after.has_cover is False

    # 2. Test FLAC
    flac_file = tmp_path / "test_cover.flac"
    shutil.copy2(sample_flac, flac_file)

    embed_flac = await mgr.embed_cover(flac_file, sample_jpeg, AudioFormat.FLAC)
    assert embed_flac is True
    flac_extracted = tmp_path / "extracted_flac.jpg"
    flac_dim = await mgr.extract_cover(flac_file, flac_extracted, AudioFormat.FLAC)
    assert flac_dim == (600, 600)
    assert (await mgr.read_metadata(flac_file, AudioFormat.FLAC)).has_cover is True

    await mgr.remove_cover(flac_file, AudioFormat.FLAC)
    assert (await mgr.read_metadata(flac_file, AudioFormat.FLAC)).has_cover is False

    # 3. Test M4A
    m4a_file = tmp_path / "test_cover.m4a"
    shutil.copy2(sample_m4a, m4a_file)

    embed_m4a = await mgr.embed_cover(m4a_file, sample_jpeg, AudioFormat.M4A)
    assert embed_m4a is True
    m4a_extracted = tmp_path / "extracted_m4a.jpg"
    m4a_dim = await mgr.extract_cover(m4a_file, m4a_extracted, AudioFormat.M4A)
    assert m4a_dim == (600, 600)
    assert (await mgr.read_metadata(m4a_file, AudioFormat.M4A)).has_cover is True

    await mgr.remove_cover(m4a_file, AudioFormat.M4A)
    assert (await mgr.read_metadata(m4a_file, AudioFormat.M4A)).has_cover is False
