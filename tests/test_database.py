"""Tests for Database and Repository."""

import pytest
from app.database.repository import DatabaseRepository


@pytest.mark.asyncio
async def test_required_channels_crud(test_repo: DatabaseRepository):
    # 1. Add channel
    ok = await test_repo.add_channel(channel_id="@musicoverdose", username="musicoverdose", title="MusicOverdose Official")
    assert ok is True

    # 2. List channels
    channels = await test_repo.list_channels()
    assert len(channels) == 1
    assert channels[0].channel_id == "@musicoverdose"
    assert channels[0].is_enabled is True

    # 3. Disable channel
    await test_repo.set_channel_enabled("@musicoverdose", False)
    enabled = await test_repo.list_channels(enabled_only=True)
    assert len(enabled) == 0

    # 4. Enable channel
    await test_repo.set_channel_enabled("@musicoverdose", True)
    enabled = await test_repo.list_channels(enabled_only=True)
    assert len(enabled) == 1

    # 5. Remove channel
    del_ok = await test_repo.remove_channel("@musicoverdose")
    assert del_ok is True
    assert len(await test_repo.list_channels()) == 0


@pytest.mark.asyncio
async def test_stats_tracking(test_repo: DatabaseRepository):
    await test_repo.increment_stat("files_received", 3)
    await test_repo.increment_stat("files_processed", 2)
    await test_repo.increment_stat("cuts_performed", 1)
    await test_repo.increment_stat("total_processed_bytes", 10 * 1024 * 1024)
    await test_repo.record_user_activity(999)

    stats = await test_repo.get_stats()
    assert stats.files_received == 3
    assert stats.files_processed == 2
    assert stats.cuts_performed == 1
    assert stats.unique_users == 1
    assert stats.total_processed_mb == 10.0
