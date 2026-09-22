"""Application configuration using Pydantic Settings."""

import os
from pathlib import Path
from typing import Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_data_dir() -> Path:
    target = Path("/data")
    try:
        if target.exists() and os.access(target, os.W_OK):
            return target
    except Exception:
        pass
    return Path("./data").resolve()


def get_default_temp_dir() -> Path:
    target = Path("/tmp/audio-bot")
    try:
        target.mkdir(parents=True, exist_ok=True)
        if os.access(target, os.W_OK):
            return target
    except Exception:
        pass
    return Path("./temp/audio-bot").resolve()


class Settings(BaseSettings):
    """Central configuration for MusicOverdose audio metadata editor bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot Token
    bot_token: str = Field(default="", description="Telegram Bot API Token")

    # Administrators (list of integer Telegram IDs)
    admin_ids: list[int] = Field(default_factory=list, description="Admin Telegram IDs")

    # Size limits in megabytes
    max_input_mb: int = Field(default=20, ge=1, le=2000, description="Max input file size in MB")
    max_output_mb: int = Field(default=50, ge=1, le=2000, description="Max output file size in MB")

    # Concurrency and Job TTL
    max_concurrent_jobs: int = Field(default=2, ge=1, le=64, description="Max concurrent processing workers")
    job_ttl_minutes: int = Field(default=30, ge=1, le=1440, description="TTL in minutes for temporary jobs")

    # Directory Paths
    data_dir: Path = Field(default_factory=get_default_data_dir, description="Path to persistent data directory")
    temp_dir: Path = Field(default_factory=get_default_temp_dir, description="Path to temporary processing directory")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # UX Features
    show_technical_info: bool = Field(default=True, description="Whether to include technical details")
    send_cover_separately: bool = Field(default=False, description="Send extracted cover as a separate image on finish")
    default_filename_format: str = Field(default="{track:02} - {title}", description="Default naming template")

    # Telegram API URLs (overridable for Local Bot API Server)
    telegram_api_base: str = Field(default="https://api.telegram.org", description="Base URL for Bot API")
    telegram_file_base: str = Field(default="https://api.telegram.org/file", description="Base URL for file downloads")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Union[str, list[int], int, None]) -> list[int]:
        if v is None or v == "":
            return []
        if isinstance(v, int):
            return [v]
        if isinstance(v, list):
            return [int(item) for item in v if str(item).strip()]
        if isinstance(v, str):
            res = []
            for item in v.split(","):
                item_str = item.strip()
                if item_str.isdigit() or (item_str.startswith("-") and item_str[1:].isdigit()):
                    res.append(int(item_str))
            return res
        return []

    @property
    def max_input_bytes(self) -> int:
        return self.max_input_mb * 1024 * 1024

    @property
    def max_output_bytes(self) -> int:
        return self.max_output_mb * 1024 * 1024

    @property
    def db_path(self) -> Path:
        return self.data_dir / "bot.db"

    @property
    def jobs_dir(self) -> Path:
        return self.temp_dir / "jobs"

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


# Global settings singleton helper
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    global _settings
    _settings = Settings()
    return _settings
