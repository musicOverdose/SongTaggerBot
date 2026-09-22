"""Audio trimming handler using FFmpeg."""

import logging
from pathlib import Path
import shutil
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.audio.cutter import AudioCutter
from app.audio.metadata_manager import MetadataManager
from app.audio.probe import AudioProber
from app.bot.formatting import format_metadata_preview
from app.bot.keyboards.cut_menu import get_cut_confirm_keyboard, get_cut_menu_keyboard
from app.bot.keyboards.main_menu import get_preview_keyboard
from app.bot.states.editor_states import EditorStates
from app.database.repository import DatabaseRepository
from app.services.job_manager import JobManager
from app.services.queue_manager import QueueManager

logger = logging.getLogger(__name__)

router = Router(name="cutter_handler_router")


@router.callback_query(F.data.startswith("cut_menu:"))
async def callback_cut_menu(callback: CallbackQuery, state: FSMContext, job_manager: JobManager) -> None:
    await state.clear()
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    dur_str = job.technical_info.duration_formatted if job.technical_info else "Unknown"
    text = (
        f"✂️ <b>Audio Cut / Trim</b>\n\n"
        f"Current Duration: <b>{dur_str}</b>\n\n"
        f"Press <b>Enter cut range</b> to specify start and end timestamps."
    )
    kb = get_cut_menu_keyboard(job.uuid)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("cut_enter:"))
async def callback_cut_enter_prompt(
    callback: CallbackQuery,
    state: FSMContext,
    job_manager: JobManager,
) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    await state.set_state(EditorStates.waiting_for_cut_range)
    await state.update_data(job_uuid=job_uuid)

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩ Cancel", callback_data=f"cut_menu:{job.uuid}")]
        ]
    )
    text = (
        "✂️ <b>Enter Cut Range</b>\n\n"
        "Send the start and end time in your next message.\n\n"
        "<b>Examples:</b>\n"
        "• <code>00:10 - 03:45</code>\n"
        "• <code>00:00:10 - 00:03:45</code>\n"
        "• <code>start 00:10 end 03:45</code>\n"
        "• <code>10 - 90</code> (in seconds)"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=cancel_kb, parse_mode="HTML")
    await callback.answer()


@router.message(EditorStates.waiting_for_cut_range)
async def process_cut_range_input(
    message: Message,
    state: FSMContext,
    job_manager: JobManager,
) -> None:
    data = await state.get_data()
    job_uuid = data.get("job_uuid")
    if not job_uuid or not message.text:
        return

    job = job_manager.get_job(job_uuid)
    if not job:
        await message.reply("⚠️ Session expired.")
        await state.clear()
        return

    parsed = AudioCutter.parse_time_range(message.text.strip())
    if not parsed:
        await message.reply(
            "⚠️ <b>Invalid time range.</b>\n"
            "Please use format: <code>00:10 - 03:45</code> or <code>10 - 90</code>",
            parse_mode="HTML",
        )
        return

    start_sec, end_sec = parsed
    new_duration = end_sec - start_sec
    if new_duration <= 0:
        await message.reply("⚠️ End time must be greater than start time.")
        return

    await state.set_state(EditorStates.confirming_cut)
    await state.update_data(job_uuid=job_uuid, start_sec=start_sec, end_sec=end_sec)

    start_fmt = AudioCutter.format_seconds(start_sec)
    end_fmt = AudioCutter.format_seconds(end_sec)
    dur_fmt = AudioCutter.format_seconds(new_duration)

    confirm_text = (
        f"✂️ <b>Audio Cut</b>\n\n"
        f"Start: <b>{start_fmt}</b>\n"
        f"End: <b>{end_fmt}</b>\n"
        f"New duration: <b>{dur_fmt}</b>"
    )
    kb = get_cut_confirm_keyboard(job.uuid)
    await message.reply(confirm_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("cut_apply:"))
async def callback_cut_apply(
    callback: CallbackQuery,
    state: FSMContext,
    job_manager: JobManager,
    queue_manager: QueueManager,
    metadata_manager: MetadataManager,
    repository: DatabaseRepository,
) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    data = await state.get_data()
    start_sec = data.get("start_sec")
    end_sec = data.get("end_sec")
    await state.clear()

    if not job or start_sec is None or end_sec is None:
        await callback.answer("⚠️ Session expired or invalid cut parameters.", show_alert=True)
        return

    status_msg = await callback.message.reply("⏳ <i>Trimming audio with FFmpeg...</i>", parse_mode="HTML")
    await callback.answer()

    async def execute_cut():
        cut_output = job.cut_temp_path
        success = await AudioCutter.cut_audio(
            input_path=job.working_path,
            output_path=cut_output,
            start_seconds=start_sec,
            end_seconds=end_sec,
        )

        if not success or not cut_output.exists():
            await status_msg.edit_text("❌ <b>Trimming failed.</b> Original working file preserved.", parse_mode="HTML")
            return

        # Replace working file with cut file
        shutil.move(str(cut_output), str(job.working_path))

        # Reapply working metadata to cut file
        await metadata_manager.write_metadata(job.working_path, job.working_metadata, job.format)

        # Re-probe technical info
        job.technical_info = await AudioProber.probe(job.working_path)
        await repository.increment_stat("cuts_performed")

        text = format_metadata_preview(
            filename=job.working_filename,
            metadata=job.working_metadata,
            tech_info=job.technical_info,
        )
        kb = get_preview_keyboard(job.uuid)
        await status_msg.edit_text(
            f"✂️ <b>Audio Trimmed Successfully!</b>\n\n{text}",
            reply_markup=kb,
            parse_mode="HTML",
        )

    await queue_manager.enqueue(
        job_id=job.uuid,
        user_id=callback.from_user.id,
        task_func=execute_cut,
    )
