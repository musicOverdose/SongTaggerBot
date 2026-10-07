"""ID3 tag adapter for MP3, AIFF, and WAV files."""

import io
import logging
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

import mutagen
from mutagen.id3 import (
    ID3, ID3NoHeaderError,
    TIT2, TPE1, TALB, TPE2, TDRC, TYER, TCON, TRCK, TPOS,
    TCOM, COMM, TCOP, USLT, APIC, TIT1, TBPM, TPUB, TPE3,
    TCMP, TSOT, TSOP, TSOA, TSO2, TSRC
)

from app.audio.models import AudioFormat, AudioMetadata
from app.audio.tags.base import BaseTagAdapter

logger = logging.getLogger(__name__)


class ID3Adapter(BaseTagAdapter):
    """Adapter for audio files utilizing ID3v2 tags (MP3, AIFF, WAV)."""

    def can_handle(self, audio_format: AudioFormat) -> bool:
        return audio_format in (AudioFormat.MP3, AudioFormat.AIFF, AudioFormat.WAV)

    def _get_id3(self, file_path: Path, create_if_missing: bool = False) -> Optional[ID3]:
        try:
            return ID3(file_path)
        except ID3NoHeaderError:
            if create_if_missing:
                tags = ID3()
                tags.save(file_path)
                return tags
            return None
        except Exception as e:
            logger.warning(f"Error loading ID3 tags from {file_path}: {e}")
            if create_if_missing:
                try:
                    tags = ID3()
                    tags.save(file_path)
                    return tags
                except Exception:
                    pass
            return None

    def read_metadata(self, file_path: Path) -> AudioMetadata:
        meta = AudioMetadata()
        tags = self._get_id3(file_path)
        if tags is None:
            return meta

        def get_text(frame_id: str) -> Optional[str]:
            frame = tags.get(frame_id)
            if frame and hasattr(frame, "text") and frame.text:
                val = str(frame.text[0]).strip()
                return val if val else None
            return None

        meta.title = get_text("TIT2")
        meta.artist = get_text("TPE1")
        meta.album = get_text("TALB")
        meta.albumartist = get_text("TPE2")
        meta.genre = get_text("TCON")
        meta.composer = get_text("TCOM")
        meta.copyright = get_text("TCOP")
        meta.grouping = get_text("TIT1")
        meta.publisher = get_text("TPUB")
        meta.conductor = get_text("TPE3")
        meta.sort_title = get_text("TSOT")
        meta.sort_artist = get_text("TSOP")
        meta.sort_album = get_text("TSOA")
        meta.sort_album_artist = get_text("TSO2")
        meta.isrc = get_text("TSRC")

        # Date / Year
        date_val = get_text("TDRC") or get_text("TYER")
        if date_val:
            meta.date = date_val

        # BPM
        bpm_str = get_text("TBPM")
        if bpm_str:
            try:
                meta.bpm = int(float(bpm_str))
            except ValueError:
                pass

        # Compilation
        tcmp = get_text("TCMP")
        if tcmp:
            meta.compilation = tcmp in ("1", "true", "True")

        # Track Number / Total
        trck = get_text("TRCK")
        if trck:
            if "/" in trck:
                parts = trck.split("/", 1)
                try:
                    meta.track_number = int(parts[0].strip())
                    meta.track_total = int(parts[1].strip())
                except ValueError:
                    pass
            else:
                try:
                    meta.track_number = int(trck.strip())
                except ValueError:
                    pass

        # Disc Number / Total
        tpos = get_text("TPOS")
        if tpos:
            if "/" in tpos:
                parts = tpos.split("/", 1)
                try:
                    meta.disc_number = int(parts[0].strip())
                    meta.disc_total = int(parts[1].strip())
                except ValueError:
                    pass
            else:
                try:
                    meta.disc_number = int(tpos.strip())
                except ValueError:
                    pass

        # Comment
        for key in tags.keys():
            if key.startswith("COMM"):
                comm_frame = tags[key]
                if hasattr(comm_frame, "text") and comm_frame.text:
                    comm_text = str(comm_frame.text[0]).strip()
                    if comm_text:
                        meta.comment = comm_text
                        break

        # Lyrics (USLT)
        lyrics_text = self.read_lyrics(file_path)
        if lyrics_text:
            meta.lyrics = lyrics_text
            meta.has_lyrics = True

        # Cover art
        for key in tags.keys():
            if key.startswith("APIC"):
                apic = tags[key]
                meta.has_cover = True
                meta.cover_mime = apic.mime
                meta.cover_size_bytes = len(apic.data)
                try:
                    with Image.open(io.BytesIO(apic.data)) as img:
                        meta.cover_dimensions = img.size
                except Exception:
                    pass
                break

        return meta

    def write_metadata(self, file_path: Path, metadata: AudioMetadata) -> None:
        tags = self._get_id3(file_path, create_if_missing=True)
        if tags is None:
            tags = ID3()

        def set_text(frame_cls, frame_id: str, value: Optional[str]):
            if value is not None and value != "":
                tags[frame_id] = frame_cls(encoding=3, text=value)
            elif frame_id in tags:
                del tags[frame_id]

        set_text(TIT2, "TIT2", metadata.title)
        set_text(TPE1, "TPE1", metadata.artist)
        set_text(TALB, "TALB", metadata.album)
        set_text(TPE2, "TPE2", metadata.albumartist)
        set_text(TCON, "TCON", metadata.genre)
        set_text(TCOM, "TCOM", metadata.composer)
        set_text(TCOP, "TCOP", metadata.copyright)
        set_text(TIT1, "TIT1", metadata.grouping)
        set_text(TPUB, "TPUB", metadata.publisher)
        set_text(TPE3, "TPE3", metadata.conductor)
        set_text(TSOT, "TSOT", metadata.sort_title)
        set_text(TSOP, "TSOP", metadata.sort_artist)
        set_text(TSOA, "TSOA", metadata.sort_album)
        set_text(TSO2, "TSO2", metadata.sort_album_artist)
        set_text(TSRC, "TSRC", metadata.isrc)

        # Date / Year
        if metadata.date:
            tags["TDRC"] = TDRC(encoding=3, text=metadata.date)
            tags["TYER"] = TYER(encoding=3, text=metadata.date[:4])
        else:
            tags.delall("TDRC")
            tags.delall("TYER")

        # Track Number / Total
        if metadata.track_number is not None:
            track_str = str(metadata.track_number)
            if metadata.track_total is not None:
                track_str += f"/{metadata.track_total}"
            tags["TRCK"] = TRCK(encoding=3, text=track_str)
        elif "TRCK" in tags:
            del tags["TRCK"]

        # Disc Number / Total
        if metadata.disc_number is not None:
            disc_str = str(metadata.disc_number)
            if metadata.disc_total is not None:
                disc_str += f"/{metadata.disc_total}"
            tags["TPOS"] = TPOS(encoding=3, text=disc_str)
        elif "TPOS" in tags:
            del tags["TPOS"]

        # BPM
        if metadata.bpm is not None:
            tags["TBPM"] = TBPM(encoding=3, text=str(metadata.bpm))
        elif "TBPM" in tags:
            del tags["TBPM"]

        # Compilation
        if metadata.compilation is not None:
            tags["TCMP"] = TCMP(encoding=3, text="1" if metadata.compilation else "0")
        elif "TCMP" in tags:
            del tags["TCMP"]

        # Comment
        if metadata.comment is not None and metadata.comment != "":
            tags.delall("COMM")
            tags.add(COMM(encoding=3, lang="eng", desc="", text=metadata.comment))
        elif metadata.comment == "":
            tags.delall("COMM")

        # Lyrics
        if metadata.lyrics is not None and metadata.lyrics.strip() != "":
            self.write_lyrics(file_path, metadata.lyrics)
        elif metadata.lyrics == "":
            self.remove_lyrics(file_path)

        # Strip extra tags outside primary edit list if requested
        if metadata.strip_extra:
            allowed_prefixes = ("TIT2", "TPE1", "TALB", "TPE2", "TDRC", "TYER", "TCON", "TRCK", "COMM", "USLT", "APIC")
            for frame_id in list(tags.keys()):
                if not any(frame_id.startswith(p) for p in allowed_prefixes):
                    del tags[frame_id]

        tags.save(file_path, v2_version=4)

    def extract_cover(self, file_path: Path, target_path: Path) -> Optional[Tuple[int, int]]:
        tags = self._get_id3(file_path)
        if tags is None:
            return None

        for key in tags.keys():
            if key.startswith("APIC"):
                apic = tags[key]
                target_path.write_bytes(apic.data)
                try:
                    with Image.open(target_path) as img:
                        return img.size
                except Exception:
                    return None
        return None

    def embed_cover(self, file_path: Path, image_path: Path) -> bool:
        tags = self._get_id3(file_path, create_if_missing=True)
        if tags is None:
            tags = ID3()

        try:
            image_bytes = image_path.read_bytes()
            with Image.open(io.BytesIO(image_bytes)) as img:
                mime = Image.MIME.get(img.format, "image/jpeg")

            tags.delall("APIC")
            tags.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,  # Front cover
                    desc="Cover",
                    data=image_bytes,
                )
            )
            tags.save(file_path, v2_version=4)
            return True
        except Exception as e:
            logger.error(f"Failed to embed cover in {file_path}: {e}")
            return False

    def remove_cover(self, file_path: Path) -> bool:
        tags = self._get_id3(file_path)
        if tags is None:
            return False
        if any(k.startswith("APIC") for k in tags.keys()):
            tags.delall("APIC")
            tags.save(file_path, v2_version=4)
            return True
        return False

    def read_lyrics(self, file_path: Path) -> Optional[str]:
        tags = self._get_id3(file_path)
        if tags is None:
            return None
        for key in tags.keys():
            if key.startswith("USLT"):
                frame = tags[key]
                if hasattr(frame, "text") and frame.text:
                    return frame.text
        return None

    def write_lyrics(self, file_path: Path, lyrics: str) -> None:
        tags = self._get_id3(file_path, create_if_missing=True)
        if tags is None:
            tags = ID3()
        tags.delall("USLT")
        tags.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))
        tags.save(file_path, v2_version=4)

    def remove_lyrics(self, file_path: Path) -> bool:
        tags = self._get_id3(file_path)
        if tags is None:
            return False
        if any(k.startswith("USLT") for k in tags.keys()):
            tags.delall("USLT")
            tags.save(file_path, v2_version=4)
            return True
        return False
