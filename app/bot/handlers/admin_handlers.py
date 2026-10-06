"""Interactive Telegram Admin Panel with audit logging, resilient broadcasts, and operational statistics."""

import asyncio
import logging
from typing import Optional, Union
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.admin_menu import (
    get_admin_audit_logs_keyboard,
    get_admin_back_keyboard,
    get_admin_banlist_keyboard,
    get_admin_broadcast_confirm_keyboard,
    get_admin_broadcast_running_keyboard,
    get_admin_channels_keyboard,
    get_admin_dashboard_keyboard,
    get_admin_whitelist_keyboard,
)
from app.bot.permissions import AdminCapability, has_admin_capability
from app.bot.states.admin_states import AdminStates
from app.config import Settings, reload_settings
from app.database.repository import DatabaseRepository
from app.services.broadcast_service import BroadcastService
from app.services.job_manager import JobManager
from app.services.uptime import get_uptime_formatted

logger = logging.getLogger(__name__)

router = Router(name="admin_handlers_router")


def is_admin_check(event: Union[Message, CallbackQuery], settings: Settings) -> bool:
    """Verifies that the event originates from a configured administrator."""
    user = event.from_user
    if not user:
        return False
    return has_admin_capability(user.id, AdminCapability.SUPERADMIN, settings)


async def render_admin_dashboard(
    settings: Settings,
    repository: Optional[DatabaseRepository] = None,
    job_manager: Optional[JobManager] = None,
) -> tuple[str, any]:
    """Builds the comprehensive operational dashboard text and keyboard."""
    if repository is None:
        from app.database.connection import Database
        repository = DatabaseRepository(Database(settings.db_path))
    if job_manager is None:
        job_manager = JobManager(settings.jobs_dir)

    is_maint = await repository.is_maintenance_mode()
    stats = await repository.get_stats()
    whitelist = await repository.list_whitelist()
    banned = await repository.list_banned()
    channels = await repository.list_channels(enabled_only=True)

    active_jobs_cnt = job_manager.get_active_jobs_count()
    temp_disk_mb = job_manager.get_temp_disk_usage_mb()
    uptime_str = get_uptime_formatted()
    maint_status = "🔴 <b>ACTIVE</b>" if is_maint else "🟢 <b>Normal</b>"

    text = (
        "🎛 <b>SongTaggerBot Admin Dashboard</b>\n\n"
        f"• Status: {maint_status} | Uptime: <code>{uptime_str}</code>\n"
        f"• Active Users: <b>{stats.unique_users}</b>\n"
        f"• Channels: <b>{len(channels)} active</b>\n"
        f"• Access: <b>{len(whitelist)} whitelisted</b> | <b>{len(banned)} banned</b>\n"
        f"• Active Jobs: <b>{active_jobs_cnt}</b> | Temp Disk: <b>{temp_disk_mb} MB</b>\n"
        f"• Total Processed: <b>{stats.files_processed} files</b> ({stats.total_processed_mb} MB)"
    )
    kb = get_admin_dashboard_keyboard(maintenance_mode=is_maint)
    return text, kb


# --- Dashboard Entry Points ---

@router.message(Command("admin"))
async def cmd_admin(
    message: Message,
    state: FSMContext,
    settings: Settings,
    repository: Optional[DatabaseRepository] = None,
    job_manager: Optional[JobManager] = None,
) -> None:
    if not is_admin_check(message, settings):
        return
    await state.clear()
    text, kb = await render_admin_dashboard(settings, repository, job_manager)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "adm_home")
async def callback_admin_home(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    repository: Optional[DatabaseRepository] = None,
    job_manager: Optional[JobManager] = None,
) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    await state.clear()
    text, kb = await render_admin_dashboard(settings, repository, job_manager)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm_close")
async def callback_admin_close(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    await state.clear()
    if callback.message:
        await callback.message.delete()
    await callback.answer()


# --- Maintenance Mode Toggle ---

@router.callback_query(F.data == "adm_maint_toggle")
async def callback_adm_maint_toggle(
    callback: CallbackQuery,
    settings: Settings,
    repository: DatabaseRepository,
    job_manager: JobManager,
) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    current = await repository.is_maintenance_mode()
    new_state = not current
    await repository.set_maintenance_mode(new_state)
    job_manager.set_maintenance_mode(new_state)

    admin_id = callback.from_user.id
    await repository.log_audit_action(
        admin_id=admin_id,
        action="maintenance_mode",
        details="Enabled" if new_state else "Disabled",
    )
    status_label = "ENABLED (New user uploads paused)" if new_state else "DISABLED (Normal operations)"
    await callback.answer(f"Maintenance mode: {status_label}", show_alert=True)

    text, kb = await render_admin_dashboard(settings, repository, job_manager)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# --- Live Statistics ---

@router.message(Command("stats"))
async def cmd_stats(message: Message, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(message, settings):
        return
    stats = await repository.get_stats()
    text = (
        "📊 <b>SongTaggerBot Operational Statistics</b>\n\n"
        f"• Uptime: <code>{get_uptime_formatted()}</code>\n"
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


@router.callback_query(F.data == "adm_stats")
async def callback_adm_stats(callback: CallbackQuery, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    stats = await repository.get_stats()
    text = (
        "📊 <b>SongTaggerBot Operational Statistics</b>\n\n"
        f"• Uptime: <code>{get_uptime_formatted()}</code>\n"
        f"• Files Received: <b>{stats.files_received}</b>\n"
        f"• Files Processed: <b>{stats.files_processed}</b>\n"
        f"• Files Failed: <b>{stats.files_failed}</b>\n"
        f"• Cuts Performed: <b>{stats.cuts_performed}</b>\n"
        f"• Covers Updated: <b>{stats.covers_updated}</b>\n"
        f"• Lyrics Updated: <b>{stats.lyrics_updated}</b>\n"
        f"• Active Users: <b>{stats.unique_users}</b>\n"
        f"• Total Data Processed: <b>{stats.total_processed_mb} MB</b>"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()


# --- Configuration Reload, Cleanup & Backups ---

@router.message(Command("reloadconfig"))
async def cmd_reload_config(
    message: Message,
    settings: Settings,
    repository: Optional[DatabaseRepository] = None,
) -> None:
    if not is_admin_check(message, settings):
        return
    new_settings = reload_settings()
    if repository:
        await repository.log_audit_action(
            admin_id=message.from_user.id,
            action="reload_config",
            details="Environment reloaded",
        )
    await message.answer(
        f"🔄 <b>Configuration reloaded!</b>\n\n"
        f"• Max Input: {new_settings.max_input_mb} MB\n"
        f"• Max Output: {new_settings.max_output_mb} MB\n"
        f"• Max Workers: {new_settings.max_concurrent_jobs}\n"
        f"• Rate Limit: {new_settings.rate_limit_uploads_per_minute}/min\n"
        f"• Admins: {len(new_settings.admin_ids)}",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_reload")
async def callback_adm_reload(callback: CallbackQuery, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    new_settings = reload_settings()
    await repository.log_audit_action(
        admin_id=callback.from_user.id,
        action="reload_config",
        details="Environment reloaded via admin panel",
    )
    await callback.answer("Configuration reloaded from environment!", show_alert=True)
    if callback.message:
        text = (
            "🔄 <b>Configuration reloaded!</b>\n\n"
            f"• Max Input: {new_settings.max_input_mb} MB\n"
            f"• Max Output: {new_settings.max_output_mb} MB\n"
            f"• Max Workers: {new_settings.max_concurrent_jobs}\n"
            f"• Rate Limit: {new_settings.rate_limit_uploads_per_minute}/min\n"
            f"• Admins: {len(new_settings.admin_ids)}"
        )
        await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "adm_cleanup")
async def callback_adm_cleanup(
    callback: CallbackQuery, settings: Settings, job_manager: JobManager, repository: DatabaseRepository
) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    cleaned_expired = job_manager.cleanup_expired_jobs()
    cleaned_orphaned = job_manager.cleanup_orphaned_job_dirs()
    total_cleaned = cleaned_expired + cleaned_orphaned

    await repository.log_audit_action(
        admin_id=callback.from_user.id,
        action="gc_cleanup",
        details=f"Cleaned {total_cleaned} directories",
    )

    text = (
        f"🧹 <b>Garbage Collection Complete</b>\n\n"
        f"• Expired jobs cleaned: <b>{cleaned_expired}</b>\n"
        f"• Orphaned directories swept: <b>{cleaned_orphaned}</b>\n"
        f"• Remaining temp storage: <b>{job_manager.get_temp_disk_usage_mb()} MB</b>"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm_backup")
async def callback_adm_backup(
    callback: CallbackQuery, settings: Settings, repository: DatabaseRepository
) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return

    try:
        backup_path = await repository.backup_database(
            backup_dir=settings.backups_dir,
            retention_days=settings.backup_retention_days,
        )
        file_size_kb = round(backup_path.stat().st_size / 1024, 1)
        await repository.log_audit_action(
            admin_id=callback.from_user.id,
            action="backup_database",
            target=str(backup_path.name),
            details=f"Size: {file_size_kb} KB",
        )
        text = (
            "💾 <b>Database Online Backup Complete!</b>\n\n"
            f"• File: <code>{backup_path.name}</code>\n"
            f"• Size: <b>{file_size_kb} KB</b>\n"
            f"• Retention: <b>{settings.backup_retention_days} days</b>"
        )
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        text = f"❌ <b>Backup failed:</b> {e}"

    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()


# --- Admin Audit Logs View ---

@router.callback_query(F.data.startswith("adm_audit:"))
async def callback_adm_audit(
    callback: CallbackQuery, settings: Settings, repository: DatabaseRepository
) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return

    page_str = callback.data.split(":", 1)[1]
    page = int(page_str) if page_str.isdigit() else 0
    limit = 7
    offset = page * limit

    logs, total_count = await repository.get_audit_logs(limit=limit, offset=offset)
    total_pages = max(1, (total_count + limit - 1) // limit)

    if not logs:
        text = "📜 <b>Admin Audit Trail</b>\n\nNo administrative actions recorded yet."
    else:
        lines = [f"📜 <b>Admin Audit Trail</b> (Page {page + 1}/{total_pages})\n"]
        for log in logs:
            target_str = f" &rarr; <code>{log.target}</code>" if log.target else ""
            details_str = f" | {log.details}" if log.details else ""
            ts_short = log.created_at[:19].replace("T", " ")
            lines.append(
                f"• <b>{log.action}</b> by <code>{log.admin_id}</code>{target_str}{details_str}\n"
                f"  <i>{ts_short}</i>"
            )
        text = "\n".join(lines)

    kb = get_admin_audit_logs_keyboard(page=page, total_pages=total_pages)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# --- Must-Join Channels Management ---

@router.message(Command("channels"))
async def cmd_channels(message: Message, settings: Settings, repository: DatabaseRepository) -> None:
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


@router.callback_query(F.data == "adm_channels")
async def callback_adm_channels(callback: CallbackQuery, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    channels = await repository.list_channels()
    text = (
        "📢 <b>Must-Join Channels Management</b>\n\n"
        "Tap a channel to toggle between 🟢 Enabled and 🔴 Disabled, or tap 🗑 Delete to remove."
    )
    kb = get_admin_channels_keyboard(channels)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ch_toggle:"))
async def callback_adm_ch_toggle(callback: CallbackQuery, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    channel_id = callback.data.split(":", 1)[1]
    channels = await repository.list_channels()
    target = next((c for c in channels if c.channel_id == channel_id), None)
    if target:
        new_state = not target.is_enabled
        await repository.set_channel_enabled(channel_id, new_state)
        await repository.log_audit_action(
            admin_id=callback.from_user.id,
            action="toggle_channel",
            target=channel_id,
            details="Enabled" if new_state else "Disabled",
        )
        await callback.answer(f"Channel {'enabled' if new_state else 'disabled'}.")
    channels = await repository.list_channels()
    kb = get_admin_channels_keyboard(channels)
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(F.data.startswith("adm_ch_del:"))
async def callback_adm_ch_del(callback: CallbackQuery, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    channel_id = callback.data.split(":", 1)[1]
    await repository.remove_channel(channel_id)
    await repository.log_audit_action(
        admin_id=callback.from_user.id,
        action="remove_channel",
        target=channel_id,
    )
    await callback.answer(f"Channel {channel_id} deleted.")
    channels = await repository.list_channels()
    kb = get_admin_channels_keyboard(channels)
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(F.data == "adm_ch_add")
async def callback_adm_ch_add(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_channel_input)
    text = (
        "📢 <b>Add Required Channel</b>\n\n"
        "Please send the channel's <code>@username</code> or numeric ID (e.g. <code>-1001234567890</code>).\n"
        "Ensure the bot is added as an administrator to that channel."
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.waiting_for_channel_input)
async def process_channel_input(
    message: Message, state: FSMContext, settings: Settings, repository: DatabaseRepository
) -> None:
    if not is_admin_check(message, settings):
        return
    channel_input = message.text.strip() if message.text else ""
    if not channel_input:
        await message.reply("Please provide a valid channel identifier.")
        return

    username = channel_input.lstrip("@") if channel_input.startswith("@") else None
    success = await repository.add_channel(channel_id=channel_input, username=username)
    await state.clear()

    if success:
        await repository.log_audit_action(
            admin_id=message.from_user.id,
            action="add_channel",
            target=channel_input,
        )
        channels = await repository.list_channels()
        kb = get_admin_channels_keyboard(channels)
        await message.answer(f"✅ Successfully added channel: <b>{channel_input}</b>", reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(f"❌ Failed to add channel: <b>{channel_input}</b>", reply_markup=get_admin_back_keyboard(), parse_mode="HTML")


@router.message(Command("addchannel"))
async def cmd_add_channel(message: Message, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(message, settings):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: <code>/addchannel @username</code> or <code>/addchannel -100123456789</code>", parse_mode="HTML")
        return
    channel_input = parts[1].strip()
    username = channel_input.lstrip("@") if channel_input.startswith("@") else None
    success = await repository.add_channel(channel_id=channel_input, username=username)
    if success:
        await repository.log_audit_action(
            admin_id=message.from_user.id,
            action="add_channel",
            target=channel_input,
        )
        await message.answer(f"✅ Added required channel: <b>{channel_input}</b>", parse_mode="HTML")
    else:
        await message.answer(f"❌ Failed to add channel: <b>{channel_input}</b>", parse_mode="HTML")


@router.message(Command("delchannel"))
async def cmd_del_channel(message: Message, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(message, settings):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: <code>/delchannel @username</code> or <code>/delchannel -100123456789</code>", parse_mode="HTML")
        return
    channel_input = parts[1].strip()
    success = await repository.remove_channel(channel_input)
    if success:
        await repository.log_audit_action(
            admin_id=message.from_user.id,
            action="remove_channel",
            target=channel_input,
        )
        await message.answer(f"✅ Removed required channel: <b>{channel_input}</b>", parse_mode="HTML")
    else:
        await message.answer(f"❌ Channel not found: <b>{channel_input}</b>", parse_mode="HTML")


# --- Whitelist Management ---

@router.callback_query(F.data == "adm_whitelist")
async def callback_adm_whitelist(callback: CallbackQuery, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    whitelist = await repository.list_whitelist()
    text = (
        "⭐ <b>Must-Join Whitelist</b>\n\n"
        "Users on this list bypass mandatory channel membership checks.\n"
        f"Total whitelisted users: <b>{len(whitelist)}</b>"
    )
    kb = get_admin_whitelist_keyboard(whitelist)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm_wl_del:"))
async def callback_adm_wl_del(callback: CallbackQuery, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    user_id_str = callback.data.split(":", 1)[1]
    try:
        user_id = int(user_id_str)
        await repository.remove_from_whitelist(user_id)
        await repository.log_audit_action(
            admin_id=callback.from_user.id,
            action="remove_whitelist",
            target=str(user_id),
        )
        await callback.answer(f"Removed user {user_id} from whitelist.")
    except ValueError:
        await callback.answer("Invalid user ID.")
    whitelist = await repository.list_whitelist()
    kb = get_admin_whitelist_keyboard(whitelist)
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(F.data == "adm_wl_add")
async def callback_adm_wl_add(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_whitelist_input)
    text = (
        "⭐ <b>Add User to Whitelist</b>\n\n"
        "Send the Telegram user ID to whitelist, optionally followed by a reason:\n"
        "<code>123456789 VIP partner</code>"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.waiting_for_whitelist_input)
async def process_whitelist_input(
    message: Message, state: FSMContext, settings: Settings, repository: DatabaseRepository
) -> None:
    if not is_admin_check(message, settings):
        return
    text = message.text.strip() if message.text else ""
    parts = text.split(maxsplit=1)
    if not parts or not parts[0].isdigit():
        await message.reply("⚠️ Please enter a numeric Telegram user ID (e.g. <code>123456789</code>).", parse_mode="HTML")
        return
    user_id = int(parts[0])
    reason = parts[1] if len(parts) > 1 else None

    await repository.add_to_whitelist(user_id=user_id, reason=reason)
    await repository.log_audit_action(
        admin_id=message.from_user.id,
        action="add_whitelist",
        target=str(user_id),
        details=reason,
    )
    await state.clear()
    whitelist = await repository.list_whitelist()
    kb = get_admin_whitelist_keyboard(whitelist)
    await message.answer(f"✅ Added user <code>{user_id}</code> to whitelist.", reply_markup=kb, parse_mode="HTML")


@router.message(Command("whitelist"))
async def cmd_whitelist(message: Message, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(message, settings):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) >= 2 and parts[1].lower() == "add":
        if len(parts) < 3 or not parts[2].split()[0].isdigit():
            await message.answer("Usage: <code>/whitelist add &lt;user_id&gt; [reason]</code>", parse_mode="HTML")
            return
        sub = parts[2].split(maxsplit=1)
        uid = int(sub[0])
        reason = sub[1] if len(sub) > 1 else None
        await repository.add_to_whitelist(uid, reason=reason)
        await repository.log_audit_action(
            admin_id=message.from_user.id,
            action="add_whitelist",
            target=str(uid),
            details=reason,
        )
        await message.answer(f"✅ User <code>{uid}</code> whitelisted.", parse_mode="HTML")
    elif len(parts) >= 2 and parts[1].lower() in ("del", "remove"):
        if len(parts) < 3 or not parts[2].strip().isdigit():
            await message.answer("Usage: <code>/whitelist del &lt;user_id&gt;</code>", parse_mode="HTML")
            return
        uid = int(parts[2].strip())
        await repository.remove_from_whitelist(uid)
        await repository.log_audit_action(
            admin_id=message.from_user.id,
            action="remove_whitelist",
            target=str(uid),
        )
        await message.answer(f"✅ User <code>{uid}</code> removed from whitelist.", parse_mode="HTML")
    else:
        whitelist = await repository.list_whitelist()
        if not whitelist:
            await message.answer("⭐ Whitelist is empty.")
            return
        lines = ["⭐ <b>Whitelisted Users:</b>\n"]
        for w in whitelist:
            r = f" ({w.reason})" if w.reason else ""
            lines.append(f"• <code>{w.user_id}</code>{r}")
        await message.answer("\n".join(lines), parse_mode="HTML")


# --- Ban List Management ---

@router.callback_query(F.data == "adm_banlist")
async def callback_adm_banlist(callback: CallbackQuery, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    banned = await repository.list_banned()
    text = (
        "🚫 <b>Banned Users Management</b>\n\n"
        "Banned users are blocked from all bot functionalities at middleware level.\n"
        f"Total banned users: <b>{len(banned)}</b>"
    )
    kb = get_admin_banlist_keyboard(banned)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ban_del:"))
async def callback_adm_ban_del(callback: CallbackQuery, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    user_id_str = callback.data.split(":", 1)[1]
    try:
        user_id = int(user_id_str)
        await repository.unban_user(user_id)
        await repository.log_audit_action(
            admin_id=callback.from_user.id,
            action="unban_user",
            target=str(user_id),
        )
        await callback.answer(f"Unbanned user {user_id}.")
    except ValueError:
        await callback.answer("Invalid user ID.")
    banned = await repository.list_banned()
    kb = get_admin_banlist_keyboard(banned)
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(F.data == "adm_ban_add")
async def callback_adm_ban_add(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_ban_input)
    text = (
        "🚫 <b>Ban User</b>\n\n"
        "Send the Telegram user ID to ban, optionally followed by a reason:\n"
        "<code>123456789 spamming large files</code>"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.waiting_for_ban_input)
async def process_ban_input(
    message: Message, state: FSMContext, settings: Settings, repository: DatabaseRepository
) -> None:
    if not is_admin_check(message, settings):
        return
    text = message.text.strip() if message.text else ""
    parts = text.split(maxsplit=1)
    if not parts or not parts[0].isdigit():
        await message.reply("⚠️ Please enter a numeric Telegram user ID (e.g. <code>123456789</code>).", parse_mode="HTML")
        return
    user_id = int(parts[0])
    reason = parts[1] if len(parts) > 1 else None

    await repository.ban_user(user_id=user_id, reason=reason)
    await repository.log_audit_action(
        admin_id=message.from_user.id,
        action="ban_user",
        target=str(user_id),
        details=reason,
    )
    await state.clear()
    banned = await repository.list_banned()
    kb = get_admin_banlist_keyboard(banned)
    await message.answer(f"🚫 User <code>{user_id}</code> has been banned.", reply_markup=kb, parse_mode="HTML")


@router.message(Command("ban"))
async def cmd_ban(message: Message, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(message, settings):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Usage: <code>/ban &lt;user_id&gt; [reason]</code>", parse_mode="HTML")
        return
    uid = int(parts[1])
    reason = parts[2] if len(parts) > 2 else None
    await repository.ban_user(uid, reason=reason)
    await repository.log_audit_action(
        admin_id=message.from_user.id,
        action="ban_user",
        target=str(uid),
        details=reason,
    )
    await message.answer(f"🚫 User <code>{uid}</code> has been banned.", parse_mode="HTML")


@router.message(Command("unban"))
async def cmd_unban(message: Message, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(message, settings):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Usage: <code>/unban &lt;user_id&gt;</code>", parse_mode="HTML")
        return
    uid = int(parts[1].strip())
    await repository.unban_user(uid)
    await repository.log_audit_action(
        admin_id=message.from_user.id,
        action="unban_user",
        target=str(uid),
    )
    await message.answer(f"✅ User <code>{uid}</code> has been unbanned.", parse_mode="HTML")


@router.message(Command("banlist"))
async def cmd_banlist(message: Message, settings: Settings, repository: DatabaseRepository) -> None:
    if not is_admin_check(message, settings):
        return
    banned = await repository.list_banned()
    if not banned:
        await message.answer("🚫 Ban list is empty.")
        return
    lines = ["🚫 <b>Banned Users:</b>\n"]
    for b in banned:
        r = f" ({b.reason})" if b.reason else ""
        lines.append(f"• <code>{b.user_id}</code>{r}")
    await message.answer("\n".join(lines), parse_mode="HTML")


# --- Broadcast Announcement Workflow with Cancellation ---

@router.callback_query(F.data == "adm_broadcast")
async def callback_adm_broadcast(
    callback: CallbackQuery, state: FSMContext, settings: Settings, repository: DatabaseRepository
) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return
    user_ids = await repository.get_all_active_user_ids()
    await state.set_state(AdminStates.waiting_for_broadcast_content)
    text = (
        "📣 <b>Broadcast Announcement</b>\n\n"
        f"Recipient Pool: <b>{len(user_ids)} active users</b>\n\n"
        "Send the message (text, photo, markdown, etc.) you wish to broadcast to all users."
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.waiting_for_broadcast_content)
async def process_broadcast_content(message: Message, state: FSMContext, settings: Settings) -> None:
    if not is_admin_check(message, settings):
        return
    await state.set_state(AdminStates.waiting_for_broadcast_confirm)
    text_preview = message.text or message.caption or "(media message)"
    await state.update_data(
        bcast_msg_id=message.message_id,
        bcast_chat_id=message.chat.id,
        bcast_preview=text_preview[:120],
    )

    kb = get_admin_broadcast_confirm_keyboard()
    await message.reply(
        "👁 <b>Broadcast Message Preview Above</b>\n\n"
        "Do you want to send this broadcast to all active users?",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_bcast_cancel:"))
async def callback_adm_bcast_cancel(
    callback: CallbackQuery,
    settings: Settings,
    repository: DatabaseRepository,
    broadcast_service: Optional[BroadcastService] = None,
) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return

    bcast_id_str = callback.data.split(":", 1)[1]
    if bcast_id_str.isdigit() and broadcast_service:
        bcast_id = int(bcast_id_str)
        broadcast_service.cancel_broadcast(bcast_id)
        await repository.log_audit_action(
            admin_id=callback.from_user.id,
            action="broadcast_cancel",
            target=str(bcast_id),
        )
        await callback.answer("🛑 Broadcast cancellation requested. Stopping safely...", show_alert=True)
    else:
        await callback.answer("Unable to cancel broadcast.")


@router.callback_query(F.data == "adm_bcast_confirm")
async def callback_adm_bcast_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    repository: DatabaseRepository,
    broadcast_service: Optional[BroadcastService] = None,
) -> None:
    if not is_admin_check(callback, settings):
        await callback.answer("Unauthorized.", show_alert=True)
        return

    data = await state.get_data()
    msg_id = data.get("bcast_msg_id")
    from_chat_id = data.get("bcast_chat_id")
    preview = data.get("bcast_preview")
    await state.clear()

    if not msg_id or not from_chat_id:
        await callback.answer("Session expired.", show_alert=True)
        return

    user_ids = await repository.get_all_active_user_ids()
    total_users = len(user_ids)
    if total_users == 0:
        await callback.answer("No active users found to broadcast to.", show_alert=True)
        return

    # Create persistent broadcast history record
    admin_id = callback.from_user.id
    bcast_id = await repository.create_broadcast_record(
        admin_id=admin_id,
        source_chat_id=from_chat_id,
        source_message_id=msg_id,
        text_preview=preview,
        total_targets=total_users,
    )

    await repository.log_audit_action(
        admin_id=admin_id,
        action="broadcast_start",
        target=str(bcast_id),
        details=f"Targets: {total_users}",
    )

    if broadcast_service is None:
        broadcast_service = BroadcastService(repository)

    running_kb = get_admin_broadcast_running_keyboard(bcast_id)
    status_msg = await callback.message.edit_text(
        f"⏳ <b>Dispatching broadcast #{bcast_id}...</b>\n0 / {total_users} delivered",
        reply_markup=running_kb,
        parse_mode="HTML",
    )

    async def update_ui(processed: int, total: int, delivered: int, blocked: int, failed: int):
        remaining = total - processed
        try:
            await status_msg.edit_text(
                f"⏳ <b>Dispatching broadcast #{bcast_id}...</b>\n"
                f"• Processed: <b>{processed} / {total}</b>\n"
                f"• Delivered: <b>{delivered}</b> | Blocked: <b>{blocked}</b> | Failed: <b>{failed}</b>\n"
                f"• Remaining: <b>{remaining}</b>",
                reply_markup=running_kb,
                parse_mode="HTML",
            )
        except Exception:
            pass

    results = await broadcast_service.execute_broadcast(
        bot=callback.bot,
        broadcast_id=bcast_id,
        source_chat_id=from_chat_id,
        source_message_id=msg_id,
        target_user_ids=user_ids,
        progress_callback=update_ui,
    )

    status_icon = "🛑" if results["status"] == "cancelled" else "📣"
    status_title = "Broadcast Cancelled" if results["status"] == "cancelled" else "Broadcast Complete"

    summary = (
        f"{status_icon} <b>{status_title}!</b> (ID #{bcast_id})\n\n"
        f"• Total Targets: <b>{results['total']}</b>\n"
        f"• Successfully Delivered: <b>{results['delivered']}</b>\n"
        f"• Blocked / Deactivated: <b>{results['blocked']}</b>\n"
        f"• Failed / Unreachable: <b>{results['failed']}</b>"
    )
    await status_msg.edit_text(summary, reply_markup=get_admin_back_keyboard(), parse_mode="HTML")
    await callback.answer()
