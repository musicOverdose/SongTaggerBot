"""Common bot command handlers (/start, /help, /cancel)."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.must_join_menu import get_must_join_keyboard
from app.services.job_manager import JobManager
from app.services.must_join_service import MustJoinService

router = Router(name="common_router")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    welcome_text = (
        "🎵 <b>SongTaggerBot</b>\n"
        "<i>by @MusicOverdose</i>\n\n"
        "Welcome! Send any music or audio track to inspect and edit its tags.\n\n"
        "<b>Supported Formats:</b>\n"
        "• MP3, FLAC, M4A, MP4 Audio\n"
        "• OGG, OPUS, WAV, AIFF, WMA\n\n"
        "<b>Features:</b>\n"
        "• Edit Title, Artist, Album, Year, Genre, Track & Disc numbers\n"
        "• Advanced tags: Composer, Conductor, BPM, Grouping, ISRC\n"
        "• Replace, extract, or remove embedded cover art\n"
        "• Edit multiline embedded lyrics\n"
        "• Trimming & cutting audio without quality loss\n"
        "• Rename files or generate names from tags\n"
        "• Undo any change at any time\n\n"
        "Just send an audio file or document to begin!"
    )
    await message.answer(welcome_text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    help_text = (
        "📖 <b>How to use SongTaggerBot:</b>\n\n"
        "1. <b>Upload:</b> Send an audio file directly into this chat.\n"
        "2. <b>Inspect:</b> The bot displays the current tags, cover, and audio specs.\n"
        "3. <b>Edit:</b> Use inline buttons to edit tags, update cover art, or edit lyrics.\n"
        "4. <b>Undo:</b> Made a mistake? Press <b>↩ Undo</b> to revert changes.\n"
        "5. <b>Finish:</b> Press <b>✅ Finish</b> to receive your updated audio file.\n"
        "6. <b>Cancel:</b> Use /cancel anytime to discard changes and delete temporary files."
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, job_manager: JobManager) -> None:
    await state.clear()
    user_job = job_manager.get_user_active_job(message.from_user.id)
    if user_job:
        job_manager.cleanup_job(user_job.uuid)
        await message.answer("❌ Active editing session cancelled. All temporary files deleted.")
    else:
        await message.answer("ℹ️ No active editing session to cancel.")


@router.callback_query(lambda c: c.data == "must_join_verify")
async def callback_must_join_verify(
    callback: CallbackQuery,
    must_join_service: MustJoinService,
) -> None:
    bot = callback.bot
    user_id = callback.from_user.id
    has_joined, missing = await must_join_service.check_user_membership(bot, user_id)

    if has_joined:
        await callback.answer("✅ Thank you! Membership confirmed.", show_alert=True)
        if callback.message:
            await callback.message.edit_text(
                "✅ <b>Membership Verified!</b>\n\nYou can now send your audio files.",
                parse_mode="HTML",
            )
    else:
        await callback.answer("⚠️ You have not joined all required channels yet.", show_alert=True)
        if callback.message:
            kb = get_must_join_keyboard(missing)
            await callback.message.edit_reply_markup(reply_markup=kb)
