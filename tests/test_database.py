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


@pytest.mark.asyncio
async def test_whitelist_crud(test_repo: DatabaseRepository):
    # 1. Add user to whitelist
    ok = await test_repo.add_to_whitelist(user_id=111222, username="tester1", reason="Beta tester")
    assert ok is True

    # 2. Check is_whitelisted
    assert await test_repo.is_whitelisted(111222) is True
    assert await test_repo.is_whitelisted(999999) is False

    # 3. List whitelist
    wl = await test_repo.list_whitelist()
    assert len(wl) == 1
    assert wl[0].user_id == 111222
    assert wl[0].reason == "Beta tester"

    # 4. Remove from whitelist
    removed = await test_repo.remove_from_whitelist(111222)
    assert removed is True
    assert await test_repo.is_whitelisted(111222) is False
    assert len(await test_repo.list_whitelist()) == 0


@pytest.mark.asyncio
async def test_ban_crud(test_repo: DatabaseRepository):
    # 1. Ban user
    ok = await test_repo.ban_user(user_id=444555, username="spammer", reason="Flood")
    assert ok is True

    # 2. Check is_banned
    assert await test_repo.is_banned(444555) is True
    assert await test_repo.is_banned(123456) is False

    # 3. List banned users
    banned = await test_repo.list_banned()
    assert len(banned) == 1
    assert banned[0].user_id == 444555
    assert banned[0].reason == "Flood"

    # 4. Unban user
    unbanned = await test_repo.unban_user(444555)
    assert unbanned is True
    assert await test_repo.is_banned(444555) is False
    assert len(await test_repo.list_banned()) == 0


@pytest.mark.asyncio
async def test_active_users_for_broadcast(test_repo: DatabaseRepository):
    await test_repo.record_user_activity(1001)
    await test_repo.record_user_activity(1002)
    await test_repo.record_user_activity(1003)

    user_ids = await test_repo.get_all_active_user_ids()
    assert len(user_ids) == 3
    assert 1001 in user_ids
    assert 1002 in user_ids
    assert 1003 in user_ids

