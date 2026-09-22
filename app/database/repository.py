"""Database repository for channels, stats, and jobs."""

from datetime import datetime, timezone
import logging
from typing import Optional, List
import aiosqlite

from app.database.connection import Database
from app.database.models import BotStatistic, JobRecord, RequiredChannel

logger = logging.getLogger(__name__)


class DatabaseRepository:
    """Async repository providing high-level CRUD operations for the bot."""

    def __init__(self, db: Database):
        self.db = db

    async def _get_conn(self) -> aiosqlite.Connection:
        return await self.db.connect()

    # --- Required Channels CRUD ---

    async def add_channel(
        self,
        channel_id: str,
        username: Optional[str] = None,
        title: Optional[str] = None,
        invite_link: Optional[str] = None,
    ) -> bool:
        conn = await self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            await conn.execute(
                """
                INSERT INTO required_channels (channel_id, username, title, invite_link, is_enabled, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    username = excluded.username,
                    title = excluded.title,
                    invite_link = excluded.invite_link,
                    is_enabled = 1;
                """,
                (channel_id, username, title, invite_link, now),
            )
            await conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding channel {channel_id}: {e}")
            return False

    async def remove_channel(self, channel_id: str) -> bool:
        conn = await self._get_conn()
        try:
            cursor = await conn.execute(
                "DELETE FROM required_channels WHERE channel_id = ? OR username = ?;",
                (channel_id, channel_id.lstrip("@")),
            )
            await conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error removing channel {channel_id}: {e}")
            return False

    async def set_channel_enabled(self, channel_id: str, is_enabled: bool) -> bool:
        conn = await self._get_conn()
        try:
            cursor = await conn.execute(
                "UPDATE required_channels SET is_enabled = ? WHERE channel_id = ? OR username = ?;",
                (1 if is_enabled else 0, channel_id, channel_id.lstrip("@")),
            )
            await conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error setting channel {channel_id} status: {e}")
            return False

    async def list_channels(self, enabled_only: bool = False) -> List[RequiredChannel]:
        conn = await self._get_conn()
        query = "SELECT id, channel_id, username, title, invite_link, is_enabled, created_at FROM required_channels"
        if enabled_only:
            query += " WHERE is_enabled = 1"
        query += " ORDER BY id ASC;"

        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [
                RequiredChannel(
                    id=row["id"],
                    channel_id=row["channel_id"],
                    username=row["username"],
                    title=row["title"],
                    invite_link=row["invite_link"],
                    is_enabled=bool(row["is_enabled"]),
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    # --- Statistics ---

    async def increment_stat(self, key: str, amount: int = 1) -> None:
        conn = await self._get_conn()
        try:
            await conn.execute(
                """
                INSERT INTO bot_stats (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = value + excluded.value;
                """,
                (key, amount),
            )
            await conn.commit()
        except Exception as e:
            logger.error(f"Error incrementing stat {key}: {e}")

    async def record_user_activity(self, user_id: int) -> None:
        conn = await self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            await conn.execute(
                """
                INSERT INTO active_users (user_id, first_seen, last_seen) VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET last_seen = excluded.last_seen;
                """,
                (user_id, now, now),
            )
            await conn.commit()
        except Exception as e:
            logger.error(f"Error recording user {user_id}: {e}")

    async def get_stats(self) -> BotStatistic:
        conn = await self._get_conn()
        stats_map = {}
        async with conn.execute("SELECT key, value FROM bot_stats;") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                stats_map[row["key"]] = row["value"]

        # Count active users
        user_count = 0
        async with conn.execute("SELECT COUNT(*) as cnt FROM active_users;") as cursor:
            row = await cursor.fetchone()
            if row:
                user_count = row["cnt"]

        return BotStatistic(
            files_received=stats_map.get("files_received", 0),
            files_processed=stats_map.get("files_processed", 0),
            files_failed=stats_map.get("files_failed", 0),
            cuts_performed=stats_map.get("cuts_performed", 0),
            covers_updated=stats_map.get("covers_updated", 0),
            lyrics_updated=stats_map.get("lyrics_updated", 0),
            unique_users=user_count,
            total_processed_bytes=stats_map.get("total_processed_bytes", 0),
        )

    # --- Job Tracking ---

    async def register_job(self, uuid_str: str, user_id: int, chat_id: int, filename: str, file_size: int) -> None:
        conn = await self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            await conn.execute(
                """
                INSERT INTO active_jobs (uuid, user_id, chat_id, filename, file_size, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?);
                """,
                (uuid_str, user_id, chat_id, filename, file_size, now, now),
            )
            await conn.commit()
        except Exception as e:
            logger.error(f"Error registering job {uuid_str}: {e}")

    async def update_job_status(self, uuid_str: str, status: str) -> None:
        conn = await self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        try:
            await conn.execute(
                "UPDATE active_jobs SET status = ?, updated_at = ? WHERE uuid = ?;",
                (status, now, uuid_str),
            )
            await conn.commit()
        except Exception as e:
            logger.error(f"Error updating job {uuid_str}: {e}")

    async def delete_job_record(self, uuid_str: str) -> None:
        conn = await self._get_conn()
        try:
            await conn.execute("DELETE FROM active_jobs WHERE uuid = ?;", (uuid_str,))
            await conn.commit()
        except Exception as e:
            logger.error(f"Error deleting job {uuid_str}: {e}")
