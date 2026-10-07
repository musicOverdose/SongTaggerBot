"""ASF / WMA tag adapter."""

import io
import logging
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

import mutagen
from mutagen.asf import ASF

from app.audio.models import AudioFormat, AudioMetadata
from app.audio.tags.base import BaseTagAdapter

logger = logging.getLogger(__name__)


class ASFAdapter(BaseTagAdapter):
    """Adapter for ASF / Windows Media Audio (WMA) files."""

    def can_handle(self, audio_format: AudioFormat) -> bool:
        return audio_format == AudioFormat.WMA

    def _get_asf(self, file_path: Path) -> Optional[ASF]:
        try:
            return ASF(file_path)
        except Exception as e:
            logger.warning(f"Error loading ASF/WMA file {file_path}: {e}")
            return None

    def read_metadata(self, file_path: Path) -> AudioMetadata:
        meta = AudioMetadata()
        audio = self._get_asf(file_path)
        if audio is None:
            return meta

        tags = audio.tags or {}

        def get_asf_str(key: str) -> Optional[str]:
            if key in tags and tags[key]:
                val = tags[key][0]
                return str(val).strip() or None
            return None

        meta.title = get_asf_str("Title")
        meta.artist = get_asf_str("Author")
        meta.album = get_asf_str("WM/AlbumTitle")
        meta.albumartist = get_asf_str("WM/AlbumArtist")
        meta.date = get_asf_str("WM/Year")
        meta.genre = get_asf_str("WM/Genre")
        meta.composer = get_asf_str("WM/Composer")
        meta.comment = get_asf_str("Description")
        meta.copyright = get_asf_str("Copyright")
        meta.publisher = get_asf_str("WM/Publisher")
        meta.conductor = get_asf_str("WM/Conductor")

        trck_str = get_asf_str("WM/TrackNumber")
        if trck_str:
            try:
                meta.track_number = int(trck_str)
            except ValueError:
                pass

        disc_str = get_asf_str("WM/PartOfSet")
        if disc_str:
            try:
                meta.disc_number = int(disc_str)
            except ValueError:
                pass

        # Lyrics
        lyrics = get_asf_str("WM/Lyrics")
        if lyrics:
            meta.lyrics = lyrics
            meta.has_lyrics = True

        # Cover
        if "WM/Picture" in tags and tags["WM/Picture"]:
            pic = tags["WM/Picture"][0]
            if hasattr(pic, "data") and pic.data:
                meta.has_cover = True
                meta.cover_size_bytes = len(pic.data)
                try:
                    with Image.open(io.BytesIO(pic.data)) as img:
                        meta.cover_dimensions = img.size
                        meta.cover_mime = Image.MIME.get(img.format, "image/jpeg")
                except Exception:
                    pass

        return meta

    def write_metadata(self, file_path: Path, metadata: AudioMetadata) -> None:
        audio = self._get_asf(file_path)
        if audio is None:
            return

        def set_val(key: str, val: Optional[str]):
            if val is not None and val != "":
                audio[key] = [val]
            elif key in audio:
                del audio[key]

        set_val("Title", metadata.title)
        set_val("Author", metadata.artist)
        set_val("WM/AlbumTitle", metadata.album)
        set_val("WM/AlbumArtist", metadata.albumartist)
        set_val("WM/Year", metadata.date)
        set_val("WM/Genre", metadata.genre)
        set_val("WM/Composer", metadata.composer)
        set_val("Description", metadata.comment)
        set_val("Copyright", metadata.copyright)
        set_val("WM/Publisher", metadata.publisher)
        set_val("WM/Conductor", metadata.conductor)

        if metadata.track_number is not None:
            audio["WM/TrackNumber"] = [str(metadata.track_number)]
        elif "WM/TrackNumber" in audio:
            del audio["WM/TrackNumber"]

        if metadata.disc_number is not None:
            audio["WM/PartOfSet"] = [str(metadata.disc_number)]
        elif "WM/PartOfSet" in audio:
            del audio["WM/PartOfSet"]

        if metadata.lyrics is not None and metadata.lyrics.strip() != "":
            audio["WM/Lyrics"] = [metadata.lyrics]
        elif metadata.lyrics == "" and "WM/Lyrics" in audio:
            del audio["WM/Lyrics"]

        if metadata.strip_extra:
            allowed_asf = {
                "Title", "Author", "WM/AlbumTitle", "WM/AlbumArtist",
                "WM/Year", "WM/Genre", "WM/TrackNumber", "Description",
                "WM/Lyrics", "WM/Picture",
            }
            for k in list(audio.keys()):
                if k not in allowed_asf:
                    del audio[k]

        audio.save()

    def extract_cover(self, file_path: Path, target_path: Path) -> Optional[Tuple[int, int]]:
        audio = self._get_asf(file_path)
        if audio is None or "WM/Picture" not in audio:
            return None
        pic = audio["WM/Picture"][0]
        if hasattr(pic, "data") and pic.data:
            target_path.write_bytes(pic.data)
            try:
                with Image.open(target_path) as img:
                    return img.size
            except Exception:
                return None
        return None

    def embed_cover(self, file_path: Path, image_path: Path) -> bool:
        # WMA cover embedding requires ASF picture packaging
        return False

    def remove_cover(self, file_path: Path) -> bool:
        audio = self._get_asf(file_path)
        if audio is None or "WM/Picture" not in audio:
            return False
        del audio["WM/Picture"]
        audio.save()
        return True

    def read_lyrics(self, file_path: Path) -> Optional[str]:
        audio = self._get_asf(file_path)
        if audio and "WM/Lyrics" in audio and audio["WM/Lyrics"]:
            return str(audio["WM/Lyrics"][0])
        return None

    def write_lyrics(self, file_path: Path, lyrics: str) -> None:
        audio = self._get_asf(file_path)
        if audio is None:
            return
        audio["WM/Lyrics"] = [lyrics]
        audio.save()

    def remove_lyrics(self, file_path: Path) -> bool:
        audio = self._get_asf(file_path)
        if audio and "WM/Lyrics" in audio:
            del audio["WM/Lyrics"]
            audio.save()
            return True
        return False
