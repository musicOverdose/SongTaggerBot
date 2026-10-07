"""MP4/M4A tag adapter using Apple iTunes atoms."""

import io
import logging
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

from mutagen.mp4 import MP4, MP4Cover, MP4Tags

from app.audio.models import AudioFormat, AudioMetadata
from app.audio.tags.base import BaseTagAdapter

logger = logging.getLogger(__name__)


class MP4Adapter(BaseTagAdapter):
    """Adapter for MP4 and M4A audio files utilizing Apple atoms."""

    def can_handle(self, audio_format: AudioFormat) -> bool:
        return audio_format in (AudioFormat.M4A, AudioFormat.MP4)

    def _get_mp4(self, file_path: Path) -> Optional[MP4]:
        try:
            return MP4(file_path)
        except Exception as e:
            logger.warning(f"Error loading MP4 audio {file_path}: {e}")
            return None

    def read_metadata(self, file_path: Path) -> AudioMetadata:
        meta = AudioMetadata()
        audio = self._get_mp4(file_path)
        if audio is None or audio.tags is None:
            return meta

        tags = audio.tags

        def get_atom(key: str) -> Optional[str]:
            if key in tags and tags[key]:
                val = tags[key][0]
                if isinstance(val, str):
                    s = val.strip()
                    return s if s else None
                return str(val)
            return None

        meta.title = get_atom("\xa9nam")
        meta.artist = get_atom("\xa9ART")
        meta.album = get_atom("\xa9alb")
        meta.albumartist = get_atom("aART")
        meta.date = get_atom("\xa9day")
        meta.genre = get_atom("\xa9gen")
        meta.composer = get_atom("\xa9wrt")
        meta.comment = get_atom("\xa9cmt")
        meta.copyright = get_atom("cprt")
        meta.grouping = get_atom("\xa9grp")
        meta.sort_title = get_atom("sonm")
        meta.sort_artist = get_atom("soar")
        meta.sort_album = get_atom("soal")
        meta.sort_album_artist = get_atom("soaa")

        # Track number / total: [(num, total)]
        if "trkn" in tags and tags["trkn"]:
            trkn_tuple = tags["trkn"][0]
            if len(trkn_tuple) >= 1 and trkn_tuple[0] > 0:
                meta.track_number = trkn_tuple[0]
            if len(trkn_tuple) >= 2 and trkn_tuple[1] > 0:
                meta.track_total = trkn_tuple[1]

        # Disc number / total: [(num, total)]
        if "disk" in tags and tags["disk"]:
            disk_tuple = tags["disk"][0]
            if len(disk_tuple) >= 1 and disk_tuple[0] > 0:
                meta.disc_number = disk_tuple[0]
            if len(disk_tuple) >= 2 and disk_tuple[1] > 0:
                meta.disc_total = disk_tuple[1]

        # BPM: [bpm]
        if "tmpo" in tags and tags["tmpo"]:
            meta.bpm = tags["tmpo"][0]

        # Compilation
        if "cpil" in tags:
            meta.compilation = bool(tags["cpil"])

        # Lyrics: \xa9lyr
        if "\xa9lyr" in tags and tags["\xa9lyr"]:
            meta.lyrics = tags["\xa9lyr"][0]
            meta.has_lyrics = True

        # Cover art: covr
        if "covr" in tags and tags["covr"]:
            cover_data = tags["covr"][0]
            meta.has_cover = True
            meta.cover_size_bytes = len(cover_data)
            try:
                with Image.open(io.BytesIO(cover_data)) as img:
                    meta.cover_dimensions = img.size
                    meta.cover_mime = Image.MIME.get(img.format, "image/jpeg")
            except Exception:
                pass

        return meta

    def write_metadata(self, file_path: Path, metadata: AudioMetadata) -> None:
        audio = self._get_mp4(file_path)
        if audio is None:
            return

        if audio.tags is None:
            audio.add_tags()

        tags = audio.tags

        def set_atom(key: str, val: Optional[str]):
            if val is not None and val != "":
                tags[key] = [val]
            elif key in tags:
                del tags[key]

        set_atom("\xa9nam", metadata.title)
        set_atom("\xa9ART", metadata.artist)
        set_atom("\xa9alb", metadata.album)
        set_atom("aART", metadata.albumartist)
        set_atom("\xa9day", metadata.date)
        set_atom("\xa9gen", metadata.genre)
        set_atom("\xa9wrt", metadata.composer)
        set_atom("\xa9cmt", metadata.comment)
        set_atom("cprt", metadata.copyright)
        set_atom("\xa9grp", metadata.grouping)
        set_atom("sonm", metadata.sort_title)
        set_atom("soar", metadata.sort_artist)
        set_atom("soal", metadata.sort_album)
        set_atom("soaa", metadata.sort_album_artist)

        # Track
        if metadata.track_number is not None:
            total = metadata.track_total if metadata.track_total is not None else 0
            tags["trkn"] = [(metadata.track_number, total)]
        elif "trkn" in tags:
            del tags["trkn"]

        # Disc
        if metadata.disc_number is not None:
            total = metadata.disc_total if metadata.disc_total is not None else 0
            tags["disk"] = [(metadata.disc_number, total)]
        elif "disk" in tags:
            del tags["disk"]

        # BPM
        if metadata.bpm is not None:
            tags["tmpo"] = [int(metadata.bpm)]
        elif "tmpo" in tags:
            del tags["tmpo"]

        # Compilation
        if metadata.compilation is not None:
            tags["cpil"] = bool(metadata.compilation)
        elif "cpil" in tags:
            del tags["cpil"]

        # Lyrics
        if metadata.lyrics is not None and metadata.lyrics.strip() != "":
            tags["\xa9lyr"] = [metadata.lyrics]
        elif metadata.lyrics == "":
            if "\xa9lyr" in tags:
                del tags["\xa9lyr"]

        if metadata.strip_extra:
            allowed_mp4 = {
                "\xa9nam", "\xa9ART", "\xa9alb", "aART", "\xa9day",
                "\xa9gen", "trkn", "\xa9cmt", "\xa9lyr", "covr",
            }
            for k in list(tags.keys()):
                if k not in allowed_mp4:
                    del tags[k]

        audio.save()

    def extract_cover(self, file_path: Path, target_path: Path) -> Optional[Tuple[int, int]]:
        audio = self._get_mp4(file_path)
        if audio is None or audio.tags is None:
            return None

        if "covr" in audio.tags and audio.tags["covr"]:
            cover_data = audio.tags["covr"][0]
            target_path.write_bytes(bytes(cover_data))
            try:
                with Image.open(target_path) as img:
                    return img.size
            except Exception:
                return None
        return None

    def embed_cover(self, file_path: Path, image_path: Path) -> bool:
        audio = self._get_mp4(file_path)
        if audio is None:
            return False

        if audio.tags is None:
            audio.add_tags()

        try:
            image_bytes = image_path.read_bytes()
            with Image.open(io.BytesIO(image_bytes)) as img:
                fmt = MP4Cover.FORMAT_PNG if img.format == "PNG" else MP4Cover.FORMAT_JPEG

            cover = MP4Cover(image_bytes, imageformat=fmt)
            audio.tags["covr"] = [cover]
            audio.save()
            return True
        except Exception as e:
            logger.error(f"Failed to embed cover in MP4 {file_path}: {e}")
            return False

    def remove_cover(self, file_path: Path) -> bool:
        audio = self._get_mp4(file_path)
        if audio is None or audio.tags is None:
            return False
        if "covr" in audio.tags:
            del audio.tags["covr"]
            audio.save()
            return True
        return False

    def read_lyrics(self, file_path: Path) -> Optional[str]:
        audio = self._get_mp4(file_path)
        if audio is None or audio.tags is None:
            return None
        if "\xa9lyr" in audio.tags and audio.tags["\xa9lyr"]:
            return audio.tags["\xa9lyr"][0]
        return None

    def write_lyrics(self, file_path: Path, lyrics: str) -> None:
        audio = self._get_mp4(file_path)
        if audio is None:
            return
        if audio.tags is None:
            audio.add_tags()
        audio.tags["\xa9lyr"] = [lyrics]
        audio.save()

    def remove_lyrics(self, file_path: Path) -> bool:
        audio = self._get_mp4(file_path)
        if audio is None or audio.tags is None:
            return False
        if "\xa9lyr" in audio.tags:
            del audio.tags["\xa9lyr"]
            audio.save()
            return True
        return False
