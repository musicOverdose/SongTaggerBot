"""Tests for Reliability, Abuse Protection, Media Safety, and Broadcast Operations."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from app.audio.cutter import AudioCutter
from app.bot.permissions import AdminCapability, has_admin_capability
from app.config import Settings
from app.database.connection import Database
from app.database.repository import DatabaseRepository
from app.services.broadcast_service import BroadcastService
from app.services.job_manager import (
    GlobalConcurrentJobLimitError,
    JobManager,
    MaintenanceModeError,
    UserConcurrentJobLimitError,
)
from app.services.rate_limiter import RateLimiter


# ==============================================================================
# 1. Rate Limiter Tests
# ==============================================================================

def test_rate_limiter_sliding_window():
    limiter = RateLimiter(max_requests=2, window_seconds=2)
    user_id = 42

    # First 2 requests within window should pass
    ok1, wait1 = limiter.check(user_id)
    assert ok1 is True
    assert wait1 == 0

    ok2, wait2 = limiter.check(user_id)
    assert ok2 is True
    assert wait2 == 0

    # 3rd request should be blocked with retry-after
    ok3, wait3 = limiter.check(user_id)
    assert ok3 is False
    assert wait3 > 0

    # Different user should not be affected
    other_ok, other_wait = limiter.check(99)
    assert other_ok is True
    assert other_wait == 0

    # Resetting user allows immediate request
    limiter.reset_user(user_id)
    ok_reset, _ = limiter.check(user_id)
    assert ok_reset is True


# ==============================================================================
# 2. JobManager Abuse Protection & Service Boundary Limits
# ==============================================================================

def test_job_manager_maintenance_mode(tmp_path: Path):
    jm = JobManager(base_jobs_dir=tmp_path)
    jm.set_maintenance_mode(True)

    # Regular user is blocked
    with pytest.raises(MaintenanceModeError):
        jm.create_job(
            user_id=100,
            chat_id=100,
            original_filename="song.mp3",
            file_ext=".mp3",
            is_admin=False,
            enforce_limits=True,
        )

    # Admin bypasses maintenance mode
    job = jm.create_job(
        user_id=1,
        chat_id=1,
        original_filename="admin_song.mp3",
        file_ext=".mp3",
        is_admin=True,
        enforce_limits=True,
    )
    assert job is not None
    assert job.user_id == 1


def test_job_manager_user_concurrency_limit(tmp_path: Path):
    jm = JobManager(base_jobs_dir=tmp_path, max_user_concurrent_jobs=1)

    # 1st job succeeds
    job1 = jm.create_job(
        user_id=200,
        chat_id=200,
        original_filename="song1.mp3",
        file_ext=".mp3",
        is_admin=False,
        enforce_limits=True,
    )
    assert job1 is not None

    # 2nd concurrent job for the same user is blocked
    with pytest.raises(UserConcurrentJobLimitError):
        jm.create_job(
            user_id=200,
            chat_id=200,
            original_filename="song2.mp3",
            file_ext=".mp3",
            is_admin=False,
            enforce_limits=True,
        )

    # Admin bypasses per-user limit
    admin_job2 = jm.create_job(
        user_id=200,
        chat_id=200,
        original_filename="song2_admin.mp3",
        file_ext=".mp3",
        is_admin=True,
        enforce_limits=True,
    )
    assert admin_job2 is not None


def test_job_manager_global_concurrency_limit(tmp_path: Path):
    jm = JobManager(base_jobs_dir=tmp_path, max_user_concurrent_jobs=5, max_global_concurrent_jobs=2)

    # Create 2 jobs from different users
    jm.create_job(user_id=301, chat_id=301, original_filename="s1.mp3", file_ext=".mp3")
    jm.create_job(user_id=302, chat_id=302, original_filename="s2.mp3", file_ext=".mp3")

    # 3rd global job is blocked
    with pytest.raises(GlobalConcurrentJobLimitError):
        jm.create_job(
            user_id=303,
            chat_id=303,
            original_filename="s3.mp3",
            file_ext=".mp3",
            is_admin=False,
            enforce_limits=True,
        )

    # Admin bypasses global limit
    admin_job = jm.create_job(
        user_id=303,
        chat_id=303,
        original_filename="s3.mp3",
        file_ext=".mp3",
        is_admin=True,
        enforce_limits=True,
    )
    assert admin_job is not None


# ==============================================================================
# 3. AudioCutter Timeout and Failure Cleanup Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_audio_cutter_failure_unlinks_output(tmp_path: Path):
    input_file = tmp_path / "corrupt_input.mp3"
    input_file.write_bytes(b"NOT_A_VALID_AUDIO_FILE")
    output_file = tmp_path / "failed_output.mp3"
    output_file.write_bytes(b"partial junk bytes")

    # Verify output file exists before cut
    assert output_file.exists()

    success = await AudioCutter.cut_audio(
        input_path=input_file,
        output_path=output_file,
        start_seconds=1.0,
        end_seconds=3.0,
    )

    assert success is False
    # The output file must be cleaned up / unlinked on failure
    assert not output_file.exists()


@pytest.mark.asyncio
async def test_audio_cutter_timeout_cleanup(sample_mp3: Path, tmp_path: Path):
    output_file = tmp_path / "timeout_output.mp3"
    output_file.write_bytes(b"leftover bytes")

    # Mock subprocess.run to simulate timeout
    import subprocess
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1.0)):
        success = await AudioCutter.cut_audio(
            input_path=sample_mp3,
            output_path=output_file,
            start_seconds=0.0,
            end_seconds=2.0,
        )
        assert success is False
        assert not output_file.exists()


# ==============================================================================
# 4. Resilient Broadcast Engine Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_broadcast_service_execution_and_resilience(test_repo: DatabaseRepository):
    broadcast_service = BroadcastService(test_repo)
    broadcast_id = await test_repo.create_broadcast_record(
        admin_id=1,
        source_chat_id=10,
        source_message_id=20,
        text_preview="Reliability Test Broadcast",
        total_targets=4,
    )
    assert broadcast_id > 0

    mock_bot = MagicMock()

    # User 1: success
    # User 2: FloodWait then success
    # User 3: Blocked (TelegramForbiddenError)
    # User 4: BadRequest (TelegramBadRequest)
    flood_wait_raised = False

    async def mock_copy_message(chat_id, from_chat_id, message_id):
        nonlocal flood_wait_raised
        if chat_id == 101:
            return MagicMock()
        elif chat_id == 102:
            if not flood_wait_raised:
                flood_wait_raised = True
                raise TelegramRetryAfter(
                    method=MagicMock(),
                    message="Flood control exceeded",
                    retry_after=0.1,
                )
            return MagicMock()
        elif chat_id == 103:
            raise TelegramForbiddenError(
                method=MagicMock(),
                message="Forbidden: bot was blocked by the user",
            )
        elif chat_id == 104:
            raise TelegramBadRequest(
                method=MagicMock(),
                message="Bad Request: user not found",
            )
        return MagicMock()

    mock_bot.copy_message = AsyncMock(side_effect=mock_copy_message)

    targets = [101, 102, 103, 104]
    progress_updates = []

    async def on_progress(processed, total, delivered, blocked, failed):
        progress_updates.append((processed, delivered, blocked, failed))

    result = await broadcast_service.execute_broadcast(
        bot=mock_bot,
        broadcast_id=broadcast_id,
        source_chat_id=10,
        source_message_id=20,
        target_user_ids=targets,
        progress_callback=on_progress,
    )

    assert result["total"] == 4
    assert result["delivered"] == 2
    assert result["blocked"] == 1
    assert result["failed"] == 1
    assert result["status"] == "completed"

    # Verify DB persistence
    record = await test_repo.get_broadcast_record(broadcast_id)
    assert record is not None
    assert record.delivered_count == 2
    assert record.blocked_count == 1
    assert record.failed_count == 1
    assert record.status == "completed"
    assert record.source_chat_id == 10
    assert record.source_message_id == 20
    assert "Reliability Test" in record.text_preview


@pytest.mark.asyncio
async def test_broadcast_service_cancellation(test_repo: DatabaseRepository):
    broadcast_service = BroadcastService(test_repo)
    broadcast_id = await test_repo.create_broadcast_record(
        admin_id=1,
        source_chat_id=10,
        source_message_id=20,
        text_preview="Cancel Test Broadcast",
        total_targets=10,
    )

    mock_bot = MagicMock()

    async def slow_copy(chat_id, from_chat_id, message_id):
        # Cancel after processing user 1
        if chat_id == 1:
            broadcast_service.cancel_broadcast(broadcast_id)
        return MagicMock()

    mock_bot.copy_message = AsyncMock(side_effect=slow_copy)

    targets = list(range(1, 11))
    result = await broadcast_service.execute_broadcast(
        bot=mock_bot,
        broadcast_id=broadcast_id,
        source_chat_id=10,
        source_message_id=20,
        target_user_ids=targets,
    )

    assert result["status"] == "cancelled"
    assert result["delivered"] < 10

    # Verify DB persistence reflects cancellation
    record = await test_repo.get_broadcast_record(broadcast_id)
    assert record is not None
    assert record.status == "cancelled"


# ==============================================================================
# 5. Database Online Backup and Retention Pruning Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_database_online_backup_and_pruning(test_repo: DatabaseRepository, tmp_path: Path):
    backups_dir = tmp_path / "backups"

    # Create dummy older backups to test retention
    backups_dir.mkdir(parents=True, exist_ok=True)
    old_file_1 = backups_dir / "bot_backup_20200101_000000.db"
    old_file_1.write_bytes(b"dummy old backup")
    # Set modification time to 100 days ago
    past_time = time.time() - (100 * 86400)
    import os
    os.utime(old_file_1, (past_time, past_time))

    old_file_2 = backups_dir / "bot_backup_20200102_000000.db"
    old_file_2.write_bytes(b"dummy old backup 2")
    os.utime(old_file_2, (past_time, past_time))

    # Add data to current DB
    await test_repo.set_system_setting("backup_test_key", "backup_test_val")

    # Run backup with retention_days = 7
    backup_path = await test_repo.backup_database(backups_dir, retention_days=7)
    assert backup_path.exists()
    assert backup_path.stat().st_size > 0

    # Verify that the backup file is a valid SQLite DB with the saved key
    def _verify_backup():
        conn = sqlite3.connect(str(backup_path))
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_settings WHERE key = 'backup_test_key';")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    val = await asyncio.to_thread(_verify_backup)
    assert val == "backup_test_val"

    # Verify that pruning kept at least 2 newest backups and cleaned up properly
    existing = list(backups_dir.glob("bot_backup_*.db"))
    assert len(existing) >= 2


# ==============================================================================
# 6. Job State Reconciliation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_reconcile_interrupted_jobs(test_db: Database, test_repo: DatabaseRepository):
    conn = await test_db.connect()

    now = datetime.now(timezone.utc).isoformat()
    # Insert dummy jobs with different statuses matching active_jobs schema
    await conn.execute(
        """
        INSERT INTO active_jobs (uuid, user_id, chat_id, filename, file_size, status, created_at, updated_at)
        VALUES
            ('job-active', 101, 101, 'song1.mp3', 1024, 'active', ?, ?),
            ('job-processing', 102, 102, 'song2.mp3', 2048, 'processing', ?, ?),
            ('job-queued', 103, 103, 'song3.mp3', 4096, 'queued', ?, ?),
            ('job-done', 104, 104, 'song4.mp3', 8192, 'completed', ?, ?);
        """,
        (now, now, now, now, now, now, now, now),
    )
    await conn.commit()

    # Reconcile dangling jobs
    interrupted_count = await test_repo.reconcile_interrupted_jobs()
    assert interrupted_count == 3

    # Check statuses
    async with conn.execute("SELECT uuid, status FROM active_jobs ORDER BY uuid;") as cursor:
        rows = {r["uuid"]: r["status"] for r in await cursor.fetchall()}

    assert rows["job-active"] == "interrupted"
    assert rows["job-processing"] == "interrupted"
    assert rows["job-queued"] == "interrupted"
    assert rows["job-done"] == "completed"


# ==============================================================================
# 7. Admin Capability Checks
# ==============================================================================

def test_admin_capability_permissions():
    settings = Settings(bot_token="test_token", admin_ids=[1001, 1002])

    # Superadmins have all capabilities
    assert has_admin_capability(1001, AdminCapability.SUPERADMIN, settings) is True
    assert has_admin_capability(1001, AdminCapability.BROADCAST, settings) is True
    assert has_admin_capability(1001, AdminCapability.SYSTEM_MAINTENANCE, settings) is True
    assert has_admin_capability(1001, AdminCapability.MANAGE_CHANNELS, settings) is True
    assert has_admin_capability(1001, AdminCapability.MANAGE_ACCESS, settings) is True
    assert has_admin_capability(1001, AdminCapability.VIEW_AUDIT, settings) is True

    # Non-admin has no capabilities
    assert has_admin_capability(9999, AdminCapability.SUPERADMIN, settings) is False
    assert has_admin_capability(9999, AdminCapability.BROADCAST, settings) is False
    assert has_admin_capability(9999, AdminCapability.SYSTEM_MAINTENANCE, settings) is False
