"""Vorbis comment adapter for FLAC, OGG, and OPUS files."""

import base64
import io
import logging
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus

from app.audio.models import AudioFormat, AudioMetadata
from app.audio.tags.base import BaseTagAdapter

logger = logging.getLogger(__name__)


class VorbisAdapter(BaseTagAdapter):
    """Adapter for Vorbis Comment tagging (FLAC, OGG Vorbis, OPUS)."""

    def can_handle(self, audio_format: AudioFormat) -> bool:
        return audio_format in (AudioFormat.FLAC, AudioFormat.OGG, AudioFormat.OPUS)

    def _get_audio_file(self, file_path: Path):
        try:
            return mutagen.File(file_path)
        except Exception as e:
            logger.warning(f"Failed to open audio file {file_path} for Vorbis comments: {e}")
            return None

    def read_metadata(self, file_path: Path) -> AudioMetadata:
        meta = AudioMetadata()
        audio = self._get_audio_file(file_path)
        if audio is None or audio.tags is None:
            return meta

        tags = audio.tags

        def get_tag(key: str) -> Optional[str]:
            for k in (key, key.lower(), key.upper()):
                if k in tags and tags[k]:
                    val = str(tags[k][0]).strip()
                    if val:
                        return val
            return None

        meta.title = get_tag("TITLE")
        meta.artist = get_tag("ARTIST")
        meta.album = get_tag("ALBUM")
        meta.albumartist = get_tag("ALBUMARTIST") or get_tag("ALBUM ARTIST")
        meta.date = get_tag("DATE") or get_tag("YEAR")
        meta.genre = get_tag("GENRE")
        meta.composer = get_tag("COMPOSER")
        meta.comment = get_tag("COMMENT") or get_tag("DESCRIPTION")
        meta.copyright = get_tag("COPYRIGHT")
        meta.grouping = get_tag("GROUPING")
        meta.publisher = get_tag("PUBLISHER") or get_tag("ORGANIZATION")
        meta.conductor = get_tag("CONDUCTOR")
        meta.sort_title = get_tag("TITLESORT")
        meta.sort_artist = get_tag("ARTISTSORT")
        meta.sort_album = get_tag("ALBUMSORT")
        meta.sort_album_artist = get_tag("ALBUMARTISTSORT")
        meta.isrc = get_tag("ISRC")

        # Track number / total
        track_str = get_tag("TRACKNUMBER")
        if track_str:
            if "/" in track_str:
                parts = track_str.split("/", 1)
                try:
                    meta.track_number = int(parts[0].strip())
                    meta.track_total = int(parts[1].strip())
                except ValueError:
                    pass
            else:
                try:
                    meta.track_number = int(track_str.strip())
                except ValueError:
                    pass
        if meta.track_total is None:
            track_total_str = get_tag("TRACKTOTAL") or get_tag("TOTALTRACKS")
            if track_total_str:
                try:
                    meta.track_total = int(track_total_str.strip())
                except ValueError:
                    pass

        # Disc number / total
        disc_str = get_tag("DISCNUMBER")
        if disc_str:
            if "/" in disc_str:
                parts = disc_str.split("/", 1)
                try:
                    meta.disc_number = int(parts[0].strip())
                    meta.disc_total = int(parts[1].strip())
                except ValueError:
                    pass
            else:
                try:
                    meta.disc_number = int(disc_str.strip())
                except ValueError:
                    pass
        if meta.disc_total is None:
            disc_total_str = get_tag("DISCTOTAL") or get_tag("TOTALDISCS")
            if disc_total_str:
                try:
                    meta.disc_total = int(disc_total_str.strip())
                except ValueError:
                    pass

        # BPM
        bpm_str = get_tag("BPM")
        if bpm_str:
            try:
                meta.bpm = int(float(bpm_str))
            except ValueError:
                pass

        # Compilation
        comp_str = get_tag("COMPILATION")
        if comp_str:
            meta.compilation = comp_str in ("1", "true", "True")

        # Lyrics
        lyrics_str = get_tag("LYRICS") or get_tag("UNSYNCEDLYRICS")
        if lyrics_str:
            meta.lyrics = lyrics_str
            meta.has_lyrics = True

        # Cover check
        # FLAC pictures
        if isinstance(audio, FLAC) and audio.pictures:
            pic = audio.pictures[0]
            meta.has_cover = True
            meta.cover_mime = pic.mime
            meta.cover_size_bytes = len(pic.data)
            try:
                with Image.open(io.BytesIO(pic.data)) as img:
                    meta.cover_dimensions = img.size
            except Exception:
                pass
        elif "metadata_block_picture" in tags:
            try:
                raw_b64 = tags["metadata_block_picture"][0]
                raw_data = base64.b64decode(raw_b64)
                pic = Picture(raw_data)
                meta.has_cover = True
                meta.cover_mime = pic.mime
                meta.cover_size_bytes = len(pic.data)
                with Image.open(io.BytesIO(pic.data)) as img:
                    meta.cover_dimensions = img.size
            except Exception:
                pass

        return meta

    def write_metadata(self, file_path: Path, metadata: AudioMetadata) -> None:
        audio = self._get_audio_file(file_path)
        if audio is None:
            return

        if audio.tags is None:
            audio.add_tags()

        tags = audio.tags

        def set_tag(key: str, val: Optional[str]):
            for k in (key, key.lower(), key.upper()):
                if k in tags:
                    del tags[k]
            if val is not None and val != "":
                tags[key.upper()] = [val]

        set_tag("TITLE", metadata.title)
        set_tag("ARTIST", metadata.artist)
        set_tag("ALBUM", metadata.album)
        set_tag("ALBUMARTIST", metadata.albumartist)
        set_tag("DATE", metadata.date)
        set_tag("GENRE", metadata.genre)
        set_tag("COMPOSER", metadata.composer)
        set_tag("COMMENT", metadata.comment)
        set_tag("COPYRIGHT", metadata.copyright)
        set_tag("GROUPING", metadata.grouping)
        set_tag("PUBLISHER", metadata.publisher)
        set_tag("CONDUCTOR", metadata.conductor)
        set_tag("TITLESORT", metadata.sort_title)
        set_tag("ARTISTSORT", metadata.sort_artist)
        set_tag("ALBUMSORT", metadata.sort_album)
        set_tag("ALBUMARTISTSORT", metadata.sort_album_artist)
        set_tag("ISRC", metadata.isrc)

        # Track
        if metadata.track_number is not None:
            set_tag("TRACKNUMBER", str(metadata.track_number))
        else:
            set_tag("TRACKNUMBER", None)

        if metadata.track_total is not None:
            set_tag("TRACKTOTAL", str(metadata.track_total))
        else:
            set_tag("TRACKTOTAL", None)

        # Disc
        if metadata.disc_number is not None:
            set_tag("DISCNUMBER", str(metadata.disc_number))
        else:
            set_tag("DISCNUMBER", None)

        if metadata.disc_total is not None:
            set_tag("DISCTOTAL", str(metadata.disc_total))
        else:
            set_tag("DISCTOTAL", None)

        # BPM
        if metadata.bpm is not None:
            set_tag("BPM", str(metadata.bpm))
        else:
            set_tag("BPM", None)

        # Compilation
        if metadata.compilation is not None:
            set_tag("COMPILATION", "1" if metadata.compilation else "0")
        else:
            set_tag("COMPILATION", None)

        # Lyrics
        if metadata.lyrics is not None and metadata.lyrics.strip() != "":
            set_tag("LYRICS", metadata.lyrics)
        elif metadata.lyrics == "":
            set_tag("LYRICS", None)
            set_tag("UNSYNCEDLYRICS", None)

        audio.save()

    def extract_cover(self, file_path: Path, target_path: Path) -> Optional[Tuple[int, int]]:
        audio = self._get_audio_file(file_path)
        if audio is None:
            return None

        # FLAC
        if isinstance(audio, FLAC) and audio.pictures:
            pic = audio.pictures[0]
            target_path.write_bytes(pic.data)
            try:
                with Image.open(target_path) as img:
                    return img.size
            except Exception:
                return None

        # Ogg Vorbis / Opus with METADATA_BLOCK_PICTURE
        if audio.tags and "metadata_block_picture" in audio.tags:
            try:
                raw_b64 = audio.tags["metadata_block_picture"][0]
                raw_data = base64.b64decode(raw_b64)
                pic = Picture(raw_data)
                target_path.write_bytes(pic.data)
                with Image.open(target_path) as img:
                    return img.size
            except Exception as e:
                logger.warning(f"Error extracting Vorbis picture from {file_path}: {e}")
                return None

        return None

    def embed_cover(self, file_path: Path, image_path: Path) -> bool:
        audio = self._get_audio_file(file_path)
        if audio is None:
            return False

        try:
            image_bytes = image_path.read_bytes()
            with Image.open(io.BytesIO(image_bytes)) as img:
                mime = Image.MIME.get(img.format, "image/jpeg")
                width, height = img.size
                depth = 24

            pic = Picture()
            pic.type = 3  # Front cover
            pic.mime = mime
            pic.desc = "Cover"
            pic.width = width
            pic.height = height
            pic.depth = depth
            pic.data = image_bytes

            if isinstance(audio, FLAC):
                audio.clear_pictures()
                audio.add_picture(pic)
                audio.save()
                return True
            else:
                # Ogg Vorbis / Opus
                if audio.tags is None:
                    audio.add_tags()
                encoded = base64.b64encode(pic.write()).decode("ascii")
                audio.tags["metadata_block_picture"] = [encoded]
                audio.save()
                return True
        except Exception as e:
            logger.error(f"Failed to embed cover in Vorbis file {file_path}: {e}")
            return False

    def remove_cover(self, file_path: Path) -> bool:
        audio = self._get_audio_file(file_path)
        if audio is None:
            return False

        changed = False
        if isinstance(audio, FLAC) and audio.pictures:
            audio.clear_pictures()
            changed = True
        elif audio.tags and "metadata_block_picture" in audio.tags:
            del audio.tags["metadata_block_picture"]
            changed = True

        if changed:
            audio.save()
            return True
        return False

    def read_lyrics(self, file_path: Path) -> Optional[str]:
        audio = self._get_audio_file(file_path)
        if audio is None or audio.tags is None:
            return None
        for k in ("LYRICS", "lyrics", "UNSYNCEDLYRICS", "unsyncedlyrics"):
            if k in audio.tags and audio.tags[k]:
                return audio.tags[k][0]
        return None

    def write_lyrics(self, file_path: Path, lyrics: str) -> None:
        audio = self._get_audio_file(file_path)
        if audio is None:
            return
        if audio.tags is None:
            audio.add_tags()
        audio.tags["LYRICS"] = [lyrics]
        audio.save()

    def remove_lyrics(self, file_path: Path) -> bool:
        audio = self._get_audio_file(file_path)
        if audio is None or audio.tags is None:
            return False
        changed = False
        for k in ("LYRICS", "lyrics", "UNSYNCEDLYRICS", "unsyncedlyrics"):
            if k in audio.tags:
                del audio.tags[k]
                changed = True
        if changed:
            audio.save()
            return True
        return False
