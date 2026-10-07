"""Isolated Job Lifecycle Manager with undo history and auto-cleanup."""

import asyncio
from dataclasses import dataclass, field
import logging
from pathlib import Path
import shutil
import time
from typing import Any, Dict, List, Optional
import uuid

from app.audio.models import AudioFormat, AudioMetadata, AudioTechnicalInfo, MetadataChange

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """Represents an isolated editing session for an uploaded audio file."""
    uuid: str
    user_id: int
    chat_id: int
    original_filename: str
    working_filename: str
    file_ext: str
    format: AudioFormat = AudioFormat.UNKNOWN
    dir_path: Path = field(default_factory=Path)
    original_path: Path = field(default_factory=Path)
    working_path: Path = field(default_factory=Path)
    cover_original_path: Path = field(default_factory=Path)
    cover_new_path: Path = field(default_factory=Path)
    thumbnail_path: Path = field(default_factory=Path)
    cut_temp_path: Path = field(default_factory=Path)

    # In-memory metadata staging and undo tracking
    original_metadata: AudioMetadata = field(default_factory=AudioMetadata)
    working_metadata: AudioMetadata = field(default_factory=AudioMetadata)
    change_history: List[MetadataChange] = field(default_factory=list)
    technical_info: Optional[AudioTechnicalInfo] = None

    # Cover art state: None = unchanged, "new" = replacement ready, "remove" = remove cover
    pending_cover_action: Optional[str] = None

    # Status & timestamps
    status: str = "active"
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_activity = time.time()

    def record_change(self, field_name: str, new_value: Any) -> None:
        """Apply a metadata change to working_metadata and push to undo stack."""
        old_val = getattr(self.working_metadata, field_name, None)
        self.change_history.append(
            MetadataChange(
                field_name=field_name,
                old_value=old_val,
                new_value=new_value,
                timestamp=time.time(),
            )
        )
        setattr(self.working_metadata, field_name, new_value)
        if field_name == "lyrics":
            self.working_metadata.has_lyrics = bool(new_value and str(new_value).strip())
        self.touch()

    def strip_extra_tags(self) -> None:
        """Strip all extra tags outside core edit list and record snapshot for undo."""
        old_snapshot = self.working_metadata.clone()
        self.working_metadata.remove_extra_tags()
        self.change_history.append(
            MetadataChange(
                field_name="_extra_tags_snapshot",
                old_value=old_snapshot,
                new_value=None,
                timestamp=time.time(),
            )
        )
        self.touch()

    def undo_last_change(self) -> Optional[MetadataChange]:
        """Revert the most recent metadata change."""
        if not self.change_history:
            return None

        last_change = self.change_history.pop()
        if last_change.field_name == "_extra_tags_snapshot":
            self.working_metadata = last_change.old_value
        else:
            setattr(self.working_metadata, last_change.field_name, last_change.old_value)
            if last_change.field_name == "lyrics":
                self.working_metadata.has_lyrics = bool(
                    last_change.old_value and str(last_change.old_value).strip()
                )
        self.touch()
        return last_change


class JobLimitError(Exception):
    """Base exception for job creation limit violations."""
    pass


class MaintenanceModeError(JobLimitError):
    """Raised when job creation is blocked due to maintenance mode."""
    pass


class UserConcurrentJobLimitError(JobLimitError):
    """Raised when a user exceeds their concurrent active job limit."""
    pass


class GlobalConcurrentJobLimitError(JobLimitError):
    """Raised when the system exceeds its global concurrent job limit."""
    pass


class JobManager:
    """Manages creation, retrieval, and disk cleanup of audio editing jobs."""

    def __init__(
        self,
        base_jobs_dir: Path,
        ttl_minutes: int = 30,
        max_user_concurrent_jobs: int = 1,
        max_global_concurrent_jobs: int = 10,
    ):
        self.base_jobs_dir = base_jobs_dir
        self.ttl_seconds = ttl_minutes * 60
        self.max_user_concurrent_jobs = max_user_concurrent_jobs
        self.max_global_concurrent_jobs = max_global_concurrent_jobs
        self._maintenance_mode: bool = False
        self._jobs: Dict[str, Job] = {}
        self._user_jobs: Dict[int, str] = {}  # user_id -> latest job uuid
        self._lock = asyncio.Lock()

    def set_maintenance_mode(self, enabled: bool) -> None:
        self._maintenance_mode = enabled

    def is_maintenance_mode(self) -> bool:
        return self._maintenance_mode

    def count_user_active_jobs(self, user_id: int) -> int:
        return sum(1 for j in self._jobs.values() if j.user_id == user_id and j.status == "active")

    def get_active_jobs_count(self) -> int:
        return sum(1 for j in self._jobs.values() if j.status == "active")

    def get_active_jobs(self) -> List[Job]:
        return [j for j in self._jobs.values() if j.status == "active"]

    def create_job(
        self,
        user_id: int,
        chat_id: int,
        original_filename: str,
        file_ext: str,
        is_admin: bool = False,
        enforce_limits: bool = True,
    ) -> Job:
        if enforce_limits and not is_admin:
            if self._maintenance_mode:
                raise MaintenanceModeError("Bot is currently in maintenance mode.")
            if self.count_user_active_jobs(user_id) >= self.max_user_concurrent_jobs:
                raise UserConcurrentJobLimitError(
                    f"User {user_id} already has an active editing session."
                )
            if self.get_active_jobs_count() >= self.max_global_concurrent_jobs:
                raise GlobalConcurrentJobLimitError(
                    "System concurrent job limit reached. Please try again shortly."
                )

        job_uuid = str(uuid.uuid4())
        job_dir = self.base_jobs_dir / job_uuid
        job_dir.mkdir(parents=True, exist_ok=True)

        norm_ext = file_ext if file_ext.startswith(".") else f".{file_ext}"

        job = Job(
            uuid=job_uuid,
            user_id=user_id,
            chat_id=chat_id,
            original_filename=original_filename,
            working_filename=original_filename,
            file_ext=norm_ext,
            dir_path=job_dir,
            original_path=job_dir / f"original{norm_ext}",
            working_path=job_dir / f"working{norm_ext}",
            cover_original_path=job_dir / "cover_original.jpg",
            cover_new_path=job_dir / "cover_new.jpg",
            thumbnail_path=job_dir / "thumbnail.jpg",
            cut_temp_path=job_dir / f"cut_temp{norm_ext}",
        )

        self._jobs[job_uuid] = job
        self._user_jobs[user_id] = job_uuid
        logger.info(f"Created job {job_uuid} for user {user_id} at {job_dir}")
        return job

    def get_job(self, job_uuid: str) -> Optional[Job]:
        job = self._jobs.get(job_uuid)
        if job:
            job.touch()
        return job

    def get_user_active_job(self, user_id: int) -> Optional[Job]:
        job_uuid = self._user_jobs.get(user_id)
        if job_uuid:
            return self.get_job(job_uuid)
        return None

    def cleanup_job(self, job_uuid: str) -> bool:
        """Clean up all job files and remove from memory."""
        job = self._jobs.pop(job_uuid, None)
        if not job:
            # Check if directory exists and remove it anyway
            dir_path = self.base_jobs_dir / job_uuid
            if dir_path.exists():
                shutil.rmtree(dir_path, ignore_errors=True)
            return False

        if self._user_jobs.get(job.user_id) == job_uuid:
            del self._user_jobs[job.user_id]

        if job.dir_path.exists():
            shutil.rmtree(job.dir_path, ignore_errors=True)
            logger.info(f"Cleaned up job directory {job.dir_path}")

        return True

    def cleanup_expired_jobs(self) -> int:
        """Periodic garbage collection for abandoned jobs."""
        now = time.time()
        expired_uuids = [
            j_uuid for j_uuid, job in self._jobs.items()
            if now - job.last_activity > self.ttl_seconds
        ]

        cleaned_count = 0
        for j_uuid in expired_uuids:
            logger.info(f"Cleaning expired job {j_uuid}")
            if self.cleanup_job(j_uuid):
                cleaned_count += 1

        # Also sweep any rogue directories in base_jobs_dir older than TTL
        try:
            if self.base_jobs_dir.exists():
                for p in self.base_jobs_dir.iterdir():
                    if p.is_dir() and p.name not in self._jobs:
                        try:
                            mtime = p.stat().st_mtime
                            if now - mtime > self.ttl_seconds:
                                shutil.rmtree(p, ignore_errors=True)
                                cleaned_count += 1
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"Error scanning base jobs dir for expired jobs: {e}")

        return cleaned_count

    def cleanup_orphaned_job_dirs(self) -> int:
        """Removes all job directories on disk that are not tracked in active memory."""
        cleaned = 0
        if not self.base_jobs_dir.exists():
            return 0
        try:
            for p in self.base_jobs_dir.iterdir():
                if p.is_dir() and p.name not in self._jobs:
                    try:
                        shutil.rmtree(p, ignore_errors=True)
                        cleaned += 1
                        logger.info(f"Cleaned up orphaned job directory: {p}")
                    except Exception as e:
                        logger.warning(f"Failed to remove orphaned directory {p}: {e}")
        except Exception as e:
            logger.warning(f"Error scanning for orphaned job directories: {e}")
        return cleaned

    def get_temp_disk_usage_mb(self) -> float:
        """Calculates total disk usage in megabytes across temporary job directories."""
        if not self.base_jobs_dir.exists():
            return 0.0
        total_bytes = 0
        try:
            for p in self.base_jobs_dir.rglob("*"):
                if p.is_file():
                    try:
                        total_bytes += p.stat().st_size
                    except OSError:
                        pass
        except Exception as e:
            logger.warning(f"Error calculating disk usage: {e}")
        return round(total_bytes / (1024 * 1024), 2)

