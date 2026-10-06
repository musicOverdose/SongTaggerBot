"""Audio file upload handler: size verification, queueing, download, and initial inspection."""

import asyncio
import logging
from pathlib import Path
import shutil

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.audio.format_detector import FormatDetector
from app.audio.metadata_manager import MetadataManager
from app.audio.models import AudioFormat
from app.audio.probe import AudioProber
from app.bot.formatting import format_metadata_preview
from app.bot.keyboards.main_menu import get_preview_keyboard
from app.config import Settings
from app.database.repository import DatabaseRepository
from app.services.job_manager import (
    GlobalConcurrentJobLimitError,
    JobManager,
    MaintenanceModeError,
    UserConcurrentJobLimitError,
)
from app.services.queue_manager import QueueManager
from app.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

router = Router(name="audio_upload_router")


@router.message(F.audio | F.document)
async def handle_audio_upload(
    message: Message,
    state: FSMContext,
    settings: Settings,
    job_manager: JobManager,
    queue_manager: QueueManager,
    metadata_manager: MetadataManager,
    repository: DatabaseRepository,
    rate_limiter: RateLimiter,
) -> None:
    await state.clear()

    if not message.from_user:
        return

    is_admin = settings.is_admin(message.from_user.id)

    # 1. Check rate limits for non-admin users
    if not is_admin:
        allowed, retry_after = rate_limiter.check(message.from_user.id)
        if not allowed:
            await message.reply(
                f"⚠️ <b>Upload rate limit reached.</b>\n\n"
                f"Please wait <b>{retry_after}s</b> before sending another audio file.",
                parse_mode="HTML",
            )
            return

    # Sync maintenance mode with database
    is_maint = await repository.is_maintenance_mode()
    job_manager.set_maintenance_mode(is_maint)

    # 2. Extract file info and validate size from Telegram metadata
    telegram_file = message.audio or message.document
    if telegram_file is None:
        return

    # Check MIME or name if document
    file_name = telegram_file.file_name or "audio.mp3"
    file_size = telegram_file.file_size or 0

    # Verify input file size limit before downloading
    if file_size > settings.max_input_bytes:
        await message.reply(
            f"❌ <b>This file is too large for the current Telegram Bot API configuration.</b>\n\n"
            f"File size: {round(file_size / (1024 * 1024), 1)} MB\n"
            f"Maximum input size: {settings.max_input_mb} MB",
            parse_mode="HTML",
        )
        return

    file_ext = Path(file_name).suffix or ".mp3"

    # 3. Create job enforced at the service boundary
    try:
        job = job_manager.create_job(
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            original_filename=file_name,
            file_ext=file_ext,
            is_admin=is_admin,
            enforce_limits=True,
        )
    except MaintenanceModeError:
        await message.reply(
            "🚧 <b>Maintenance Mode Active</b>\n\n"
            "SongTaggerBot is currently undergoing maintenance. "
            "New uploads are temporarily paused. Please check back shortly!",
            parse_mode="HTML",
        )
        return
    except UserConcurrentJobLimitError:
        await message.reply(
            "⚠️ <b>Active Session in Progress</b>\n\n"
            "You already have an active editing session. Please finish or /cancel "
            "your current track before uploading a new one.",
            parse_mode="HTML",
        )
        return
    except GlobalConcurrentJobLimitError:
        await message.reply(
            "🚦 <b>Server Busy</b>\n\n"
            "The bot is currently handling maximum concurrent audio jobs. "
            "Please try again in a few moments.",
            parse_mode="HTML",
        )
        return

    # 4. Define async task to execute in worker queue
    status_msg = await message.reply("⏳ <i>Processing file...</i>", parse_mode="HTML")

    async def process_upload():
        try:
            # Download file from Telegram
            bot = message.bot
            file_info = await bot.get_file(telegram_file.file_id)
            await bot.download_file(file_info.file_path, destination=job.original_path)

            # Copy to working file
            shutil.copy2(job.original_path, job.working_path)

            # Detect format
            fmt, detected_ext, mime = FormatDetector.detect_format(job.working_path)
            if fmt == AudioFormat.UNKNOWN:
                job_manager.cleanup_job(job.uuid)
                await repository.increment_stat("files_failed")
                await status_msg.edit_text(
                    "❌ <b>Unable to read this audio file.</b>\n\n"
                    "Format: unknown\n"
                    "Reason: unsupported or corrupted file",
                    parse_mode="HTML",
                )
                return

            job.format = fmt
            if detected_ext and not job.file_ext.lower() == detected_ext.lower():
                # Correct extension if original was missing or incorrect
                job.file_ext = detected_ext
                new_working_name = Path(job.working_filename).stem + detected_ext
                job.working_filename = new_working_name

            # Read metadata
            meta = await metadata_manager.read_metadata(job.working_path, fmt)
            job.original_metadata = meta
            job.working_metadata = meta.clone()

            # Extract embedded cover if present
            if meta.has_cover:
                cover_dim = await metadata_manager.extract_cover(
                    job.working_path, job.cover_original_path, fmt
                )
                if cover_dim:
                    job.working_metadata.cover_dimensions = cover_dim

            # Probe technical info
            tech_info = await AudioProber.probe(job.working_path)
            job.technical_info = tech_info

            # Register in database & record stats
            await repository.register_job(
                uuid_str=job.uuid,
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                filename=job.working_filename,
                file_size=file_size,
            )
            await repository.record_user_activity(message.from_user.id)
            await repository.increment_stat("files_received")

            # Show metadata preview
            preview_text = format_metadata_preview(
                filename=job.working_filename,
                metadata=job.working_metadata,
                tech_info=job.technical_info,
            )
            kb = get_preview_keyboard(job.uuid)
            await status_msg.edit_text(preview_text, reply_markup=kb, parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error processing audio upload for job {job.uuid}: {e}", exc_info=True)
            job_manager.cleanup_job(job.uuid)
            await repository.increment_stat("files_failed")
            await status_msg.edit_text(
                "❌ <b>Failed to process audio file.</b>\n\n"
                "The file may be corrupted or incompatible.",
                parse_mode="HTML",
            )

    # 4. Enqueue in worker queue
    future, position, is_busy = await queue_manager.enqueue(
        job_id=job.uuid,
        user_id=message.from_user.id,
        task_func=process_upload,
    )

    if is_busy and position > 1:
        await status_msg.edit_text(
            f"⏳ <b>Your file has been queued.</b>\n\nPosition: {position}",
            parse_mode="HTML",
        )
