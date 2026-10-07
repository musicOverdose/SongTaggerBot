#!/usr/bin/env bash
set -e

# If running as root, fix permissions on mounted volumes and drop privileges to botuser
if [ "$(id -u)" = "0" ]; then
    mkdir -p /data /tmp/audio-bot
    chown -R botuser:botgroup /data /tmp/audio-bot 2>/dev/null || true
    exec gosu botuser "$@"
fi

exec "$@"
