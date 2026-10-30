"""Conversions between mm:ss:ms timecodes, milliseconds and ffmpeg time strings."""

import re

from app.errors import InvalidTimecodeError

TIMECODE_PATTERN: re.Pattern[str] = re.compile(r"^(\d{1,4}):([0-5]?\d):(\d{1,3})$")

MS_PER_SECOND: int = 1_000
MS_PER_MINUTE: int = 60_000
MS_PER_HOUR: int = 3_600_000


def parse_timecode(value: str) -> int:
    """Parse an ``mm:ss:ms`` timecode into total milliseconds."""
    match = TIMECODE_PATTERN.match(value.strip())
    if match is None:
        raise InvalidTimecodeError(f"Timecode must look like mm:ss:ms, got {value!r}")
    minutes, seconds, millis = (int(group) for group in match.groups())
    return minutes * MS_PER_MINUTE + seconds * MS_PER_SECOND + millis


def format_timecode(total_ms: int) -> str:
    """Render milliseconds as an ``mm:ss:ms`` timecode."""
    if total_ms < 0:
        raise InvalidTimecodeError(f"Timecode cannot be negative, got {total_ms}")
    minutes, rest = divmod(total_ms, MS_PER_MINUTE)
    seconds, millis = divmod(rest, MS_PER_SECOND)
    return f"{minutes:02d}:{seconds:02d}:{millis:03d}"


def to_ffmpeg_time(total_ms: int) -> str:
    """Render milliseconds as the ``HH:MM:SS.mmm`` form ffmpeg expects."""
    if total_ms < 0:
        raise InvalidTimecodeError(f"ffmpeg time cannot be negative, got {total_ms}")
    hours, rest = divmod(total_ms, MS_PER_HOUR)
    minutes, rest = divmod(rest, MS_PER_MINUTE)
    seconds, millis = divmod(rest, MS_PER_SECOND)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
