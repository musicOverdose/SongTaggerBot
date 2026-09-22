"""Cover art manager: image validation, conversion, and Telegram thumbnail generation."""

import asyncio
import io
import logging
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_THUMBNAIL_DIMENSION = 320
MAX_THUMBNAIL_BYTES = 200 * 1024  # 200 KB


class CoverManager:
    """Handles album artwork processing, validation, and thumbnail generation."""

    @staticmethod
    def validate_image_sync(image_path: Path) -> Tuple[bool, Optional[str], Optional[Tuple[int, int]], int]:
        """
        Validate image file.
        Returns (is_valid, format_str, (width, height), size_bytes).
        """
        try:
            size_bytes = image_path.stat().st_size
            with Image.open(image_path) as img:
                img_format = img.format
                width, height = img.size
                if img_format not in ("JPEG", "PNG", "WEBP"):
                    return False, img_format, None, size_bytes
                return True, img_format, (width, height), size_bytes
        except Exception as e:
            logger.warning(f"Invalid image file {image_path}: {e}")
            return False, None, None, 0

    @classmethod
    async def validate_image(cls, image_path: Path) -> Tuple[bool, Optional[str], Optional[Tuple[int, int]], int]:
        return await asyncio.to_thread(cls.validate_image_sync, image_path)

    @staticmethod
    def prepare_embedded_cover_sync(source_image: Path, target_image: Path) -> bool:
        """
        Ensure image is suitable for embedding into audio files.
        Converts RGBA/P/WebP to high-quality RGB JPEG if needed.
        """
        try:
            with Image.open(source_image) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode in ("RGBA", "LA", "P"):
                    # Create white background for transparency
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    bg.paste(img, mask=img.split()[3])
                    bg.save(target_image, format="JPEG", quality=95, optimize=True)
                elif img.format != "JPEG":
                    rgb_img = img.convert("RGB")
                    rgb_img.save(target_image, format="JPEG", quality=95, optimize=True)
                else:
                    target_image.write_bytes(source_image.read_bytes())
            return True
        except Exception as e:
            logger.error(f"Failed to prepare embedded cover {source_image}: {e}")
            return False

    @classmethod
    async def prepare_embedded_cover(cls, source_image: Path, target_image: Path) -> bool:
        return await asyncio.to_thread(cls.prepare_embedded_cover_sync, source_image, target_image)

    @staticmethod
    def generate_telegram_thumbnail_sync(source_image: Path, target_thumb: Path) -> bool:
        """
        Generate Telegram-compliant thumbnail:
        - JPEG
        - <= 320x320 pixels
        - <= 200 KB file size
        """
        try:
            with Image.open(source_image) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode != "RGB":
                    img = img.convert("RGB")

                # Resize maintaining aspect ratio to fit inside 320x320
                img.thumbnail((MAX_THUMBNAIL_DIMENSION, MAX_THUMBNAIL_DIMENSION), Image.Resampling.LANCZOS)

                # Compress and check byte size limit
                quality = 90
                while quality >= 20:
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=quality, optimize=True)
                    data = buf.getvalue()
                    if len(data) <= MAX_THUMBNAIL_BYTES:
                        target_thumb.write_bytes(data)
                        return True
                    quality -= 10

                # Final attempt with lower quality if still above limit
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=15, optimize=True)
                target_thumb.write_bytes(buf.getvalue())
                return True
        except Exception as e:
            logger.error(f"Failed to generate Telegram thumbnail from {source_image}: {e}")
            return False

    @classmethod
    async def generate_telegram_thumbnail(cls, source_image: Path, target_thumb: Path) -> bool:
        return await asyncio.to_thread(cls.generate_telegram_thumbnail_sync, source_image, target_thumb)
