"""Extended integration and edge case tests."""

import asyncio
from pathlib import Path
import shutil
import time
from unittest.mock import MagicMock, patch
import pytest

from app.audio.models import AudioFormat, AudioMetadata
from app.audio.metadata_manager import MetadataManager
from app.cli import async_main
from app.config import Settings
from app.services.job_manager import JobManager


@pytest.mark.asyncio
async def test_undo_multiple_changes_in_sequence(sample_mp3: Path, tmp_path: Path):
    test_file = tmp_path / "undo_test.mp3"
    shutil.copy2(sample_mp3, test_file)

    mgr = JobManager(base_jobs_dir=tmp_path / "jobs", ttl_minutes=30)
    job = mgr.create_job(1, 1, "test.mp3", ".mp3")

    # Initial state
    job.working_metadata = AudioMetadata(title="Original Title", artist="Original Artist")

    # Change 1: Title
    job.record_change("title", "Changed Title 1")
    assert job.working_metadata.title == "Changed Title 1"

    # Change 2: Artist
    job.record_change("artist", "Changed Artist 1")
    assert job.working_metadata.artist == "Changed Artist 1"

    # Change 3: Title again
    job.record_change("title", "Changed Title 2")
    assert job.working_metadata.title == "Changed Title 2"

    # Undo 1 -> Reverts title back to Changed Title 1
    c1 = job.undo_last_change()
    assert c1.field_name == "title"
    assert job.working_metadata.title == "Changed Title 1"

    # Undo 2 -> Reverts artist back to Original Artist
    c2 = job.undo_last_change()
    assert c2.field_name == "artist"
    assert job.working_metadata.artist == "Original Artist"

    # Undo 3 -> Reverts title back to Original Title
    c3 = job.undo_last_change()
    assert c3.field_name == "title"
    assert job.working_metadata.title == "Original Title"

    mgr.cleanup_job(job.uuid)


def test_abandoned_jobs_garbage_collection(tmp_path: Path):
    jobs_dir = tmp_path / "jobs"
    mgr = JobManager(base_jobs_dir=jobs_dir, ttl_minutes=1)  # 1 minute TTL

    job = mgr.create_job(2, 2, "old.mp3", ".mp3")
    assert job.dir_path.exists()

    # Manually age the job past TTL
    job.last_activity = time.time() - 120

    cleaned = mgr.cleanup_expired_jobs()
    assert cleaned >= 1
    assert not job.dir_path.exists()
    assert mgr.get_job(job.uuid) is None


def test_custom_api_server_config():
    # Verify local bot API URL configuration
    s = Settings(
        telegram_api_mode="local",
        telegram_api_base_url="http://localhost:8081",
        max_input_mb=2000,
        max_output_mb=2000,
    )
    assert s.max_input_bytes == 2000 * 1024 * 1024
    assert s.telegram_api_mode == "local"
    assert s.is_local_mode is True
    assert s.effective_api_base_url == "http://localhost:8081"


@pytest.mark.asyncio
async def test_cli_argument_parsing(tmp_path: Path):
    db_file = tmp_path / "cli_test.db"
    settings = Settings(data_dir=tmp_path, temp_dir=tmp_path / "temp")

    with patch("app.cli.get_settings", return_value=settings):
        with patch("sys.argv", ["cli", "channels", "add", "@testchannel"]):
            await async_main()

        with patch("sys.argv", ["cli", "channels", "list"]):
            await async_main()

        with patch("sys.argv", ["cli", "stats"]):
            await async_main()

        with patch("sys.argv", ["cli", "cleanup"]):
            await async_main()

        with patch("sys.argv", ["cli", "channels", "remove", "@testchannel"]):
            await async_main()
