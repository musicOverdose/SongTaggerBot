"""Command-line administrative interface for MusicOverdose Bot."""

import argparse
import asyncio
from pathlib import Path
import sys

from app.config import get_settings
from app.database.connection import Database
from app.database.repository import DatabaseRepository
from app.services.job_manager import JobManager


async def cmd_channels_list(repo: DatabaseRepository):
    channels = await repo.list_channels()
    if not channels:
        print("No required channels configured.")
        return
    print("Required Channels:")
    print("-" * 60)
    for c in channels:
        status = "ENABLED" if c.is_enabled else "DISABLED"
        display = c.username or c.channel_id
        print(f"[{status:8s}] {display:25s} (ID: {c.channel_id})")
    print("-" * 60)


async def cmd_channels_add(repo: DatabaseRepository, channel_arg: str):
    channel_id = channel_arg
    username = channel_arg.lstrip("@") if channel_arg.startswith("@") else None
    success = await repo.add_channel(channel_id=channel_id, username=username)
    if success:
        print(f"Successfully added required channel: {channel_arg}")
    else:
        print(f"Failed to add channel: {channel_arg}", file=sys.stderr)
        sys.exit(1)


async def cmd_channels_remove(repo: DatabaseRepository, channel_arg: str):
    success = await repo.remove_channel(channel_arg)
    if success:
        print(f"Successfully removed channel: {channel_arg}")
    else:
        print(f"Channel not found: {channel_arg}", file=sys.stderr)
        sys.exit(1)


async def cmd_channels_enable(repo: DatabaseRepository, channel_arg: str):
    success = await repo.set_channel_enabled(channel_arg, True)
    if success:
        print(f"Enabled channel: {channel_arg}")
    else:
        print(f"Channel not found: {channel_arg}", file=sys.stderr)
        sys.exit(1)


async def cmd_channels_disable(repo: DatabaseRepository, channel_arg: str):
    success = await repo.set_channel_enabled(channel_arg, False)
    if success:
        print(f"Disabled channel: {channel_arg}")
    else:
        print(f"Channel not found: {channel_arg}", file=sys.stderr)
        sys.exit(1)


async def cmd_stats(repo: DatabaseRepository):
    stats = await repo.get_stats()
    print("=" * 45)
    print("       MusicOverdose Bot Statistics")
    print("=" * 45)
    print(f"Files Received:        {stats.files_received}")
    print(f"Files Processed:       {stats.files_processed}")
    print(f"Files Failed:          {stats.files_failed}")
    print(f"Cuts Performed:        {stats.cuts_performed}")
    print(f"Covers Updated:        {stats.covers_updated}")
    print(f"Lyrics Updated:        {stats.lyrics_updated}")
    print(f"Unique Active Users:   {stats.unique_users}")
    print(f"Total Processed:       {stats.total_processed_mb} MB")
    print("=" * 45)


def cmd_cleanup(settings):
    job_mgr = JobManager(base_jobs_dir=settings.jobs_dir, ttl_minutes=settings.job_ttl_minutes)
    count = job_mgr.cleanup_expired_jobs()
    print(f"Cleanup completed. Removed {count} expired/abandoned job directories.")


async def async_main():
    settings = get_settings()
    db = Database(settings.db_path)
    repo = DatabaseRepository(db)

    parser = argparse.ArgumentParser(
        prog="cli",
        description="MusicOverdose Bot Administrative CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # channels subparser
    channels_parser = subparsers.add_parser("channels", help="Manage required broadcast channels")
    channels_sub = channels_parser.add_subparsers(dest="action", required=True)

    channels_sub.add_parser("list", help="List all configured required channels")

    add_p = channels_sub.add_parser("add", help="Add a required channel")
    add_p.add_argument("channel", help="Channel @username or ID")

    remove_p = channels_sub.add_parser("remove", help="Remove a required channel")
    remove_p.add_argument("channel", help="Channel @username or ID")

    enable_p = channels_sub.add_parser("enable", help="Enable a required channel")
    enable_p.add_argument("channel", help="Channel @username or ID")

    disable_p = channels_sub.add_parser("disable", help="Disable a required channel")
    disable_p.add_argument("channel", help="Channel @username or ID")

    # stats parser
    subparsers.add_parser("stats", help="Show usage statistics")

    # cleanup parser
    subparsers.add_parser("cleanup", help="Trigger cleanup of expired jobs")

    # If invoked with args
    args = parser.parse_args()

    try:
        if args.command == "channels":
            if args.action == "list":
                await cmd_channels_list(repo)
            elif args.action == "add":
                await cmd_channels_add(repo, args.channel)
            elif args.action == "remove":
                await cmd_channels_remove(repo, args.channel)
            elif args.action == "enable":
                await cmd_channels_enable(repo, args.channel)
            elif args.action == "disable":
                await cmd_channels_disable(repo, args.channel)
        elif args.command == "stats":
            await cmd_stats(repo)
        elif args.command == "cleanup":
            cmd_cleanup(settings)
    finally:
        await db.close()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
