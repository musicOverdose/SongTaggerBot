"""Extended integration and edge case tests."""

import asyncio
from pathlib import Path
import shutil
import time
from unittest.mock import MagicMock, patch
import pytest

from app.audio.models import AudioFormat, AudioMetadata
from app.audio.metadata_manager import MetadataManager
from app.cli import async_main
from app.config import Settings
from app.services.job_manager import JobManager


@pytest.mark.asyncio
async def test_undo_multiple_changes_in_sequence(sample_mp3: Path, tmp_path: Path):
    test_file = tmp_path / "undo_test.mp3"
    shutil.copy2(sample_mp3, test_file)

    mgr = JobManager(base_jobs_dir=tmp_path / "jobs", ttl_minutes=30)
    job = mgr.create_job(1, 1, "test.mp3", ".mp3")

    # Initial state
    job.working_metadata = AudioMetadata(title="Original Title", artist="Original Artist")

    # Change 1: Title
    job.record_change("title", "Changed Title 1")
    assert job.working_metadata.title == "Changed Title 1"

    # Change 2: Artist
    job.record_change("artist", "Changed Artist 1")
    assert job.working_metadata.artist == "Changed Artist 1"

    # Change 3: Title again
    job.record_change("title", "Changed Title 2")
    assert job.working_metadata.title == "Changed Title 2"

    # Undo 1 -> Reverts title back to Changed Title 1
    c1 = job.undo_last_change()
    assert c1.field_name == "title"
    assert job.working_metadata.title == "Changed Title 1"

    # Undo 2 -> Reverts artist back to Original Artist
    c2 = job.undo_last_change()
    assert c2.field_name == "artist"
    assert job.working_metadata.artist == "Original Artist"

    # Undo 3 -> Reverts title back to Original Title
    c3 = job.undo_last_change()
    assert c3.field_name == "title"
    assert job.working_metadata.title == "Original Title"

    mgr.cleanup_job(job.uuid)


def test_abandoned_jobs_garbage_collection(tmp_path: Path):
    jobs_dir = tmp_path / "jobs"
    mgr = JobManager(base_jobs_dir=jobs_dir, ttl_minutes=1)  # 1 minute TTL

    job = mgr.create_job(2, 2, "old.mp3", ".mp3")
    assert job.dir_path.exists()

    # Manually age the job past TTL
    job.last_activity = time.time() - 120

    cleaned = mgr.cleanup_expired_jobs()
    assert cleaned >= 1
    assert not job.dir_path.exists()
    assert mgr.get_job(job.uuid) is None


def test_custom_api_server_config():
    # Verify local bot API URL configuration
    s = Settings(
        telegram_api_mode="local",
        telegram_api_base_url="http://localhost:8081",
        max_input_mb=2000,
        max_output_mb=2000,
    )
    assert s.max_input_bytes == 2000 * 1024 * 1024
    assert s.telegram_api_mode == "local"
    assert s.is_local_mode is True
    assert s.effective_api_base_url == "http://localhost:8081"


@pytest.mark.asyncio
async def test_cli_argument_parsing(tmp_path: Path):
    db_file = tmp_path / "cli_test.db"
    settings = Settings(data_dir=tmp_path, temp_dir=tmp_path / "temp")

    with patch("app.cli.get_settings", return_value=settings):
        with patch("sys.argv", ["cli", "channels", "add", "@testchannel"]):
            await async_main()

        with patch("sys.argv", ["cli", "channels", "list"]):
            await async_main()

        with patch("sys.argv", ["cli", "stats"]):
            await async_main()

        with patch("sys.argv", ["cli", "cleanup"]):
            await async_main()

        with patch("sys.argv", ["cli", "channels", "remove", "@testchannel"]):
            await async_main()


def test_compact_metadata_preview_formatting():
    from app.audio.models import AudioMetadata, AudioTechnicalInfo
    from app.bot.formatting import format_metadata_preview, format_technical_info

    meta = AudioMetadata(
        title="Tell më",
        artist="Yeat",
        album="2093",
        albumartist="Various Artists",
        date="2024-12-11",
        genre="Rap/Hip Hop",
        track_number=10,
        track_total=30,
        has_cover=True,
        cover_dimensions=(1200, 1200),
        lyrics="Sample lyrics",
        has_lyrics=True,
    )
    tech = AudioTechnicalInfo(
        format_name="MP3",
        codec_name="mp3",
        mime_type="audio/mpeg",
        duration_seconds=243.0,
        file_size_bytes=int(9.4 * 1024 * 1024),
        bitrate_kbps=320,
        sample_rate_hz=44100,
        channel_layout="Stereo",
    )
    result = format_metadata_preview("10. Yeat - Tell më.mp3", meta, tech)

    # Verify bold labels
    assert "<b>File:</b> <code>10. Yeat - Tell më.mp3</code>" in result
    assert "<b>Title:</b> Tell më" in result
    assert "<b>Artist:</b> Yeat" in result
    assert "<b>Album:</b> 2093" in result
    assert "<b>Album Artist:</b> Various Artists" in result
    assert "<b>Year:</b> 2024-12-11" in result
    assert "<b>Genre:</b> Rap/Hip Hop" in result
    assert "<b>Track:</b> 10 / 30" in result
    assert "<b>Cover:</b> ✅ 1200×1200" in result
    assert "<b>Lyrics:</b> ✅ Present" in result
    assert "<b>Audio:</b> MP3 • 320 kbps • 44.1 kHz • Stereo\n04:03 • 9.4 MB" in result

    # Verify no redundant blank lines between adjacent fields
    assert "<b>Title:</b> Tell më\n<b>Artist:</b> Yeat" in result
    assert "<b>Artist:</b> Yeat\n<b>Album:</b> 2093" in result

    # Test technical info formatting
    tech_info_text = format_technical_info("10. Yeat - Tell më.mp3", tech)
    assert "<b>Filename:</b> <code>10. Yeat - Tell më.mp3</code>" in tech_info_text
    assert "<b>Format:</b> MP3" in tech_info_text


def test_navigation_keyboards_return_to_main_preview():
    from app.bot.keyboards.cover_menu import get_cover_menu_keyboard
    from app.bot.keyboards.cut_menu import get_cut_menu_keyboard
    from app.bot.keyboards.editor_menu import get_advanced_editor_keyboard, get_editor_keyboard
    from app.bot.keyboards.filename_menu import get_filename_menu_keyboard
    from app.bot.keyboards.lyrics_menu import get_lyrics_menu_keyboard
    from app.bot.keyboards.main_menu import get_preview_keyboard

    uuid = "job_test_123"

    # Main menu
    main_kb = get_preview_keyboard(uuid)
    main_callbacks = [btn.callback_data for row in main_kb.inline_keyboard for btn in row]
    main_texts = [btn.text for row in main_kb.inline_keyboard for btn in row]
    assert f"edit_menu:{uuid}" in main_callbacks
    assert f"cover_menu:{uuid}" in main_callbacks
    assert f"lyrics_menu:{uuid}" in main_callbacks
    assert f"cut_menu:{uuid}" in main_callbacks
    assert f"undo:preview:{uuid}" in main_callbacks
    assert "🔄 Undo Changes" in main_texts

    # Editor keyboard has simplified tags and swapped Undo / Back to Main buttons
    editor_kb = get_editor_keyboard(uuid)
    editor_callbacks = [btn.callback_data for row in editor_kb.inline_keyboard for btn in row]
    editor_texts = [btn.text for row in editor_kb.inline_keyboard for btn in row]

    # Verify essential tags are present
    assert f"field:title:{uuid}" in editor_callbacks
    assert f"field:artist:{uuid}" in editor_callbacks
    assert f"field:album:{uuid}" in editor_callbacks
    assert f"field:date:{uuid}" in editor_callbacks
    assert f"field:genre:{uuid}" in editor_callbacks
    assert f"field:track_number:{uuid}" in editor_callbacks
    assert f"field:albumartist:{uuid}" in editor_callbacks
    assert f"fn_menu:{uuid}" in editor_callbacks

    # Verify extra clutter tags are NOT in the simplified primary editor
    assert f"field:disc_number:{uuid}" not in editor_callbacks
    assert f"field:composer:{uuid}" not in editor_callbacks
    assert f"field:comment:{uuid}" not in editor_callbacks
    assert f"field:copyright:{uuid}" not in editor_callbacks

    # Verify button positions: Undo Changes is above Back to Main + Finish
    undo_row = editor_kb.inline_keyboard[4]
    nav_row = editor_kb.inline_keyboard[5]
    assert len(undo_row) == 1
    assert undo_row[0].text == "🔄 Undo Changes"
    assert undo_row[0].callback_data == f"undo:editor:{uuid}"
    assert len(nav_row) == 2
    assert nav_row[0].text == "🏠 Back to Main"
    assert nav_row[0].callback_data == f"preview:{uuid}"
    assert nav_row[1].text == "✅ Finish"

    # Cover menu has 🏠 Back to Main
    cover_kb = get_cover_menu_keyboard(uuid)
    cover_callbacks = [btn.callback_data for row in cover_kb.inline_keyboard for btn in row]
    cover_texts = [btn.text for row in cover_kb.inline_keyboard for btn in row]
    assert f"preview:{uuid}" in cover_callbacks
    assert "🏠 Back to Main" in cover_texts

    # Lyrics menu has 🏠 Back to Main
    lyrics_kb = get_lyrics_menu_keyboard(uuid)
    lyrics_callbacks = [btn.callback_data for row in lyrics_kb.inline_keyboard for btn in row]
    lyrics_texts = [btn.text for row in lyrics_kb.inline_keyboard for btn in row]
    assert f"preview:{uuid}" in lyrics_callbacks
    assert "🏠 Back to Main" in lyrics_texts

    # Cut menu has 🏠 Back to Main
    cut_kb = get_cut_menu_keyboard(uuid)
    cut_callbacks = [btn.callback_data for row in cut_kb.inline_keyboard for btn in row]
    cut_texts = [btn.text for row in cut_kb.inline_keyboard for btn in row]
    assert f"preview:{uuid}" in cut_callbacks
    assert "🏠 Back to Main" in cut_texts

    # Advanced editor has 🏠 Back to Main and 🔄 Undo Changes
    adv_kb = get_advanced_editor_keyboard(uuid)
    adv_callbacks = [btn.callback_data for row in adv_kb.inline_keyboard for btn in row]
    adv_texts = [btn.text for row in adv_kb.inline_keyboard for btn in row]
    assert f"preview:{uuid}" in adv_callbacks
    assert f"edit_menu:{uuid}" in adv_callbacks
    assert "🏠 Back to Main" in adv_texts
    assert "🔄 Undo Changes" in adv_texts

    # Filename menu has 🏠 Back to Main and back to tags
    fn_kb = get_filename_menu_keyboard(uuid)
    fn_callbacks = [btn.callback_data for row in fn_kb.inline_keyboard for btn in row]
    fn_texts = [btn.text for row in fn_kb.inline_keyboard for btn in row]
    assert f"preview:{uuid}" in fn_callbacks
    assert f"edit_menu:{uuid}" in fn_callbacks
    assert "🏠 Back to Main" in fn_texts


@pytest.mark.asyncio
async def test_finish_sends_file_without_caption_or_extra_attachments(sample_mp3: Path, tmp_path: Path):
    from unittest.mock import AsyncMock, MagicMock
    from app.audio.models import AudioFormat, AudioMetadata
    from app.bot.handlers.finish_handler import callback_finish
    import shutil

    # Prepare job
    test_file = tmp_path / "finish_test.mp3"
    shutil.copy2(sample_mp3, test_file)

    mgr = JobManager(base_jobs_dir=tmp_path / "jobs", ttl_minutes=30)
    job = mgr.create_job(101, 101, "finish_test.mp3", ".mp3")
    job.format = AudioFormat.MP3
    shutil.copy2(test_file, job.working_path)
    job.working_metadata = AudioMetadata(title="Test Song", artist="Test Artist")

    callback = MagicMock()
    callback.data = f"finish:{job.uuid}"
    callback.from_user.id = 101
    callback.message = MagicMock()
    status_msg = AsyncMock()
    callback.message.reply = AsyncMock(return_value=status_msg)
    callback.answer = AsyncMock()

    state = AsyncMock()
    bot = AsyncMock()
    callback.bot = bot

    queue_mgr = MagicMock()
    async def mock_enqueue(job_id, user_id, task_func):
        await task_func()
    queue_mgr.enqueue = mock_enqueue

    metadata_mgr = MagicMock()
    metadata_mgr.write_metadata = AsyncMock(return_value=True)
    metadata_mgr.extract_cover = AsyncMock(return_value=False)

    settings = Settings(bot_token="test:token", send_cover_separately=False)
    repo = MagicMock()
    repo.increment_stat = AsyncMock()
    repo.update_job_status = AsyncMock()

    await callback_finish(
        callback=callback,
        state=state,
        job_manager=mgr,
        queue_manager=queue_mgr,
        metadata_manager=metadata_mgr,
        settings=settings,
        repository=repo,
    )

    # Verify send_audio was called with NO caption and NO parse_mode
    bot.send_audio.assert_called_once()
    call_kwargs = bot.send_audio.call_args.kwargs
    assert "caption" not in call_kwargs or call_kwargs.get("caption") is None
    assert "parse_mode" not in call_kwargs

    # Verify send_photo was NOT called
    bot.send_photo.assert_not_called()
