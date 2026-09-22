"""Main application entrypoint: initializes dependencies, registers routers, and starts polling."""

import asyncio
import logging
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.audio.metadata_manager import MetadataManager
from app.bot.handlers import (
    admin_handlers,
    audio_upload,
    common,
    cover_editor,
    cutter_handler,
    editor_menu,
    field_editor,
    filename_editor,
    finish_handler,
    lyrics_editor,
)
from app.bot.middleware.must_join_middleware import MustJoinMiddleware
from app.config import get_settings
from app.database.connection import Database
from app.database.repository import DatabaseRepository
from app.services.job_manager import JobManager
from app.services.must_join_service import MustJoinService
from app.services.queue_manager import QueueManager

logger = logging.getLogger("musicoverdose_bot")


async def periodic_cleanup_task(job_manager: JobManager, interval_seconds: int = 300):
    """Periodically cleans up abandoned jobs."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            cleaned = job_manager.cleanup_expired_jobs()
            if cleaned > 0:
                logger.info(f"Periodic GC: cleaned {cleaned} abandoned jobs.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Error in periodic cleanup task: {e}")


async def main():
    settings = get_settings()

    # Configure structured logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    if not settings.bot_token:
        logger.error("BOT_TOKEN is not set! Please configure it in your environment or .env file.")
        sys.exit(1)

    logger.info("Initializing MusicOverdose Audio Metadata Editor Bot...")

    # Ensure required directories exist
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)

    # Initialize Database & Services
    db = Database(settings.db_path)
    await db.connect()
    repository = DatabaseRepository(db)

    job_manager = JobManager(
        base_jobs_dir=settings.jobs_dir,
        ttl_minutes=settings.job_ttl_minutes,
    )

    queue_manager = QueueManager(max_concurrent_jobs=settings.max_concurrent_jobs)
    queue_manager.start()

    metadata_manager = MetadataManager()
    must_join_service = MustJoinService(repository)

    # Configure Bot instance (support Local Bot API server if configured)
    session = None
    if settings.telegram_api_base != "https://api.telegram.org":
        custom_server = TelegramAPIServer(
            base=f"{settings.telegram_api_base}/bot{{token}}/{{method}}",
            file=f"{settings.telegram_file_base}/file/bot{{token}}/{{path}}",
        )
        session = AiohttpSession(api=custom_server)

    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Dispatcher & FSM Memory Storage
    dp = Dispatcher(storage=MemoryStorage())

    # Dependency injection into all handlers
    dp["settings"] = settings
    dp["repository"] = repository
    dp["job_manager"] = job_manager
    dp["queue_manager"] = queue_manager
    dp["metadata_manager"] = metadata_manager
    dp["must_join_service"] = must_join_service

    # Attach Must-Join verification middleware to messages & callback queries
    dp.message.middleware(MustJoinMiddleware(must_join_service))
    dp.callback_query.middleware(MustJoinMiddleware(must_join_service))

    # Register Routers in logical priority order
    dp.include_router(common.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(audio_upload.router)
    dp.include_router(editor_menu.router)
    dp.include_router(field_editor.router)
    dp.include_router(cover_editor.router)
    dp.include_router(lyrics_editor.router)
    dp.include_router(filename_editor.router)
    dp.include_router(cutter_handler.router)
    dp.include_router(finish_handler.router)

    # Start background tasks
    cleanup_task = asyncio.create_task(periodic_cleanup_task(job_manager))

    logger.info(
        f"Bot initialized successfully. Max input: {settings.max_input_mb} MB, "
        f"Max output: {settings.max_output_mb} MB, Concurrency: {settings.max_concurrent_jobs}."
    )

    # Graceful shutdown setup
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received termination signal, shutting down...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    try:
        # Start long polling
        polling_task = asyncio.create_task(
            dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                close_bot_session=True,
            )
        )
        await stop_event.wait()
        polling_task.cancel()
        await asyncio.gather(polling_task, return_exceptions=True)
    finally:
        logger.info("Stopping background tasks and workers...")
        cleanup_task.cancel()
        await queue_manager.stop()
        await db.close()
        await bot.session.close()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
