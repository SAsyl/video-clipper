"""ffprobe based media inspection."""

import json
import subprocess
from pathlib import Path
from typing import Any, NamedTuple

from app.config import FFPROBE_BIN
from app.errors import ProbeError

PROBE_TIMEOUT_SECONDS: int = 60


class MediaInfo(NamedTuple):
    duration_ms: int
    width: int
    height: int
    fps: float


def probe_media(path: Path) -> MediaInfo:
    """Return duration, resolution and frame rate for a media file."""
    command = [
        FFPROBE_BIN,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=PROBE_TIMEOUT_SECONDS, check=True
        )
    except subprocess.CalledProcessError as error:
        raise ProbeError(f"ffprobe failed for {path.name}: {error.stderr.strip()}") from error
    except subprocess.TimeoutExpired as error:
        raise ProbeError(f"ffprobe timed out for {path.name}") from error

    payload: dict[str, Any] = json.loads(result.stdout)
    video = _first_video_stream(payload, path)
    return MediaInfo(
        duration_ms=_duration_ms(payload, video, path),
        width=int(video.get("width", 0)),
        height=int(video.get("height", 0)),
        fps=_frame_rate(video),
    )


def _first_video_stream(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    for stream in payload.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    raise ProbeError(f"No video stream found in {path.name}")


def _duration_ms(payload: dict[str, Any], video: dict[str, Any], path: Path) -> int:
    raw = payload.get("format", {}).get("duration") or video.get("duration")
    if raw is None:
        raise ProbeError(f"Could not determine duration of {path.name}")
    return int(round(float(raw) * 1000))


def _frame_rate(video: dict[str, Any]) -> float:
    raw = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
    numerator, _, denominator = str(raw).partition("/")
    try:
        divisor = float(denominator or "1")
        return float(numerator) / divisor if divisor else 0.0
    except ValueError:
        return 0.0
