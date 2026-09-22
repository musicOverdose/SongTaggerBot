"""Telegram message text formatters for metadata and technical info."""

from typing import Optional
from app.audio.models import AudioMetadata, AudioTechnicalInfo


def val_or_dash(val: Optional[str]) -> str:
    if val is None or str(val).strip() == "":
        return "—"
    return str(val).strip()


def format_metadata_preview(
    filename: str,
    metadata: AudioMetadata,
    tech_info: Optional[AudioTechnicalInfo] = None,
) -> str:
    """Format the primary metadata preview message."""
    # Track formatting
    track_str = "—"
    if metadata.track_number is not None:
        track_str = f"{metadata.track_number:02d}"
        if metadata.track_total is not None:
            track_str += f" / {metadata.track_total:02d}"

    # Cover formatting
    cover_str = "—"
    if metadata.has_cover:
        if metadata.cover_dimensions:
            w, h = metadata.cover_dimensions
            cover_str = f"✅ {w}×{h}"
        else:
            cover_str = "✅ Embedded"

    # Lyrics formatting
    lyrics_str = "✅ Present" if metadata.has_lyrics else "—"

    # Audio technical line
    audio_line = ""
    if tech_info:
        parts = [tech_info.format_name]
        if tech_info.bitrate_kbps:
            parts.append(f"{tech_info.bitrate_kbps} kbps")
        if tech_info.sample_rate_hz:
            parts.append(f"{tech_info.sample_rate_hz / 1000:.1f} kHz")
        if tech_info.channel_layout:
            parts.append(tech_info.channel_layout)

        line1 = " • ".join(parts)
        line2 = f"{tech_info.duration_formatted} • {tech_info.file_size_mb} MB"
        audio_line = f"\n\nAudio\n{line1}\n{line2}"

    album_artist_line = ""
    if metadata.albumartist:
        album_artist_line = f"\n\nAlbum Artist\n{metadata.albumartist}"

    msg = (
        f"🎵 <b>Audio Metadata</b>\n\n"
        f"File\n<code>{filename}</code>\n\n"
        f"Title\n{val_or_dash(metadata.title)}\n\n"
        f"Artist\n{val_or_dash(metadata.artist)}\n\n"
        f"Album\n{val_or_dash(metadata.album)}"
        f"{album_artist_line}\n\n"
        f"Year\n{val_or_dash(metadata.date)}\n\n"
        f"Genre\n{val_or_dash(metadata.genre)}\n\n"
        f"Track\n{track_str}\n\n"
        f"Cover\n{cover_str}\n\n"
        f"Lyrics\n{lyrics_str}"
        f"{audio_line}"
    )
    return msg


def format_technical_info(
    filename: str,
    tech_info: AudioTechnicalInfo,
) -> str:
    """Format the detailed file information view."""
    cover_str = "—"
    if tech_info.has_cover:
        if tech_info.cover_dimensions:
            w, h = tech_info.cover_dimensions
            cover_str = f"{w}×{h}"
        else:
            cover_str = "Embedded"

    lyrics_str = "Present" if tech_info.has_lyrics else "Not present"
    bit_depth_str = f"{tech_info.bit_depth}-bit" if tech_info.bit_depth else "—"
    sample_rate_str = (
        f"{tech_info.sample_rate_hz / 1000:.1f} kHz"
        if tech_info.sample_rate_hz
        else "—"
    )
    bitrate_str = (
        f"{tech_info.bitrate_kbps} kbps"
        if tech_info.bitrate_kbps
        else "—"
    )

    return (
        f"📄 <b>File Information</b>\n\n"
        f"Filename\n<code>{filename}</code>\n\n"
        f"Format\n{tech_info.format_name}\n\n"
        f"Codec\n{tech_info.codec_name}\n\n"
        f"MIME Type\n{tech_info.mime_type}\n\n"
        f"Bit depth\n{bit_depth_str}\n\n"
        f"Sample rate\n{sample_rate_str}\n\n"
        f"Bitrate\n{bitrate_str}\n\n"
        f"Channels\n{tech_info.channel_layout or '—'}\n\n"
        f"Duration\n{tech_info.duration_formatted}\n\n"
        f"Size\n{tech_info.file_size_mb} MB\n\n"
        f"Tags\n{tech_info.tag_type}\n\n"
        f"Cover\n{cover_str}\n\n"
        f"Lyrics\n{lyrics_str}"
    )
