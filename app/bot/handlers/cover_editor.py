"""Cover art submenu and image upload handlers."""

import logging
from pathlib import Path
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.audio.cover_manager import CoverManager
from app.bot.keyboards.cover_menu import get_cover_confirm_keyboard, get_cover_menu_keyboard
from app.bot.states.editor_states import EditorStates
from app.config import Settings
from app.database.repository import DatabaseRepository
from app.services.file_acquisition import (
    FileAcquisitionService,
    LocalFileAccessError,
    SecurityError,
)
from app.services.job_manager import JobManager

logger = logging.getLogger(__name__)

router = Router(name="cover_editor_router")


@router.callback_query(F.data.startswith("cover_menu:"))
async def callback_cover_menu(callback: CallbackQuery, state: FSMContext, job_manager: JobManager) -> None:
    await state.clear()
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    if job.pending_cover_action == "remove":
        current_status = "🗑 Marked for removal"
    elif job.pending_cover_action == "new" and job.cover_new_path.exists():
        current_status = "🆕 New cover staged"
    elif job.working_metadata.has_cover:
        dim = job.working_metadata.cover_dimensions
        dim_str = f"{dim[0]} × {dim[1]}" if dim else "Embedded"
        current_status = f"✅ Embedded cover\n{dim_str}"
    else:
        current_status = "— None"

    text = (
        f"🖼 <b>Cover Art</b>\n\n"
        f"<b>Status:</b> {current_status}"
    )
    kb = get_cover_menu_keyboard(job.uuid)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("cover_view:"))
async def callback_cover_view(callback: CallbackQuery, job_manager: JobManager) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    # Check new cover first, then original cover
    target_cover: Path | None = None
    if job.pending_cover_action == "new" and job.cover_new_path.exists():
        target_cover = job.cover_new_path
    elif job.cover_original_path.exists():
        target_cover = job.cover_original_path

    if target_cover and target_cover.exists():
        photo_file = FSInputFile(str(target_cover))
        await callback.message.reply_photo(photo=photo_file, caption="🖼 Current Album Artwork")
        await callback.answer()
    else:
        await callback.answer("ℹ️ No cover art embedded in this file.", show_alert=True)


@router.callback_query(F.data.startswith("cover_remove:"))
async def callback_cover_remove(
    callback: CallbackQuery,
    job_manager: JobManager,
    repository: DatabaseRepository,
) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    job.pending_cover_action = "remove"
    job.working_metadata.has_cover = False
    job.working_metadata.cover_dimensions = None
    await repository.increment_stat("covers_updated")
    await callback.answer("🗑 Cover art marked for removal on finish.", show_alert=True)

    text = "🖼 <b>Cover Art</b>\n\nCurrent:\n🗑 Marked for removal"
    kb = get_cover_menu_keyboard(job.uuid)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("cover_upload:"))
async def callback_cover_upload_prompt(
    callback: CallbackQuery,
    state: FSMContext,
    job_manager: JobManager,
) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    await state.set_state(EditorStates.waiting_for_cover)
    await state.update_data(job_uuid=job_uuid)

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩ Cancel", callback_data=f"cover_menu:{job.uuid}")]
        ]
    )
    text = (
        "📤 <b>Upload New Cover</b>\n\n"
        "Send an image file (JPG, PNG, or WebP) as a photo or uncompressed document."
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=cancel_kb, parse_mode="HTML")
    await callback.answer()


@router.message(EditorStates.waiting_for_cover, F.photo | F.document)
async def process_cover_upload(
    message: Message,
    state: FSMContext,
    job_manager: JobManager,
    settings: Settings = None,
    file_acquisition: FileAcquisitionService = None,
) -> None:
    data = await state.get_data()
    job_uuid = data.get("job_uuid")
    if not job_uuid:
        return

    job = job_manager.get_job(job_uuid)
    if not job:
        await message.reply("⚠️ Session expired. Please upload the file again.")
        await state.clear()
        return

    # Acquire image to temp location
    bot = message.bot
    temp_img = job.dir_path / "temp_upload_cover"

    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    else:
        return

    acquisition_svc = file_acquisition or FileAcquisitionService(settings or Settings())
    try:
        await acquisition_svc.acquire_file(bot, file_id, destination=temp_img)
    except LocalFileAccessError as e:
        logger.error(f"Local file acquisition error for cover: {e}")
        await message.reply(
            "❌ <b>Local Bot API storage is unavailable.</b>\n\n"
            "Could not read cover image from the centralized volume.",
            parse_mode="HTML",
        )
        return
    except SecurityError as e:
        logger.error(f"Security violation during cover acquisition: {e}")
        await message.reply("❌ <b>Access Denied:</b> Invalid file path.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"Failed to acquire cover image: {e}")
        await message.reply("❌ <b>Failed to download image.</b> Please try again.", parse_mode="HTML")
        return

    # Validate image
    is_valid, fmt, dims, size_bytes = await CoverManager.validate_image(temp_img)
    if not is_valid or dims is None:
        if temp_img.exists():
            temp_img.unlink()
        await message.reply(
            "❌ <b>Invalid image file.</b>\n"
            "Please send a valid JPG, PNG, or WebP image.",
            parse_mode="HTML",
        )
        return

    # Prepare high-quality cover
    await CoverManager.prepare_embedded_cover(temp_img, job.cover_new_path)
    if temp_img.exists():
        temp_img.unlink()

    w, h = dims
    size_kb = round(size_bytes / 1024, 1)

    await state.set_state(EditorStates.confirming_cover)
    await state.update_data(job_uuid=job_uuid, dimensions=dims)

    confirm_text = (
        f"<b>Cover received.</b>\n\n"
        f"{w} × {h} {fmt}\n"
        f"{size_kb} KB"
    )
    kb = get_cover_confirm_keyboard(job.uuid)
    await message.reply(confirm_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("cover_confirm:"))
async def callback_cover_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    job_manager: JobManager,
    repository: DatabaseRepository,
) -> None:
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    data = await state.get_data()
    dims = data.get("dimensions")
    await state.clear()

    if not job:
        await callback.answer("⚠️ Session expired.", show_alert=True)
        return

    job.pending_cover_action = "new"
    job.working_metadata.has_cover = True
    if dims:
        job.working_metadata.cover_dimensions = tuple(dims)

    await repository.increment_stat("covers_updated")
    await callback.answer("✅ New cover staged! Press Finish to save.", show_alert=True)

    # Return to cover menu
    text = (
        f"🖼 <b>Cover Art</b>\n\n"
        f"Current:\n🆕 New cover staged ({dims[0]} × {dims[1]} JPEG)"
    )
    kb = get_cover_menu_keyboard(job.uuid)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
