"""Tests for FileAcquisitionService: Local Bot API volume copy, security boundary, and Cloud HTTP fallback."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram import Bot
from aiogram.types import File

from app.config import Settings
from app.services.file_acquisition import (
    FileAcquisitionService,
    LocalFileAccessError,
    SecurityError,
)


@pytest.fixture
def temp_tg_volume(tmp_path: Path) -> Path:
    """Simulates the mounted /var/lib/telegram-bot-api volume."""
    vol_dir = tmp_path / "telegram-bot-api"
    vol_dir.mkdir()
    return vol_dir


@pytest.fixture
def local_settings(temp_tg_volume: Path) -> Settings:
    return Settings(
        bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        admin_ids=[1001],
        telegram_api_mode="local",
        telegram_api_base_url="http://telegram-bot-api:8081",
        local_bot_api_data_dir=temp_tg_volume,
    )


@pytest.fixture
def cloud_settings() -> Settings:
    return Settings(
        bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        admin_ids=[1001],
        telegram_api_mode="cloud",
        telegram_api_base_url="https://api.telegram.org",
    )


@pytest.mark.asyncio
async def test_local_mode_copies_file_from_mounted_volume(local_settings: Settings, temp_tg_volume: Path, tmp_path: Path):
    """Local mode copies directly from the mounted volume without making an HTTP request."""
    # Create simulated audio file inside the volume
    bot_dir = temp_tg_volume / "123456:ABC" / "music"
    bot_dir.mkdir(parents=True)
    source_file = bot_dir / "file_0.mp3"
    source_file.write_bytes(b"MOCK_AUDIO_DATA_FOR_LOCAL_COPY")

    service = FileAcquisitionService(local_settings)

    mock_bot = MagicMock(spec=Bot)
    mock_file = File(
        file_id="tg_file_123",
        file_unique_id="uniq_123",
        file_path=str(source_file),
    )
    mock_bot.get_file = AsyncMock(return_value=mock_file)
    mock_bot.download_file = AsyncMock()

    dest = tmp_path / "scratch" / "job_original.mp3"
    result = await service.acquire_file(mock_bot, "tg_file_123", destination=dest)

    assert result == dest
    assert dest.exists()
    assert dest.read_bytes() == b"MOCK_AUDIO_DATA_FOR_LOCAL_COPY"

    # bot.download_file must NOT have been called
    mock_bot.download_file.assert_not_called()


@pytest.mark.asyncio
async def test_security_boundary_rejects_path_traversal(local_settings: Settings, tmp_path: Path):
    """Paths outside allowed_root (/var/lib/telegram-bot-api) are rejected with SecurityError."""
    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("SENSITIVE")

    service = FileAcquisitionService(local_settings)

    mock_bot = MagicMock(spec=Bot)
    mock_file = File(
        file_id="tg_file_evil",
        file_unique_id="uniq_evil",
        file_path=str(outside_file),
    )
    mock_bot.get_file = AsyncMock(return_value=mock_file)

    dest = tmp_path / "scratch" / "target.mp3"
    with pytest.raises(SecurityError) as exc_info:
        await service.acquire_file(mock_bot, "tg_file_evil", destination=dest)

    assert "outside allowed" in str(exc_info.value).lower()
    assert not dest.exists()


@pytest.mark.asyncio
async def test_missing_local_file_raises_error_without_http_fallback(local_settings: Settings, temp_tg_volume: Path, tmp_path: Path):
    """If file is missing on the mounted volume, raise LocalFileAccessError without silent HTTP fallback."""
    nonexistent = temp_tg_volume / "bot_dir" / "missing_file.mp3"

    service = FileAcquisitionService(local_settings)

    mock_bot = MagicMock(spec=Bot)
    mock_file = File(
        file_id="tg_file_missing",
        file_unique_id="uniq_missing",
        file_path=str(nonexistent),
    )
    mock_bot.get_file = AsyncMock(return_value=mock_file)
    mock_bot.download_file = AsyncMock()

    dest = tmp_path / "scratch" / "target.mp3"
    with pytest.raises(LocalFileAccessError) as exc_info:
        await service.acquire_file(mock_bot, "tg_file_missing", destination=dest)

    assert "missing or inaccessible" in str(exc_info.value).lower()
    assert "telegram-bot-api-data" in str(exc_info.value)
    # Crucial: do NOT silently try to download from broken http://.../file/... endpoint
    mock_bot.download_file.assert_not_called()


@pytest.mark.asyncio
async def test_cloud_mode_uses_http_download(cloud_settings: Settings, tmp_path: Path):
    """In Cloud mode, file is downloaded via bot.download_file."""
    service = FileAcquisitionService(cloud_settings)

    dest = tmp_path / "scratch" / "target.mp3"

    async def fake_download(file_path, destination):
        destination.write_bytes(b"DOWNLOADED_VIA_HTTP")

    mock_bot = MagicMock(spec=Bot)
    mock_file = File(
        file_id="cloud_file_123",
        file_unique_id="uniq_cloud",
        file_path="music/file_0.mp3",
    )
    mock_bot.get_file = AsyncMock(return_value=mock_file)
    mock_bot.download_file = AsyncMock(side_effect=fake_download)

    result = await service.acquire_file(mock_bot, "cloud_file_123", destination=dest)

    assert result == dest
    assert dest.read_bytes() == b"DOWNLOADED_VIA_HTTP"
    mock_bot.download_file.assert_called_once_with("music/file_0.mp3", destination=dest)


@pytest.mark.asyncio
async def test_cover_image_acquisition_uses_same_service(local_settings: Settings, temp_tg_volume: Path, tmp_path: Path):
    """Cover image downloads go through the same FileAcquisitionService logic."""
    bot_dir = temp_tg_volume / "photos"
    bot_dir.mkdir(parents=True)
    source_img = bot_dir / "cover_1.jpg"
    source_img.write_bytes(b"\xFF\xD8\xFF\xE0_FAKE_JPEG")

    service = FileAcquisitionService(local_settings)

    mock_bot = MagicMock(spec=Bot)
    mock_file = File(
        file_id="photo_123",
        file_unique_id="uniq_photo",
        file_path=str(source_img),
    )
    mock_bot.get_file = AsyncMock(return_value=mock_file)

    dest = tmp_path / "scratch" / "temp_cover.jpg"
    result = await service.acquire_file(mock_bot, "photo_123", destination=dest)

    assert result == dest
    assert dest.exists()
    assert dest.read_bytes() == b"\xFF\xD8\xFF\xE0_FAKE_JPEG"
