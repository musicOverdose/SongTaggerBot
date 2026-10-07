"""Tests for MessageService: defaults, placeholders, HTML validation, persistence, reset, and audit trail."""

from pathlib import Path
import pytest
from aiogram.types import User

from app.database.connection import Database
from app.database.repository import DatabaseRepository
from app.services.message_service import (
    DEFAULT_HELP_MESSAGE,
    DEFAULT_MUST_JOIN_MESSAGE,
    DEFAULT_WELCOME_MESSAGE,
    MessageService,
)


@pytest.fixture
async def msg_repo(tmp_path: Path):
    db_file = tmp_path / "test_msg.db"
    db = Database(db_file)
    await db.connect()
    repo = DatabaseRepository(db)
    yield repo
    await db.close()


@pytest.fixture
def msg_service(msg_repo: DatabaseRepository):
    return MessageService(msg_repo)


@pytest.fixture
def sample_user():
    return User(
        id=8815650422,
        is_bot=False,
        first_name="Farzad",
        username="farzad_dev",
    )


@pytest.mark.asyncio
async def test_message_service_returns_defaults_initially(msg_service: MessageService, sample_user: User):
    """When no customization exists in DB, MessageService returns built-in defaults."""
    welcome = await msg_service.get_welcome_message(sample_user)
    assert "SongTaggerBot" in welcome
    assert "Supported Formats:" in welcome

    join = await msg_service.get_must_join_message(sample_user)
    assert "Channel Membership Required" in join

    help_msg = await msg_service.get_help_message(sample_user)
    assert "How to use SongTaggerBot" in help_msg

    overview = await msg_service.get_status_overview()
    assert overview["welcome"]["is_custom"] is False
    assert overview["must_join"]["is_custom"] is False
    assert overview["help"]["is_custom"] is False


@pytest.mark.asyncio
async def test_placeholder_substitution(msg_service: MessageService, msg_repo: DatabaseRepository, sample_user: User):
    """Placeholders {first_name}, {username}, {user_id}, {bot_name} are correctly substituted."""
    custom_template = (
        "Hello <b>{first_name}</b> ({username}, ID: {user_id})! Welcome to <b>{bot_name}</b>."
    )
    ok, msg = await msg_service.set_message("welcome", custom_template, admin_id=1001)
    assert ok is True

    rendered = await msg_service.get_welcome_message(sample_user, bot_name="MusicTaggerPro")
    assert "Hello <b>Farzad</b> (@farzad_dev, ID: 8815650422)! Welcome to <b>MusicTaggerPro</b>." == rendered


def test_telegram_html_validation():
    """Valid Telegram HTML passes; invalid or unclosed tags fail."""
    # Valid tags
    valid_text = "<b>Bold</b> <i>Italic</i> <u>Underline</u> <code>Code</code> <a href=\"https://t.me\">Link</a>"
    ok, err = MessageService.validate_telegram_html(valid_text)
    assert ok is True
    assert err == ""

    # Invalid tag (<script>, <div>, etc.)
    invalid_tag = "Hello <script>alert(1)</script>"
    ok, err = MessageService.validate_telegram_html(invalid_tag)
    assert ok is False
    assert "unsupported tag" in err.lower()

    # Unclosed tag
    unclosed = "Hello <b>World"
    ok, err = MessageService.validate_telegram_html(unclosed)
    assert ok is False
    assert "unclosed" in err.lower()

    # Mismatched tag
    mismatched = "Hello <b>World</i>"
    ok, err = MessageService.validate_telegram_html(mismatched)
    assert ok is False
    assert "mismatched" in err.lower()


@pytest.mark.asyncio
async def test_custom_message_persistence_and_reset(msg_service: MessageService, msg_repo: DatabaseRepository, sample_user: User):
    """Setting a message persists it in DB; resetting removes the DB row and restores default."""
    custom_help = "📖 <b>Simple Guide:</b>\nSend music, get tags."
    ok, _ = await msg_service.set_message("help", custom_help, admin_id=1001)
    assert ok is True

    # DB row exists
    db_val = await msg_repo.get_system_setting("msg_help")
    assert db_val == custom_help

    # Rendered message is custom
    res = await msg_service.get_help_message(sample_user)
    assert "Simple Guide:" in res

    overview = await msg_service.get_status_overview()
    assert overview["help"]["is_custom"] is True

    # Reset
    ok, _ = await msg_service.reset_message("help", admin_id=1001)
    assert ok is True

    # DB row is cleanly DELETED (not duplicated default)
    db_val_after = await msg_repo.get_system_setting("msg_help", "")
    assert db_val_after == ""

    # Returns default again
    res_after = await msg_service.get_help_message(sample_user)
    assert "How to use SongTaggerBot" in res_after

    overview_after = await msg_service.get_status_overview()
    assert overview_after["help"]["is_custom"] is False


@pytest.mark.asyncio
async def test_audit_logs_recorded_on_message_changes(msg_service: MessageService, msg_repo: DatabaseRepository):
    """Audit logs are recorded whenever a message is set or reset."""
    await msg_service.set_message("must_join", "Please join <b>@OurChannel</b>!", admin_id=777)
    await msg_service.reset_message("must_join", admin_id=777)

    logs, count = await msg_repo.get_audit_logs(limit=10)
    assert count == 2
    actions = [log.action for log in logs]
    assert "reset_custom_message" in actions
    assert "update_custom_message" in actions
    assert logs[0].admin_id == 777
