"""SQLite database connection and schema initialization."""

import logging
from pathlib import Path
import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS required_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT UNIQUE NOT NULL,
    username TEXT,
    title TEXT,
    invite_link TEXT,
    is_enabled BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bot_stats (
    key TEXT PRIMARY KEY,
    value INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS active_users (
    user_id INTEGER PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS active_jobs (
    uuid TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class Database:
    """Manages async SQLite connections and migrations."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> aiosqlite.Connection:
        if self._connection is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = await aiosqlite.connect(str(self.db_path))
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA journal_mode=WAL;")
            await self._connection.execute("PRAGMA synchronous=NORMAL;")
            await self.init_schema()
        return self._connection

    async def init_schema(self) -> None:
        if self._connection:
            await self._connection.executescript(SCHEMA_SQL)
            await self._connection.commit()
            logger.info("Database schema initialized successfully.")

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None
