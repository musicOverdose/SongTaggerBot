"""Inline field editing handler using FSM."""

import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.formatting import format_metadata_preview, val_or_dash
from app.bot.keyboards.editor_menu import get_editor_keyboard
from app.bot.states.editor_states import EditorStates
from app.services.job_manager import JobManager

logger = logging.getLogger(__name__)

router = Router(name="field_editor_router")

FIELD_NAMES_MAP = {
    "title": "Title",
    "artist": "Artist",
    "album": "Album",
    "albumartist": "Album Artist",
    "date": "Year / Date",
    "genre": "Genre",
    "track_number": "Track Number",
    "disc_number": "Disc Number",
    "composer": "Composer",
    "comment": "Comment",
    "copyright": "Copyright",
    "grouping": "Grouping",
    "bpm": "BPM",
    "publisher": "Publisher",
    "conductor": "Conductor",
    "compilation": "Compilation (Yes/No)",
    "sort_title": "Sort Title",
    "sort_artist": "Sort Artist",
    "sort_album": "Sort Album",
    "sort_album_artist": "Sort Album Artist",
    "isrc": "ISRC Code",
}


@router.callback_query(F.data.startswith("field:"))
async def callback_edit_field(
    callback: CallbackQuery,
    state: FSMContext,
    job_manager: JobManager,
) -> None:
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Invalid request.")
        return

    _, field_name, job_uuid = parts
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired or invalid.", show_alert=True)
        return

    current_val = getattr(job.working_metadata, field_name, None)
    display_name = FIELD_NAMES_MAP.get(field_name, field_name.capitalize())

    await state.set_state(EditorStates.waiting_for_field_value)
    await state.update_data(job_uuid=job_uuid, field_name=field_name)

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩ Cancel", callback_data=f"edit_menu:{job.uuid}")]
        ]
    )

    prompt = (
        f"<b>Current {display_name}:</b> <code>{val_or_dash(str(current_val) if current_val is not None else None)}</code>\n\n"
        f"Send the new {display_name}."
    )
    if callback.message:
        await callback.message.edit_text(prompt, reply_markup=cancel_kb, parse_mode="HTML")
    await callback.answer()


@router.message(EditorStates.waiting_for_field_value)
async def process_field_value(
    message: Message,
    state: FSMContext,
    job_manager: JobManager,
) -> None:
    data = await state.get_data()
    job_uuid = data.get("job_uuid")
    field_name = data.get("field_name")
    await state.clear()

    if not job_uuid or not field_name:
        return

    job = job_manager.get_job(job_uuid)
    if not job:
        await message.reply("⚠️ Session expired. Please upload the file again.")
        return

    user_text = message.text.strip() if message.text else ""

    # Parse and validate based on field type
    parsed_value = user_text
    if field_name == "track_number":
        if "/" in user_text:
            parts = user_text.split("/", 1)
            try:
                job.record_change("track_number", int(parts[0].strip()))
                job.record_change("track_total", int(parts[1].strip()))
            except ValueError:
                pass
            parsed_value = None
        else:
            try:
                parsed_value = int(user_text) if user_text else None
            except ValueError:
                parsed_value = None
    elif field_name == "disc_number":
        if "/" in user_text:
            parts = user_text.split("/", 1)
            try:
                job.record_change("disc_number", int(parts[0].strip()))
                job.record_change("disc_total", int(parts[1].strip()))
            except ValueError:
                pass
            parsed_value = None
        else:
            try:
                parsed_value = int(user_text) if user_text else None
            except ValueError:
                parsed_value = None
    elif field_name == "bpm":
        try:
            parsed_value = int(float(user_text)) if user_text else None
        except ValueError:
            parsed_value = None
    elif field_name == "compilation":
        parsed_value = user_text.lower() in ("1", "true", "yes", "y")

    if parsed_value is not None:
        job.record_change(field_name, parsed_value)

    # Redraw editor with updated state
    text = format_metadata_preview(
        filename=job.working_filename,
        metadata=job.working_metadata,
        tech_info=job.technical_info,
    )
    kb = get_editor_keyboard(job.uuid)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
