"""Tests for MustJoinService."""

from unittest.mock import AsyncMock, MagicMock
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberMember, ChatMemberLeft
import pytest

from app.database.repository import DatabaseRepository
from app.services.must_join_service import MustJoinService


@pytest.mark.asyncio
async def test_must_join_evaluation(test_repo: DatabaseRepository):
    service = MustJoinService(test_repo)

    # 1. No required channels configured -> always True
    mock_bot = MagicMock()
    has_joined, missing = await service.check_user_membership(mock_bot, 12345)
    assert has_joined is True
    assert len(missing) == 0

    # 2. Add required channels
    await test_repo.add_channel("@chan1", username="chan1")
    await test_repo.add_channel("@chan2", username="chan2")

    # Case A: User is member of both
    mock_bot.get_chat_member = AsyncMock(
        return_value=MagicMock(status=ChatMemberStatus.MEMBER)
    )
    has_joined, missing = await service.check_user_membership(mock_bot, 12345)
    assert has_joined is True
    assert len(missing) == 0

    # Case B: User left chan2
    async def fake_get_chat_member(chat_id, user_id):
        if "chan2" in chat_id:
            return MagicMock(status=ChatMemberStatus.LEFT)
        return MagicMock(status=ChatMemberStatus.MEMBER)

    mock_bot.get_chat_member = AsyncMock(side_effect=fake_get_chat_member)
    has_joined, missing = await service.check_user_membership(mock_bot, 12345)
    assert has_joined is False
    assert len(missing) == 1
    assert missing[0].channel_id == "@chan2"
