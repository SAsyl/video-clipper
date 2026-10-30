"""Timecode conversion and ffmpeg command construction tests."""

from pathlib import Path

import pytest

from app.cutter import build_clip_name, build_command
from app.errors import InvalidTimecodeError
from app.models import CutMode, CutRequest
from app.timecode import format_timecode, parse_timecode, to_ffmpeg_time


@pytest.mark.parametrize(
    ("text", "expected"),
    [("00:00:000", 0), ("01:16:250", 76250), ("00:04:999", 4999), ("08:30:747", 510747)],
)
def test_parse_timecode(text: str, expected: int) -> None:
    assert parse_timecode(text) == expected


@pytest.mark.parametrize("text", ["76", "1:2", "00:60:000", "aa:bb:ccc", "00:00:0000"])
def test_parse_timecode_rejects_malformed(text: str) -> None:
    with pytest.raises(InvalidTimecodeError):
        parse_timecode(text)


@pytest.mark.parametrize("total_ms", [0, 1, 999, 1000, 59999, 60000, 510747])
def test_format_round_trips(total_ms: int) -> None:
    assert parse_timecode(format_timecode(total_ms)) == total_ms


def test_format_timecode_rejects_negative() -> None:
    with pytest.raises(InvalidTimecodeError):
        format_timecode(-1)


def test_to_ffmpeg_time_uses_hours() -> None:
    assert to_ffmpeg_time(76250) == "00:01:16.250"
    assert to_ffmpeg_time(3_661_500) == "01:01:01.500"


def test_cut_request_rejects_inverted_range() -> None:
    with pytest.raises(ValueError):
        CutRequest(source_id="abc", start_ms=9000, end_ms=5000)


def test_cut_request_rejects_empty_range() -> None:
    with pytest.raises(ValueError):
        CutRequest(source_id="abc", start_ms=5000, end_ms=5000)


def test_build_clip_name_is_deterministic() -> None:
    request = CutRequest(source_id="abc", start_ms=76250, end_ms=94100)
    assert build_clip_name(request) == "abc-76250-94100-precise.mp4"


def test_precise_mode_re_encodes() -> None:
    request = CutRequest(source_id="abc", start_ms=76250, end_ms=94100, mode=CutMode.PRECISE)
    command = build_command(Path("in.mp4"), Path("out.mp4"), request, 17850)
    assert "libx264" in command
    assert command[command.index("-ss") + 1] == "00:01:16.250"
    assert command[command.index("-t") + 1] == "00:00:17.850"
    # Input seeking must precede -i so ffmpeg decodes from the preceding keyframe.
    assert command.index("-ss") < command.index("-i")


def test_fast_mode_streams_copy() -> None:
    request = CutRequest(source_id="abc", start_ms=1000, end_ms=2000, mode=CutMode.FAST)
    command = build_command(Path("in.mp4"), Path("out.mp4"), request, 1000)
    assert "copy" in command
    assert "libx264" not in command
