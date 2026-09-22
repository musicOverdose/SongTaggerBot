"""Audio format detection using magic bytes, Mutagen, and FFprobe fallback."""

import json
import logging
from pathlib import Path
import subprocess
from typing import Optional, Tuple

import mutagen
from app.audio.models import AudioFormat

logger = logging.getLogger(__name__)

# Map format to standard file extension and MIME
FORMAT_INFO = {
    AudioFormat.MP3: {"ext": ".mp3", "mime": "audio/mpeg"},
    AudioFormat.FLAC: {"ext": ".flac", "mime": "audio/flac"},
    AudioFormat.M4A: {"ext": ".m4a", "mime": "audio/mp4"},
    AudioFormat.MP4: {"ext": ".mp4", "mime": "audio/mp4"},
    AudioFormat.OGG: {"ext": ".ogg", "mime": "audio/ogg"},
    AudioFormat.OPUS: {"ext": ".opus", "mime": "audio/opus"},
    AudioFormat.WAV: {"ext": ".wav", "mime": "audio/wav"},
    AudioFormat.AIFF: {"ext": ".aiff", "mime": "audio/aiff"},
    AudioFormat.WMA: {"ext": ".wma", "mime": "audio/x-ms-wma"},
}


class FormatDetector:
    """Detects actual audio format regardless of file extension."""

    @staticmethod
    def detect_by_magic_bytes(header: bytes) -> Optional[AudioFormat]:
        if len(header) < 12:
            return None

        # FLAC: fLaC
        if header.startswith(b"fLaC"):
            return AudioFormat.FLAC

        # OGG / OPUS: OggS
        if header.startswith(b"OggS"):
            # Check for OpusHead or vorbis later in stream
            if b"OpusHead" in header[:64]:
                return AudioFormat.OPUS
            return AudioFormat.OGG

        # MP3 ID3 header: ID3
        if header.startswith(b"ID3"):
            return AudioFormat.MP3

        # MP3 sync frame (no ID3 tag)
        if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
            return AudioFormat.MP3

        # WAV: RIFF....WAVE
        if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
            return AudioFormat.WAV

        # AIFF: FORM....AIFF
        if header.startswith(b"FORM") and (header[8:12] == b"AIFF" or header[8:12] == b"AIFC"):
            return AudioFormat.AIFF

        # MP4/M4A: ....ftyp
        if header[4:8] == b"ftyp":
            brand = header[8:12]
            if brand in (b"M4A ", b"M4B ", b"M4P "):
                return AudioFormat.M4A
            return AudioFormat.MP4

        # ASF / WMA GUID: 30 26 B2 75 8E 66 CF 11
        asf_guid = bytes([0x30, 0x26, 0xB2, 0x75, 0x8E, 0x66, 0xCF, 0x11])
        if header.startswith(asf_guid):
            return AudioFormat.WMA

        return None

    @classmethod
    def detect_format(cls, file_path: Path) -> Tuple[AudioFormat, str, str]:
        """
        Detect the real audio format.
        Returns (AudioFormat, file_extension, mime_type).
        """
        # 1. Read first 128 bytes for magic inspection
        try:
            with open(file_path, "rb") as f:
                header = f.read(128)
            magic_fmt = cls.detect_by_magic_bytes(header)
            if magic_fmt is not None:
                info = FORMAT_INFO[magic_fmt]
                return magic_fmt, info["ext"], info["mime"]
        except Exception as e:
            logger.debug(f"Magic bytes check failed for {file_path}: {e}")

        # 2. Mutagen probing
        try:
            probe = mutagen.File(file_path)
            if probe is not None:
                class_name = type(probe).__name__.lower()
                if "mp3" in class_name or "id3" in class_name:
                    return AudioFormat.MP3, ".mp3", "audio/mpeg"
                if "flac" in class_name:
                    return AudioFormat.FLAC, ".flac", "audio/flac"
                if "mp4" in class_name or "m4a" in class_name:
                    return AudioFormat.M4A, ".m4a", "audio/mp4"
                if "oggopus" in class_name:
                    return AudioFormat.OPUS, ".opus", "audio/opus"
                if "ogg" in class_name:
                    return AudioFormat.OGG, ".ogg", "audio/ogg"
                if "wave" in class_name or "wav" in class_name:
                    return AudioFormat.WAV, ".wav", "audio/wav"
                if "aiff" in class_name:
                    return AudioFormat.AIFF, ".aiff", "audio/aiff"
                if "asf" in class_name:
                    return AudioFormat.WMA, ".wma", "audio/x-ms-wma"
        except Exception as e:
            logger.debug(f"Mutagen probe failed for {file_path}: {e}")

        # 3. FFprobe fallback
        ffprobe_fmt = cls._probe_with_ffprobe(file_path)
        if ffprobe_fmt is not None:
            info = FORMAT_INFO.get(ffprobe_fmt, {"ext": file_path.suffix.lower(), "mime": "application/octet-stream"})
            return ffprobe_fmt, info["ext"], info["mime"]

        # If extension is known as fallback
        ext = file_path.suffix.lower()
        for fmt, info in FORMAT_INFO.items():
            if info["ext"] == ext:
                return fmt, info["ext"], info["mime"]

        return AudioFormat.UNKNOWN, file_path.suffix.lower(), "application/octet-stream"

    @staticmethod
    def _probe_with_ffprobe(file_path: Path) -> Optional[AudioFormat]:
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)
            format_names = data.get("format", {}).get("format_name", "").lower().split(",")
            streams = data.get("streams", [])
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
            codec = audio_stream.get("codec_name", "").lower() if audio_stream else ""

            if codec == "mp3" or "mp3" in format_names:
                return AudioFormat.MP3
            if codec == "flac" or "flac" in format_names:
                return AudioFormat.FLAC
            if codec in ("aac", "alac") or "mov,mp4,m4a,3gp,3g2,mj2" in format_names:
                return AudioFormat.M4A
            if codec == "opus":
                return AudioFormat.OPUS
            if codec == "vorbis" or "ogg" in format_names:
                return AudioFormat.OGG
            if codec in ("pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le") and "wav" in format_names:
                return AudioFormat.WAV
            if "aiff" in format_names:
                return AudioFormat.AIFF
            if codec in ("wmav1", "wmav2", "wmapro") or "asf" in format_names:
                return AudioFormat.WMA
        except Exception as e:
            logger.debug(f"ffprobe invocation failed: {e}")
        return None
