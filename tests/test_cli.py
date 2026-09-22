"""Tests for administrative CLI."""

import io
from unittest.mock import patch
import pytest

from app.cli import (
    cmd_channels_add,
    cmd_channels_disable,
    cmd_channels_enable,
    cmd_channels_list,
    cmd_channels_remove,
    cmd_cleanup,
    cmd_stats,
)
from app.config import Settings
from app.database.repository import DatabaseRepository


@pytest.mark.asyncio
async def test_cli_channel_and_stats_commands(test_repo: DatabaseRepository, tmp_path):
    # 1. Add channel via CLI
    await cmd_channels_add(test_repo, "@musicoverdose")

    # 2. List channels via CLI
    with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
        await cmd_channels_list(test_repo)
        output = mock_out.getvalue()
        assert "@musicoverdose" in output
        assert "ENABLED" in output

    # 3. Disable channel
    await cmd_channels_disable(test_repo, "@musicoverdose")
    with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
        await cmd_channels_list(test_repo)
        assert "DISABLED" in mock_out.getvalue()

    # 4. Enable channel
    await cmd_channels_enable(test_repo, "@musicoverdose")
    with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
        await cmd_channels_list(test_repo)
        assert "ENABLED" in mock_out.getvalue()

    # 5. Stats command
    await test_repo.increment_stat("files_processed", 5)
    with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
        await cmd_stats(test_repo)
        assert "Files Processed:       5" in mock_out.getvalue()

    # 6. Remove channel
    await cmd_channels_remove(test_repo, "@musicoverdose")
    with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
        await cmd_channels_list(test_repo)
        assert "No required channels configured" in mock_out.getvalue()

    # 7. Cleanup command
    settings = Settings(temp_dir=tmp_path / "temp")
    with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
        cmd_cleanup(settings)
        assert "Cleanup completed" in mock_out.getvalue()
