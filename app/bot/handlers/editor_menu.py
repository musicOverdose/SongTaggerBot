"""Editor navigation handlers: switching screens, previewing, undo, and cancel."""

import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.formatting import format_metadata_preview, format_technical_info
from app.bot.keyboards.editor_menu import get_advanced_editor_keyboard, get_editor_keyboard
from app.bot.keyboards.main_menu import get_preview_keyboard
from app.services.job_manager import JobManager

logger = logging.getLogger(__name__)

router = Router(name="editor_menu_router")


@router.callback_query(F.data.startswith("edit_menu:"))
async def callback_edit_menu(callback: CallbackQuery, state: FSMContext, job_manager: JobManager) -> None:
    await state.clear()
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired or invalid.", show_alert=True)
        return

    text = format_metadata_preview(
        filename=job.working_filename,
        metadata=job.working_metadata,
        tech_info=job.technical_info,
    )
    kb = get_editor_keyboard(job.uuid)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adv_menu:"))
async def callback_adv_menu(callback: CallbackQuery, state: FSMContext, job_manager: JobManager) -> None:
    await state.clear()
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired or invalid.", show_alert=True)
        return

    text = format_metadata_preview(
        filename=job.working_filename,
        metadata=job.working_metadata,
        tech_info=job.technical_info,
    )
    kb = get_advanced_editor_keyboard(job.uuid)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("preview:"))
async def callback_preview(callback: CallbackQuery, state: FSMContext, job_manager: JobManager) -> None:
    await state.clear()
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired or invalid.", show_alert=True)
        return

    text = format_metadata_preview(
        filename=job.working_filename,
        metadata=job.working_metadata,
        tech_info=job.technical_info,
    )
    kb = get_preview_keyboard(job.uuid)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("file_info:"))
async def callback_file_info(callback: CallbackQuery, job_manager: JobManager) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job or not job.technical_info:
        await callback.answer("⚠️ File info unavailable.", show_alert=True)
        return

    text = format_technical_info(
        filename=job.working_filename,
        tech_info=job.technical_info,
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩ Back", callback_data=f"preview:{job.uuid}")]
        ]
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("undo:"))
async def callback_undo(callback: CallbackQuery, job_manager: JobManager) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired or invalid.", show_alert=True)
        return

    change = job.undo_last_change()
    if change is None:
        await callback.answer("ℹ️ Nothing to undo.", show_alert=False)
        return

    await callback.answer(f"↩ Reverted {change.field_name}", show_alert=False)

    # Redraw current preview
    text = format_metadata_preview(
        filename=job.working_filename,
        metadata=job.working_metadata,
        tech_info=job.technical_info,
    )
    kb = get_editor_keyboard(job.uuid)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("cancel:"))
async def callback_cancel(callback: CallbackQuery, state: FSMContext, job_manager: JobManager) -> None:
    await state.clear()
    job_uuid = callback.data.split(":", 1)[1]
    job_manager.cleanup_job(job_uuid)
    if callback.message:
        await callback.message.edit_text(
            "❌ <b>Editing cancelled.</b>\nAll temporary changes were discarded.",
            parse_mode="HTML",
        )
    await callback.answer()
