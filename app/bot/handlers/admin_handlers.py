"""Administrator-only Telegram commands."""

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import Settings, reload_settings
from app.database.repository import DatabaseRepository

logger = logging.getLogger(__name__)

router = Router(name="admin_handlers_router")


def is_admin_check(message: Message, settings: Settings) -> bool:
    if not message.from_user:
        return False
    return settings.is_admin(message.from_user.id)


@router.message(Command("channels"))
async def admin_list_channels(
    message: Message,
    settings: Settings,
    repository: DatabaseRepository,
) -> None:
    if not is_admin_check(message, settings):
        return

    channels = await repository.list_channels()
    if not channels:
        await message.answer("📢 No required channels configured.")
        return

    lines = ["📢 <b>Required Channels:</b>\n"]
    for c in channels:
        status_emoji = "🟢 Enabled" if c.is_enabled else "🔴 Disabled"
        display = c.username or c.channel_id
        lines.append(f"• <b>{display}</b> ({status_emoji}) - ID: <code>{c.channel_id}</code>")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("addchannel"))
async def admin_add_channel(
    message: Message,
    settings: Settings,
    repository: DatabaseRepository,
) -> None:
    if not is_admin_check(message, settings):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: <code>/addchannel @username</code> or <code>/addchannel -100123456789</code>", parse_mode="HTML")
        return

    channel_input = parts[1].strip()
    username = channel_input.lstrip("@") if channel_input.startswith("@") else None
    channel_id = channel_input

    success = await repository.add_channel(
        channel_id=channel_id,
        username=username,
    )
    if success:
        await message.answer(f"✅ Added required channel: <b>{channel_input}</b>", parse_mode="HTML")
    else:
        await message.answer(f"❌ Failed to add channel: <b>{channel_input}</b>", parse_mode="HTML")


@router.message(Command("delchannel"))
async def admin_del_channel(
    message: Message,
    settings: Settings,
    repository: DatabaseRepository,
) -> None:
    if not is_admin_check(message, settings):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: <code>/delchannel @username</code> or <code>/delchannel -100123456789</code>", parse_mode="HTML")
        return

    channel_input = parts[1].strip()
    success = await repository.remove_channel(channel_input)
    if success:
        await message.answer(f"✅ Removed required channel: <b>{channel_input}</b>", parse_mode="HTML")
    else:
        await message.answer(f"❌ Channel not found: <b>{channel_input}</b>", parse_mode="HTML")


@router.message(Command("stats"))
async def admin_stats(
    message: Message,
    settings: Settings,
    repository: DatabaseRepository,
) -> None:
    if not is_admin_check(message, settings):
        return

    stats = await repository.get_stats()
    text = (
        "📊 <b>MusicOverdose Bot Statistics</b>\n\n"
        f"• Files Received: <b>{stats.files_received}</b>\n"
        f"• Files Processed: <b>{stats.files_processed}</b>\n"
        f"• Files Failed: <b>{stats.files_failed}</b>\n"
        f"• Cuts Performed: <b>{stats.cuts_performed}</b>\n"
        f"• Covers Updated: <b>{stats.covers_updated}</b>\n"
        f"• Lyrics Updated: <b>{stats.lyrics_updated}</b>\n"
        f"• Active Users: <b>{stats.unique_users}</b>\n"
        f"• Total Data Processed: <b>{stats.total_processed_mb} MB</b>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("reloadconfig"))
async def admin_reload_config(message: Message, settings: Settings) -> None:
    if not is_admin_check(message, settings):
        return

    new_settings = reload_settings()
    await message.answer(
        f"🔄 <b>Configuration reloaded!</b>\n\n"
        f"• Max Input: {new_settings.max_input_mb} MB\n"
        f"• Max Output: {new_settings.max_output_mb} MB\n"
        f"• Max Workers: {new_settings.max_concurrent_jobs}\n"
        f"• Admins: {len(new_settings.admin_ids)}",
        parse_mode="HTML",
    )
