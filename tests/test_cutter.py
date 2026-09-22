"""Tests for AudioCutter: timestamp parsing and FFmpeg trimming."""

from pathlib import Path
import shutil
import pytest

from app.audio.cutter import AudioCutter
from app.audio.probe import AudioProber


def test_time_range_parsing():
    # Valid ranges
    assert AudioCutter.parse_time_range("00:10 - 03:45") == (10.0, 225.0)
    assert AudioCutter.parse_time_range("00:00:10 - 00:03:45") == (10.0, 225.0)
    assert AudioCutter.parse_time_range("start 00:10 end 03:45") == (10.0, 225.0)
    assert AudioCutter.parse_time_range("10 - 90") == (10.0, 90.0)
    assert AudioCutter.parse_time_range("01:30.500 to 02:00.000") == (90.5, 120.0)

    # Invalid ranges
    assert AudioCutter.parse_time_range("invalid string") is None
    assert AudioCutter.parse_time_range("03:00 - 01:00") is None  # End before start
    assert AudioCutter.parse_time_range("01:00 - 01:00") is None  # Equal


def test_time_formatting():
    assert AudioCutter.format_seconds(75) == "01:15"
    assert AudioCutter.format_seconds(3665) == "01:01:05"


@pytest.mark.asyncio
async def test_audio_cut_execution(sample_mp3: Path, tmp_path: Path):
    input_file = tmp_path / "cut_input.mp3"
    output_file = tmp_path / "cut_output.mp3"
    shutil.copy2(sample_mp3, input_file)

    # Cut 2 seconds: from 1.0s to 3.0s
    success = await AudioCutter.cut_audio(
        input_path=input_file,
        output_path=output_file,
        start_seconds=1.0,
        end_seconds=3.0,
    )

    assert success is True
    assert output_file.exists()
    assert output_file.stat().st_size > 0

    # Probe duration of cut file
    tech = await AudioProber.probe(output_file)
    assert tech is not None
    # Expected duration ~2.0 seconds (tolerance within 0.5s for audio frame boundaries)
    assert 1.5 <= tech.duration_seconds <= 2.5
