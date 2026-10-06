"""Tests for Telegram Admin Panel handlers and security permissions."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey

from app.bot.handlers.admin_handlers import (
    cmd_admin,
    cmd_ban,
    cmd_unban,
    cmd_whitelist,
    cmd_stats,
    cmd_reload_config,
    is_admin_check,
)
from app.config import Settings
from app.database.repository import DatabaseRepository


@pytest.fixture
def fsm_context():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=100, user_id=100)
    return FSMContext(storage=storage, key=key)


@pytest.mark.asyncio
async def test_admin_permission_check():
    settings = Settings(bot_token="test", admin_ids=[1001, 1002])

    # Admin message
    msg_admin = MagicMock()
    msg_admin.from_user.id = 1001
    assert is_admin_check(msg_admin, settings) is True

    # Non-admin message
    msg_user = MagicMock()
    msg_user.from_user.id = 9999
    assert is_admin_check(msg_user, settings) is False


@pytest.mark.asyncio
async def test_cmd_admin_dashboard(fsm_context):
    settings = Settings(bot_token="test", admin_ids=[1001])

    # Admin execution
    msg = MagicMock()
    msg.from_user.id = 1001
    msg.answer = AsyncMock()

    await cmd_admin(msg, fsm_context, settings)
    msg.answer.assert_called_once()
    assert "SongTaggerBot Admin Dashboard" in msg.answer.call_args[0][0]

    # Non-admin execution
    msg_unauthorized = MagicMock()
    msg_unauthorized.from_user.id = 9999
    msg_unauthorized.answer = AsyncMock()

    await cmd_admin(msg_unauthorized, fsm_context, settings)
    msg_unauthorized.answer.assert_not_called()


@pytest.mark.asyncio
async def test_admin_whitelist_and_ban_commands(test_repo: DatabaseRepository, fsm_context):
    settings = Settings(bot_token="test", admin_ids=[1001])

    msg = MagicMock()
    msg.from_user.id = 1001
    msg.answer = AsyncMock()

    # 1. Ban user
    msg.text = "/ban 777 spammer"
    await cmd_ban(msg, settings, test_repo)
    assert await test_repo.is_banned(777) is True
    assert "banned" in msg.answer.call_args[0][0].lower()

    # 2. Unban user
    msg.text = "/unban 777"
    await cmd_unban(msg, settings, test_repo)
    assert await test_repo.is_banned(777) is False
    assert "unbanned" in msg.answer.call_args[0][0].lower()

    # 3. Whitelist user
    msg.text = "/whitelist add 888 VIP"
    await cmd_whitelist(msg, settings, test_repo)
    assert await test_repo.is_whitelisted(888) is True
    assert "whitelisted" in msg.answer.call_args[0][0].lower()

    # 4. Remove from whitelist
    msg.text = "/whitelist del 888"
    await cmd_whitelist(msg, settings, test_repo)
    assert await test_repo.is_whitelisted(888) is False


@pytest.mark.asyncio
async def test_admin_stats_and_reload(test_repo: DatabaseRepository):
    settings = Settings(bot_token="test", admin_ids=[1001])

    msg = MagicMock()
    msg.from_user.id = 1001
    msg.answer = AsyncMock()

    # Stats
    await cmd_stats(msg, settings, test_repo)
    msg.answer.assert_called_once()
    assert "Statistics" in msg.answer.call_args[0][0]

    # Reload config
    msg.answer.reset_mock()
    await cmd_reload_config(msg, settings)
    msg.answer.assert_called_once()
    assert "reloaded" in msg.answer.call_args[0][0].lower()
