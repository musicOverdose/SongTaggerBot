"""FFmpeg audio cutter and trimmer with stream-copy and re-encode fallback."""

import asyncio
import logging
from pathlib import Path
import re
import subprocess
from typing import Optional, Tuple

from app.audio.format_detector import FormatDetector
from app.audio.models import AudioFormat

logger = logging.getLogger(__name__)


class AudioCutter:
    """Handles audio trimming using FFmpeg."""

    @staticmethod
    def parse_time_component(time_str: str) -> Optional[float]:
        """
        Parse time string into seconds.
        Supports:
        - "90" -> 90.0
        - "01:30" -> 90.0
        - "00:01:30.500" -> 90.5
        """
        time_str = time_str.strip().lower()
        if not time_str:
            return None

        # Format: HH:MM:SS or MM:SS or SS
        parts = time_str.split(":")
        try:
            if len(parts) == 1:
                return float(parts[0])
            elif len(parts) == 2:
                minutes = float(parts[0])
                seconds = float(parts[1])
                return minutes * 60 + seconds
            elif len(parts) == 3:
                hours = float(parts[0])
                minutes = float(parts[1])
                seconds = float(parts[2])
                return hours * 3600 + minutes * 60 + seconds
        except ValueError:
            return None
        return None

    @classmethod
    def parse_time_range(cls, input_text: str) -> Optional[Tuple[float, float]]:
        """
        Parse user-specified range into (start_seconds, end_seconds).
        Accepts:
        - "00:10 - 03:45"
        - "00:00:10 - 00:03:45"
        - "start 00:10 end 03:45"
        - "10 - 90"
        - "10:30 to 12:00"
        """
        text = input_text.strip()

        # Check for 'start X end Y'
        match = re.search(r"start\s+([\d:.]+)\s+end\s+([\d:.]+)", text, re.IGNORECASE)
        if match:
            s = cls.parse_time_component(match.group(1))
            e = cls.parse_time_component(match.group(2))
            if s is not None and e is not None and e > s:
                return s, e

        # Check for separators like '-' or 'to'
        for sep in ("-", "to", "—"):
            if sep in text:
                parts = text.split(sep, 1)
                s = cls.parse_time_component(parts[0])
                e = cls.parse_time_component(parts[1])
                if s is not None and e is not None and e > s:
                    return s, e

        return None

    @staticmethod
    def format_seconds(seconds: float) -> str:
        s_int = int(seconds)
        hours = s_int // 3600
        minutes = (s_int % 3600) // 60
        secs = s_int % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @classmethod
    def cut_audio_sync(
        cls,
        input_path: Path,
        output_path: Path,
        start_seconds: float,
        end_seconds: float,
    ) -> bool:
        """
        Trims audio from start_seconds to end_seconds.
        Tries stream-copy first; if it fails, falls back to re-encoding.
        """
        duration = end_seconds - start_seconds
        if duration <= 0:
            logger.error(f"Invalid duration for trimming: start={start_seconds}, end={end_seconds}")
            return False

        # Attempt 1: Fast stream copy
        copy_cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_seconds),
            "-to", str(end_seconds),
            "-i", str(input_path),
            "-c", "copy",
            "-map_metadata", "0",
            str(output_path),
        ]
        try:
            res = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=30)
            if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1024:
                logger.info(f"Stream-copy cut successful for {input_path}")
                return True
        except Exception as e:
            logger.warning(f"Stream copy trimming failed or timed out: {e}")

        # Attempt 2: Re-encode fallback based on audio format
        audio_fmt, _, _ = FormatDetector.detect_format(input_path)
        codec_args = []
        if audio_fmt == AudioFormat.MP3:
            codec_args = ["-c:a", "libmp3lame", "-q:a", "2"]
        elif audio_fmt == AudioFormat.FLAC:
            codec_args = ["-c:a", "flac"]
        elif audio_fmt in (AudioFormat.M4A, AudioFormat.MP4):
            codec_args = ["-c:a", "aac", "-b:a", "256k"]
        elif audio_fmt == AudioFormat.OGG:
            codec_args = ["-c:a", "libvorbis", "-q:a", "6"]
        elif audio_fmt == AudioFormat.OPUS:
            codec_args = ["-c:a", "libopus", "-b:a", "160k"]
        elif audio_fmt == AudioFormat.WAV:
            codec_args = ["-c:a", "pcm_s16le"]
        else:
            codec_args = ["-c:a", "copy"]

        reencode_cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_seconds),
            "-to", str(end_seconds),
            "-i", str(input_path),
            *codec_args,
            "-map_metadata", "0",
            str(output_path),
        ]

        try:
            res = subprocess.run(reencode_cmd, capture_output=True, text=True, timeout=60)
            if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1024:
                logger.info(f"Re-encode cut successful for {input_path}")
                return True
            else:
                logger.error(f"FFmpeg re-encode failed: {res.stderr}")
                return False
        except Exception as e:
            logger.error(f"FFmpeg cut invocation exception: {e}")
            return False

    @classmethod
    async def cut_audio(
        cls,
        input_path: Path,
        output_path: Path,
        start_seconds: float,
        end_seconds: float,
    ) -> bool:
        return await asyncio.to_thread(
            cls.cut_audio_sync, input_path, output_path, start_seconds, end_seconds
        )
