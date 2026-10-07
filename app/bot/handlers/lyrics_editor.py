"""Lyrics submenu and multiline editor handlers."""

import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards.lyrics_menu import get_lyrics_menu_keyboard
from app.bot.states.editor_states import EditorStates
from app.database.repository import DatabaseRepository
from app.services.job_manager import JobManager

logger = logging.getLogger(__name__)

router = Router(name="lyrics_editor_router")


@router.callback_query(F.data.startswith("lyrics_menu:"))
async def callback_lyrics_menu(callback: CallbackQuery, state: FSMContext, job_manager: JobManager) -> None:
    await state.clear()
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    status_str = "✅ Embedded" if (job.working_metadata.lyrics and job.working_metadata.lyrics.strip()) else "— Not set"
    text = (
        f"🎤 <b>Lyrics</b>\n\n"
        f"<b>Status:</b> {status_str}"
    )
    kb = get_lyrics_menu_keyboard(job.uuid)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("lyrics_preview:"))
async def callback_lyrics_preview(callback: CallbackQuery, job_manager: JobManager) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    lyrics = job.working_metadata.lyrics
    if not lyrics or not lyrics.strip():
        await callback.answer("ℹ️ No lyrics available to preview.", show_alert=True)
        return

    # Truncate safely for Telegram 4096 character limit
    display_lyrics = lyrics.strip()
    if len(display_lyrics) > 3800:
        display_lyrics = display_lyrics[:3800] + "\n\n... [Truncated for preview]"

    text = f"🎤 <b>Lyrics Preview:</b>\n\n<pre>{display_lyrics}</pre>"
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩ Back to Lyrics Menu", callback_data=f"lyrics_menu:{job.uuid}")]
        ]
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("lyrics_remove:"))
async def callback_lyrics_remove(
    callback: CallbackQuery,
    job_manager: JobManager,
    repository: DatabaseRepository,
) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    job.record_change("lyrics", "")
    await repository.increment_stat("lyrics_updated")
    await callback.answer("🗑 Lyrics removed from working file.", show_alert=True)

    text = "🎤 <b>Lyrics</b>\n\n<b>Status:</b> — Not set"
    kb = get_lyrics_menu_keyboard(job.uuid)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("lyrics_edit:"))
async def callback_lyrics_edit_prompt(
    callback: CallbackQuery,
    state: FSMContext,
    job_manager: JobManager,
) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    await state.set_state(EditorStates.waiting_for_lyrics)
    await state.update_data(job_uuid=job_uuid)

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩ Cancel", callback_data=f"lyrics_menu:{job.uuid}")]
        ]
    )
    text = (
        "🎤 <b>Edit Lyrics</b>\n\n"
        "Send the multiline lyrics text in your next message."
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=cancel_kb, parse_mode="HTML")
    await callback.answer()


@router.message(EditorStates.waiting_for_lyrics)
async def process_lyrics_text(
    message: Message,
    state: FSMContext,
    job_manager: JobManager,
    repository: DatabaseRepository,
) -> None:
    data = await state.get_data()
    job_uuid = data.get("job_uuid")
    await state.clear()

    if not job_uuid or not message.text:
        return

    job = job_manager.get_job(job_uuid)
    if not job:
        await message.reply("⚠️ Session expired. Please upload file again.")
        return

    new_lyrics = message.text.strip()
    job.record_change("lyrics", new_lyrics)
    await repository.increment_stat("lyrics_updated")

    text = "🎤 <b>Lyrics</b>\n\nStatus:\n✅ Embedded\n\n<i>Lyrics updated successfully!</i>"
    kb = get_lyrics_menu_keyboard(job.uuid)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
