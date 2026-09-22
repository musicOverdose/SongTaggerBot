<p align="center">
  <img src="assets/logo.png" alt="OverdoseAudio Bot Logo" width="180"/>
  <br/>
  <img src="assets/banner.svg" alt="OverdoseAudio Banner" width="750"/>
</p>

# OverdoseAudio (@MusicOverdose)
### Production-Ready Telegram Audio Metadata Editor Bot

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![aiogram 3.31+](https://img.shields.io/badge/aiogram-3.31+-2BA0D8.svg)](https://docs.aiogram.dev/)
[![Docker Compose](https://img.shields.io/badge/docker-compose-2496ED.svg)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Channel](https://img.shields.io/badge/Telegram-@MusicOverdose-ff2a85.svg)](https://t.me/MusicOverdose)

Production-ready Telegram bot for inspecting and interactively editing audio file metadata, replacing or extracting album artwork, updating lyrics, trimming audio, sanitizing filenames, and managing file tags.

Designed to be deployed using **Docker Compose** directly through **Portainer** or standard Docker hosts.

---

## Key Features

- 🎵 **Format Support Without Trusting Extensions**: Detects actual media containers via Mutagen, magic byte headers, and FFprobe fallback. Supports **MP3**, **FLAC**, **M4A/MP4**, **OGG Vorbis**, **OPUS**, **WAV**, **AIFF**, and **WMA**.
- ✏️ **Interactive In-Telegram Tag Editor**: Edit Title, Artist, Album, Album Artist, Year/Date, Genre, Track Number/Total, Disc Number/Total, Composer, Comment, and Copyright without leaving Telegram.
- ⚙️ **Advanced Metadata Fields**: Manage Grouping, BPM, Publisher, Conductor, Compilation flag, ISRC code, and Sort tags (Title, Artist, Album, Album Artist).
- 🖼 **Cover Art Management**:
  - Extract embedded album artwork to inspect full resolution.
  - Upload JPG, PNG, or WebP images; automatically optimized and embedded.
  - Automatic compliant Telegram thumbnail generation ($\le 320\times 320$ pixels, $\le 200\text{ KB}$ JPEG).
  - Remove embedded cover art.
- 🎤 **Multiline Lyrics**: View formatted embedded lyrics, update with multiline text, or remove lyrics.
- ✂️ **Audio Trimming / Cutting**: Fast stream-copy trimming using FFmpeg (`-c copy`) with automatic re-encoding fallback; preserves all tags and embedded artwork.
- 📝 **Filename Sanitization & Generation**: Protects against directory traversal and control characters. Generates filenames from tags using configurable templates (e.g., `{track:02} - {title}`).
- ↩ **Undo History & Staging**: Changes are staged in memory; audio files are never repeatedly re-encoded on every field edit. Undo changes step-by-step or cancel completely without modifying the original upload.
- 🔒 **Zero Exposed HTTP Ports**: Operates entirely through Telegram Bot API long-polling. No Web UI, no Flask/FastAPI admin panel.
- 📢 **Mandatory Channel Membership (Must-Join)**: Configurable channel membership gating with instant re-verification.
- 🛠 **Container CLI Administration**: Administer channels, view stats, and trigger cleanup inside the container via `docker compose run --rm bot cli ...`.
- 🗄 **Persistent SQLite Storage**: Stores required broadcast channels, usage statistics, and active job tracking in `./data:/data`.
- 🚦 **Worker Queue**: Configurable concurrency pool (`MAX_CONCURRENT_JOBS`) with real-time queue position notifications.
- 👤 **Non-Root Container Security**: Container runs as dedicated `botuser` (UID 10001).

---

## Telegram File Size Limits

The standard Telegram Bot API imposes strict file transfer boundaries:
- **Maximum download size**: **20 MB**
- **Maximum upload size**: **50 MB**

MusicOverdose checks Telegram's reported file size **before** initiating downloads and rejects oversized files with a friendly message:

```
❌ This file is too large for the current Telegram Bot API configuration.

Maximum input size: 20 MB
```

### Local Bot API Server Support
The download architecture is fully abstracted. When deploying with a self-hosted [Telegram Local Bot API Server](https://core.telegram.org/bots/api#using-a-local-bot-api-server), simply adjust the environment variables:
```dotenv
MAX_INPUT_MB=2000
MAX_OUTPUT_MB=2000
TELEGRAM_API_BASE=http://telegram-bot-api:8081
TELEGRAM_FILE_BASE=http://telegram-bot-api:8081/file
```
No code refactoring is necessary.

---

## Supported Formats & Tag Specifications

| Format | Extension | Container / Tag Standard | Cover Art Embedding | Lyrics Field |
| :--- | :--- | :--- | :--- | :--- |
| **MP3** | `.mp3` | ID3v2.4 / ID3v2.3 (`TIT2`, `TPE1`, etc.) | `APIC` frame | `USLT` (Unsynced lyrics) |
| **FLAC** | `.flac` | Vorbis Comment | `METADATA_BLOCK_PICTURE` | `LYRICS` |
| **M4A / MP4** | `.m4a`, `.mp4` | Apple iTunes Atoms (`©nam`, `©ART`, etc.) | `covr` atom | `©lyr` atom |
| **OGG Vorbis** | `.ogg` | Vorbis Comment | `METADATA_BLOCK_PICTURE` | `LYRICS` |
| **OPUS** | `.opus` | Ogg Opus / Vorbis Comment | `METADATA_BLOCK_PICTURE` | `LYRICS` |
| **WAV** | `.wav` | RIFF with ID3 chunk | Supported | `USLT` |
| **AIFF** | `.aiff` | AIFF with ID3 chunk | `APIC` frame | `USLT` |
| **WMA** | `.wma` | ASF / Windows Media tags | ASF Picture | `WM/Lyrics` |

---

## BotFather Setup

1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to choose a name and username.
3. Copy the HTTP API token (e.g. `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_01234567`).
4. (Optional) Set bot description and profile picture using `/setdescription` and `/setuserpic`.
5. (Optional) Disable group privacy if you intend to use the bot in groups: `/setprivacy` -> `Disable`.

---

## Configuration (`.env`)

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

| Variable | Default | Description |
| :--- | :--- | :--- |
| `BOT_TOKEN` | *Required* | Telegram Bot API token from @BotFather |
| `ADMIN_IDS` | `""` | Comma-separated Telegram User IDs with admin access |
| `MAX_INPUT_MB` | `20` | Maximum input audio file size in MB |
| `MAX_OUTPUT_MB` | `50` | Maximum processed audio file size in MB |
| `MAX_CONCURRENT_JOBS` | `2` | Number of simultaneous background worker tasks |
| `JOB_TTL_MINUTES` | `30` | Inactivity lifetime for temporary processing jobs |
| `DATA_DIR` | `/data` | Path to persistent database directory |
| `TEMP_DIR` | `/tmp/audio-bot` | Path to temporary isolated job folders |
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `SHOW_TECHNICAL_INFO` | `true` | Show bitrate, sample rate, channels in preview |
| `SEND_COVER_SEPARATELY`| `false` | Send extracted album cover as a separate image on finish |
| `DEFAULT_FILENAME_FORMAT`| `{track:02} - {title}` | Default template for filename generation |
| `TELEGRAM_API_BASE` | `https://api.telegram.org` | Telegram Bot API base endpoint |
| `TELEGRAM_FILE_BASE`| `https://api.telegram.org/file` | Telegram file download endpoint |

---

## Deployment with Docker Compose

### Prerequisites
- Docker Engine 24.0+
- Docker Compose v2+

### Quick Start

1. **Clone repository**:
   ```bash
   git clone https://github.com/MusicOverdose/audio-metadata-editor-bot.git
   cd audio-metadata-editor-bot
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   nano .env
   ```

3. **Build and start the container**:
   ```bash
   docker compose build
   docker compose up -d
   ```

4. **Verify container logs**:
   ```bash
   docker compose logs -f bot
   ```

---

## Deployment in Portainer

Portainer allows deploying the bot as a Stack without exposing any ports.

1. Log into your **Portainer** dashboard.
2. Navigate to **Stacks** &rarr; **Add stack**.
3. Choose a name: `musicoverdose-bot`.
4. Select **Repository** or **Web editor**:
   - **Option A (Repository)**:
     - Repository URL: `https://github.com/MusicOverdose/audio-metadata-editor-bot.git`
     - Repository reference: `refs/heads/main`
     - Compose path: `compose.yaml`
   - **Option B (Web editor)**:
     - Paste the contents of `compose.yaml`.
5. Under **Environment variables**, define your variables:
   - `BOT_TOKEN`: `your_bot_token_here`
   - `ADMIN_IDS`: `your_telegram_user_id`
   - `MAX_INPUT_MB`: `20`
   - `MAX_OUTPUT_MB`: `50`
   - `MAX_CONCURRENT_JOBS`: `2`
6. Click **Deploy the stack**.
7. The container will build, start up in non-root mode, connect via long-polling, and persist its database in `./data`.

---

## CLI Administration

Administrative tasks can be executed inside the container without stopping the service:

```bash
# List all required broadcast channels
docker compose run --rm bot cli channels list

# Add a required channel (@username or -100... ID)
docker compose run --rm bot cli channels add @MusicOverdose

# Disable a channel temporarily
docker compose run --rm bot cli channels disable @MusicOverdose

# Re-enable a channel
docker compose run --rm bot cli channels enable @MusicOverdose

# Remove a required channel
docker compose run --rm bot cli channels remove @MusicOverdose

# View bot operational statistics
docker compose run --rm bot cli stats

# Trigger immediate cleanup of abandoned/expired job directories
docker compose run --rm bot cli cleanup
```

---

## Admin Telegram Commands

Administrators (whose user IDs are in `ADMIN_IDS`) can also manage the bot directly inside Telegram:

- `/channels` &mdash; View configured required channels and their status.
- `/addchannel @username` &mdash; Add a mandatory broadcast channel.
- `/delchannel @username` &mdash; Remove a mandatory broadcast channel.
- `/stats` &mdash; View files received, processed, cuts, and processed data volume.
- `/reloadconfig` &mdash; Reload settings from environment without restarting.

Regular users attempting to run these commands receive no response and have no access to administrative features.

---

## Local Development & Testing

### Setup Environment

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run CLI locally
./cli --help
```

### Run Test Suite

The repository includes comprehensive automated tests covering all formats, cover management, lyrics, trimming, queue concurrency, and CLI operations:

```bash
# Run all tests with verbose output
pytest -v
```

---

## File Storage & Backup Instructions

### Directory Structure
```
/home/farzad/metadataeditor/
├── data/                    # Persistent SQLite storage
│   └── bot.db               # Database file
└── /tmp/audio-bot/jobs/     # Ephemeral scratch space (auto-cleaned)
    └── <uuid>/
        ├── original.<ext>
        ├── working.<ext>
        ├── cover_original.jpg
        ├── cover_new.jpg
        └── thumbnail.jpg
```

### Backing up Database
To backup your bot configuration and statistics, backup the `./data` directory:

```bash
# Create timestamped tar archive of data
tar -czvf "backup_bot_data_$(date +%F).tar.gz" data/
```

### Restoring Database
```bash
docker compose down
tar -xzvf backup_bot_data_YYYY-MM-DD.tar.gz
docker compose up -d
```

---

## Troubleshooting

### 1. Bot doesn't respond to messages
- Check container logs: `docker compose logs -f bot`.
- Ensure `BOT_TOKEN` in `.env` is valid and has no trailing spaces.
- Verify whether the bot has network access to `https://api.telegram.org`.

### 2. "Unable to read this audio file"
- Ensure the uploaded file is not corrupted. Test locally with `ffprobe <file>`.
- Unsupported legacy codecs might require re-wrapping in standard containers (e.g. MP3, FLAC, M4A).

### 3. File rejected as oversized
- Default Telegram Bot API download limit is 20 MB.
- If using Local Bot API Server, verify `TELEGRAM_API_BASE` and `MAX_INPUT_MB` are configured.

### 4. Permission Denied on `/data`
- The container runs as non-root user `botuser` (UID 10001).
- Ensure the host directory `./data` is writable:
  ```bash
  sudo chown -R 10001:10001 ./data
  ```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
Published by **MusicOverdose** ([@MusicOverdose](https://t.me/MusicOverdose)).
