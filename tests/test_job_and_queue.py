"""Tests for JobManager and QueueManager."""

import asyncio
from pathlib import Path
import pytest

from app.services.job_manager import JobManager
from app.services.queue_manager import QueueManager


def test_job_lifecycle_and_undo(tmp_path: Path):
    mgr = JobManager(base_jobs_dir=tmp_path / "jobs", ttl_minutes=30)

    # 1. Create Job
    job = mgr.create_job(
        user_id=12345,
        chat_id=67890,
        original_filename="song.mp3",
        file_ext=".mp3",
    )
    assert job.uuid is not None
    assert job.dir_path.exists()
    assert job.working_filename == "song.mp3"

    # 2. Record changes
    job.record_change("title", "New Title")
    assert job.working_metadata.title == "New Title"
    assert len(job.change_history) == 1

    job.record_change("artist", "New Artist")
    assert job.working_metadata.artist == "New Artist"
    assert len(job.change_history) == 2

    # 3. Undo changes
    reverted_artist = job.undo_last_change()
    assert reverted_artist.field_name == "artist"
    assert job.working_metadata.artist is None

    reverted_title = job.undo_last_change()
    assert reverted_title.field_name == "title"
    assert job.working_metadata.title is None

    # Undo on empty stack returns None
    assert job.undo_last_change() is None

    # 4. Cleanup
    assert mgr.cleanup_job(job.uuid) is True
    assert not job.dir_path.exists()
    assert mgr.get_job(job.uuid) is None


@pytest.mark.asyncio
async def test_queue_manager_concurrency():
    qm = QueueManager(max_concurrent_jobs=2)
    qm.start()

    executed_order = []
    active_concurrent_counts = []
    current_concurrent = 0
    lock = asyncio.Lock()

    async def sample_task(task_id: int):
        nonlocal current_concurrent
        async with lock:
            current_concurrent += 1
            active_concurrent_counts.append(current_concurrent)

        await asyncio.sleep(0.05)
        executed_order.append(task_id)

        async with lock:
            current_concurrent -= 1

        return f"result_{task_id}"

    try:
        # Enqueue 4 tasks
        fut1, pos1, busy1 = await qm.enqueue("j1", 101, sample_task, 1)
        fut2, pos2, busy2 = await qm.enqueue("j2", 102, sample_task, 2)
        fut3, pos3, busy3 = await qm.enqueue("j3", 103, sample_task, 3)
        fut4, pos4, busy4 = await qm.enqueue("j4", 104, sample_task, 4)

        results = await asyncio.gather(fut1, fut2, fut3, fut4)
        assert results == ["result_1", "result_2", "result_3", "result_4"]
        assert len(executed_order) == 4

        # Max concurrent tasks should never exceed 2
        assert max(active_concurrent_counts) <= 2

    finally:
        await qm.stop()
