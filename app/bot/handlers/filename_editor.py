"""Filename submenu and generator handlers."""

import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards.filename_menu import get_filename_menu_keyboard
from app.bot.states.editor_states import EditorStates
from app.config import Settings
from app.services.filename_service import FilenameService
from app.services.job_manager import JobManager

logger = logging.getLogger(__name__)

router = Router(name="filename_editor_router")


@router.callback_query(F.data.startswith("fn_menu:"))
async def callback_filename_menu(callback: CallbackQuery, state: FSMContext, job_manager: JobManager) -> None:
    await state.clear()
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    text = (
        f"📝 <b>Filename Options</b>\n\n"
        f"Current filename:\n<code>{job.working_filename}</code>"
    )
    kb = get_filename_menu_keyboard(job.uuid)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("fn_edit:"))
async def callback_filename_edit_prompt(
    callback: CallbackQuery,
    state: FSMContext,
    job_manager: JobManager,
) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    await state.set_state(EditorStates.waiting_for_filename)
    await state.update_data(job_uuid=job_uuid)

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩ Cancel", callback_data=f"fn_menu:{job.uuid}")]
        ]
    )
    text = (
        f"Current filename:\n<code>{job.working_filename}</code>\n\n"
        f"Send the new filename.\n<i>(Extension may be omitted)</i>"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=cancel_kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("fn_generate:"))
async def callback_filename_generate(
    callback: CallbackQuery,
    job_manager: JobManager,
    settings: Settings,
) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    generated = FilenameService.generate_from_metadata(
        metadata=job.working_metadata,
        expected_ext=job.file_ext,
        template=settings.default_filename_format,
        fallback_name=job.original_filename,
    )
    job.working_filename = generated

    await callback.answer(f"✨ Generated: {generated}", show_alert=False)
    text = (
        f"📝 <b>Filename Options</b>\n\n"
        f"Current filename:\n<code>{job.working_filename}</code>\n\n"
        f"<i>Filename updated from tags!</i>"
    )
    kb = get_filename_menu_keyboard(job.uuid)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.message(EditorStates.waiting_for_filename)
async def process_filename_input(
    message: Message,
    state: FSMContext,
    job_manager: JobManager,
) -> None:
    data = await state.get_data()
    job_uuid = data.get("job_uuid")
    await state.clear()

    if not job_uuid or not message.text:
        return

    job = job_manager.get_job(job_uuid)
    if not job:
        await message.reply("⚠️ Session expired.")
        return

    sanitized = FilenameService.sanitize(message.text.strip(), expected_ext=job.file_ext)
    job.working_filename = sanitized

    text = (
        f"📝 <b>Filename Options</b>\n\n"
        f"Current filename:\n<code>{job.working_filename}</code>\n\n"
        f"<i>Filename updated successfully!</i>"
    )
    kb = get_filename_menu_keyboard(job.uuid)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
