"""Finish handler: committing tags, thumbnail generation, sending file, and cleanup."""

import logging
from pathlib import Path
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

from app.audio.cover_manager import CoverManager
from app.audio.metadata_manager import MetadataManager
from app.audio.models import AudioFormat
from app.audio.probe import AudioProber
from app.config import Settings
from app.database.repository import DatabaseRepository
from app.services.job_manager import JobManager
from app.services.queue_manager import QueueManager

logger = logging.getLogger(__name__)

router = Router(name="finish_handler_router")


@router.callback_query(F.data.startswith("finish:"))
async def callback_finish(
    callback: CallbackQuery,
    state: FSMContext,
    job_manager: JobManager,
    queue_manager: QueueManager,
    metadata_manager: MetadataManager,
    settings: Settings,
    repository: DatabaseRepository,
) -> None:
    await state.clear()
    job_uuid = callback.data.split(":", 1)[1]
    job = job_manager.get_job(job_uuid)
    if not job:
        await callback.answer("⚠️ Session expired or invalid.", show_alert=True)
        return

    status_msg = await callback.message.reply(
        "⏳ <b>Finalizing and saving your audio file...</b>",
        parse_mode="HTML",
    )
    await callback.answer()

    async def execute_finish():
        try:
            bot = callback.bot

            # 1. Apply cover modifications if pending
            if job.pending_cover_action == "remove":
                await metadata_manager.remove_cover(job.working_path, job.format)
                job.working_metadata.has_cover = False
                job.working_metadata.cover_dimensions = None
            elif job.pending_cover_action == "new" and job.cover_new_path.exists():
                await metadata_manager.embed_cover(job.working_path, job.cover_new_path, job.format)
                job.working_metadata.has_cover = True

            # 2. Write staged metadata to the working file (WITHOUT re-encoding audio!)
            write_success = await metadata_manager.write_metadata(
                job.working_path, job.working_metadata, job.format
            )
            if not write_success:
                logger.warning(f"Metadata write warning on {job.working_path}")

            # 3. Verify resulting file
            if not job.working_path.exists():
                await status_msg.edit_text("❌ <b>Error:</b> Output file missing.", parse_mode="HTML")
                job_manager.cleanup_job(job.uuid)
                return

            output_size = job.working_path.stat().st_size
            if output_size == 0:
                await status_msg.edit_text("❌ <b>Error:</b> Output file is empty.", parse_mode="HTML")
                job_manager.cleanup_job(job.uuid)
                return

            if output_size > settings.max_output_bytes:
                await status_msg.edit_text(
                    f"❌ <b>Resulting file exceeds Telegram upload limit.</b>\n\n"
                    f"Size: {round(output_size / (1024 * 1024), 1)} MB\n"
                    f"Max output: {settings.max_output_mb} MB",
                    parse_mode="HTML",
                )
                job_manager.cleanup_job(job.uuid)
                return

            # Re-probe for fresh technical and tag stats
            final_tech = await AudioProber.probe(job.working_path)

            # 4. Generate Telegram-compliant thumbnail (<=320x320, <=200 KB JPEG)
            thumb_input_path: Path | None = None
            if job.pending_cover_action == "new" and job.cover_new_path.exists():
                thumb_input_path = job.cover_new_path
            elif job.working_metadata.has_cover:
                # Extract cover to thumbnail source
                extracted = await metadata_manager.extract_cover(
                    job.working_path, job.cover_original_path, job.format
                )
                if extracted and job.cover_original_path.exists():
                    thumb_input_path = job.cover_original_path

            has_thumb = False
            if thumb_input_path and thumb_input_path.exists():
                has_thumb = await CoverManager.generate_telegram_thumbnail(
                    thumb_input_path, job.thumbnail_path
                )

            thumb_file = FSInputFile(str(job.thumbnail_path)) if has_thumb and job.thumbnail_path.exists() else None

            # 5. Send file directly without caption or extra attachments
            audio_file = FSInputFile(str(job.working_path), filename=job.working_filename)

            if job.format in (AudioFormat.MP3, AudioFormat.M4A):
                # Send as Telegram native music audio
                duration = int(final_tech.duration_seconds) if final_tech else None
                performer = job.working_metadata.artist or job.working_metadata.albumartist
                title = job.working_metadata.title or job.working_filename

                await bot.send_audio(
                    chat_id=job.chat_id,
                    audio=audio_file,
                    duration=duration,
                    performer=performer,
                    title=title,
                    thumbnail=thumb_file,
                )
            else:
                # Send as Document with thumbnail for FLAC, OGG, OPUS, WAV, AIFF, WMA
                await bot.send_document(
                    chat_id=job.chat_id,
                    document=audio_file,
                    thumbnail=thumb_file,
                )

            # 8. Update stats & database
            await repository.increment_stat("files_processed")
            await repository.increment_stat("total_processed_bytes", output_size)
            await repository.update_job_status(job.uuid, "completed")

            # 9. Cleanup temporary job directory and messages
            job_manager.cleanup_job(job.uuid)
            try:
                await status_msg.delete()
            except Exception:
                pass

            if callback.message:
                try:
                    await callback.message.delete()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error finalizing job {job.uuid}: {e}", exc_info=True)
            job_manager.cleanup_job(job.uuid)
            await repository.increment_stat("files_failed")
            await status_msg.edit_text(
                "❌ <b>Error occurred while processing file.</b>\n"
                "Please try again.",
                parse_mode="HTML",
            )

    await queue_manager.enqueue(
        job_id=job.uuid,
        user_id=callback.from_user.id,
        task_func=execute_finish,
    )
