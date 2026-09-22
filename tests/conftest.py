"""Pytest configuration and synthetic audio/image fixtures."""

import io
from pathlib import Path
import subprocess
import pytest
from PIL import Image

from app.database.connection import Database
from app.database.repository import DatabaseRepository


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("audio_fixtures")
    return base


def _create_synthetic_audio(output_path: Path, codec_args: list[str]) -> Path:
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=5",
        *codec_args,
        str(output_path),
    ]
    res = subprocess.run(cmd, capture_output=True)
    assert res.returncode == 0, f"FFmpeg failed to create {output_path}: {res.stderr}"
    assert output_path.exists()
    return output_path


@pytest.fixture(scope="session")
def sample_mp3(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "test_sample.mp3"
    return _create_synthetic_audio(path, ["-c:a", "libmp3lame", "-b:a", "128k"])


@pytest.fixture(scope="session")
def sample_flac(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "test_sample.flac"
    return _create_synthetic_audio(path, ["-c:a", "flac"])


@pytest.fixture(scope="session")
def sample_m4a(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "test_sample.m4a"
    return _create_synthetic_audio(path, ["-c:a", "aac", "-b:a", "128k"])


@pytest.fixture(scope="session")
def sample_ogg(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "test_sample.ogg"
    return _create_synthetic_audio(path, ["-c:a", "libvorbis", "-q:a", "4"])


@pytest.fixture(scope="session")
def sample_opus(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "test_sample.opus"
    return _create_synthetic_audio(path, ["-c:a", "libopus", "-b:a", "96k"])


@pytest.fixture(scope="session")
def sample_wav(fixtures_dir: Path) -> Path:
    path = fixtures_dir / "test_sample.wav"
    return _create_synthetic_audio(path, ["-c:a", "pcm_s16le"])


@pytest.fixture
def sample_jpeg(tmp_path: Path) -> Path:
    img_path = tmp_path / "cover.jpg"
    img = Image.new("RGB", (600, 600), color=(255, 0, 128))
    img.save(img_path, format="JPEG")
    return img_path


@pytest.fixture
def sample_png(tmp_path: Path) -> Path:
    img_path = tmp_path / "cover.png"
    img = Image.new("RGBA", (500, 500), color=(0, 200, 255, 200))
    img.save(img_path, format="PNG")
    return img_path


@pytest.fixture
def sample_webp(tmp_path: Path) -> Path:
    img_path = tmp_path / "cover.webp"
    img = Image.new("RGB", (400, 400), color=(50, 255, 50))
    img.save(img_path, format="WEBP")
    return img_path


@pytest.fixture
async def test_db(tmp_path: Path):
    db_file = tmp_path / "test.db"
    db = Database(db_file)
    await db.connect()
    yield db
    await db.close()


@pytest.fixture
async def test_repo(test_db: Database) -> DatabaseRepository:
    return DatabaseRepository(test_db)
