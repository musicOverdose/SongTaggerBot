"""Technical audio probing using Mutagen and FFprobe."""

import asyncio
import json
import logging
from pathlib import Path
import subprocess
from typing import Optional

import mutagen
from app.audio.format_detector import FormatDetector
from app.audio.models import AudioFormat, AudioTechnicalInfo

logger = logging.getLogger(__name__)


class AudioProber:
    """Probes technical information from audio files."""

    @classmethod
    async def probe(cls, file_path: Path, timeout: Optional[int] = None) -> Optional[AudioTechnicalInfo]:
        return await asyncio.to_thread(cls.probe_sync, file_path, timeout)

    @classmethod
    def probe_sync(cls, file_path: Path, timeout: Optional[int] = None) -> Optional[AudioTechnicalInfo]:
        from app.config import get_settings
        if timeout is None:
            timeout = get_settings().ffprobe_timeout_seconds
        if not file_path.exists():
            return None

        file_size = file_path.stat().st_size
        audio_fmt, ext, mime = FormatDetector.detect_format(file_path)

        duration: float = 0.0
        bitrate_kbps: Optional[int] = None
        bitrate_mode: Optional[str] = None
        sample_rate: Optional[int] = None
        channels: Optional[int] = None
        channel_layout: Optional[str] = None
        bit_depth: Optional[int] = None
        codec: str = audio_fmt.value
        tag_type: str = "Unknown"
        has_cover: bool = False
        cover_dim: Optional[tuple[int, int]] = None
        has_lyrics: bool = False

        # 1. Mutagen extraction
        try:
            m = mutagen.File(file_path)
            if m is not None:
                tag_type = type(m).__name__
                if hasattr(m, "info") and m.info is not None:
                    info = m.info
                    duration = getattr(info, "length", 0.0)
                    bitrate = getattr(info, "bitrate", None)
                    if bitrate:
                        bitrate_kbps = int(bitrate // 1000)
                    sample_rate = getattr(info, "sample_rate", None)
                    channels = getattr(info, "channels", None)
                    bit_depth = getattr(info, "bits_per_sample", None)

                # Tag specific detection
                if hasattr(m, "tags") and m.tags:
                    tag_keys_lower = [str(k).lower() for k in m.tags.keys()]
                    if any("uslt" in k or "lyr" in k for k in tag_keys_lower):
                        has_lyrics = True

                # Check pictures
                if hasattr(m, "pictures") and m.pictures:
                    has_cover = True
                elif hasattr(m, "tags") and m.tags:
                    for k in m.tags.keys():
                        if str(k).startswith("APIC") or k in ("covr", "metadata_block_picture", "WM/Picture"):
                            has_cover = True
                            break
        except Exception as e:
            logger.debug(f"Mutagen probe error for {file_path}: {e}")

        # 2. FFprobe to fill missing gaps
        ff_data = cls._run_ffprobe(file_path, timeout=timeout)
        if ff_data:
            format_dict = ff_data.get("format", {})
            streams = ff_data.get("streams", [])
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

            if duration <= 0:
                try:
                    duration = float(format_dict.get("duration", 0.0))
                except ValueError:
                    duration = float(audio_stream.get("duration", 0.0))

            if bitrate_kbps is None:
                try:
                    br = int(format_dict.get("bit_rate", 0))
                    if br > 0:
                        bitrate_kbps = int(br // 1000)
                except ValueError:
                    pass

            if sample_rate is None:
                try:
                    sample_rate = int(audio_stream.get("sample_rate", 0))
                except ValueError:
                    pass

            if channels is None:
                channels = audio_stream.get("channels")

            if channel_layout is None:
                channel_layout = audio_stream.get("channel_layout")

            if bit_depth is None:
                bits = audio_stream.get("bits_per_raw_sample") or audio_stream.get("bits_per_sample")
                if bits:
                    try:
                        bit_depth = int(bits)
                    except ValueError:
                        pass

            codec_raw = audio_stream.get("codec_name")
            if codec_raw:
                codec = codec_raw.upper()

        if channels:
            if channels == 1:
                channel_layout = "Mono"
            elif channels == 2:
                channel_layout = "Stereo"
            elif channels == 6:
                channel_layout = "5.1 Surround"

        # Sanity validation on duration: clamp negative/NaN to 0
        if duration < 0 or duration != duration:
            duration = 0.0

        # Friendly tag type name
        if "ID3" in tag_type or audio_fmt in (AudioFormat.MP3, AudioFormat.AIFF, AudioFormat.WAV):
            tag_type = "ID3v2"
        elif "FLAC" in tag_type or "Vorbis" in tag_type or audio_fmt in (AudioFormat.FLAC, AudioFormat.OGG, AudioFormat.OPUS):
            tag_type = "Vorbis Comment"
        elif "MP4" in tag_type or audio_fmt in (AudioFormat.M4A, AudioFormat.MP4):
            tag_type = "iTunes MP4"
        elif "ASF" in tag_type or audio_fmt == AudioFormat.WMA:
            tag_type = "Windows Media ASF"

        return AudioTechnicalInfo(
            format_name=audio_fmt.value,
            codec_name=codec,
            mime_type=mime,
            file_size_bytes=file_size,
            duration_seconds=duration,
            bitrate_kbps=bitrate_kbps,
            bitrate_mode=bitrate_mode,
            sample_rate_hz=sample_rate,
            channels=channels,
            channel_layout=channel_layout,
            bit_depth=bit_depth,
            tag_type=tag_type,
            has_cover=has_cover,
            cover_dimensions=cover_dim,
            has_lyrics=has_lyrics,
        )

    @staticmethod
    def _run_ffprobe(file_path: Path, timeout: int = 15) -> Optional[dict]:
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(file_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0:
                return json.loads(res.stdout)
        except Exception as e:
            logger.debug(f"ffprobe execution failed for {file_path}: {e}")
        return None

