"""ffmpeg wrapper that cuts a millisecond accurate clip out of a source file."""

import subprocess
import tempfile
from pathlib import Path

from app.config import CLIP_DIR, FFMPEG_BIN
from app.errors import CutError
from app.jobs import registry
from app.models import ClipInfo, CutMode, CutRequest
from app.probe import probe_media
from app.storage import resolve_source
from app.timecode import to_ffmpeg_time

PROGRESS_PREFIX: str = "out_time_us="


def cut_clip(job_id: str, request: CutRequest) -> None:
    """Produce the requested clip and record it on the job."""
    duration_ms = request.end_ms - request.start_ms
    if duration_ms <= 0:
        raise CutError("End timecode must be greater than start timecode")

    source_path = resolve_source(request.source_id)
    output_path = CLIP_DIR / build_clip_name(request)
    registry.mark_running(job_id, "Cutting clip")

    command = build_command(source_path, output_path, request, duration_ms)
    _run_ffmpeg(command, duration_ms, job_id)

    if not output_path.is_file():
        raise CutError("ffmpeg finished but produced no output file")

    media = probe_media(output_path)
    clip = ClipInfo(
        name=output_path.name,
        start_ms=request.start_ms,
        end_ms=request.end_ms,
        duration_ms=media.duration_ms,
        size_bytes=output_path.stat().st_size,
        media_url=f"/media/clips/{output_path.name}",
        download_url=f"/media/clips/{output_path.name}?download=1",
    )
    registry.mark_cut(job_id, clip)


def build_clip_name(request: CutRequest) -> str:
    """Build a deterministic, filesystem safe clip filename."""
    return f"{request.source_id}-{request.start_ms}-{request.end_ms}-{request.mode.value}.mp4"


def build_command(
    source: Path, output: Path, request: CutRequest, duration_ms: int
) -> list[str]:
    """Assemble the ffmpeg invocation for the requested cut mode."""
    codec_args = (
        ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k"]
        if request.mode is CutMode.PRECISE
        else ["-c", "copy", "-avoid_negative_ts", "make_zero"]
    )
    return [
        FFMPEG_BIN,
        "-hide_banner",
        "-nostdin",
        "-loglevel", "error",
        "-y",
        "-ss", to_ffmpeg_time(request.start_ms),
        "-i", str(source),
        "-t", to_ffmpeg_time(duration_ms),
        *codec_args,
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        "-nostats",
        str(output),
    ]


def _run_ffmpeg(command: list[str], duration_ms: int, job_id: str) -> None:
    """Run ffmpeg, forwarding its progress to the job registry."""
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as error_log:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=error_log, text=True, bufsize=1
        )
        if process.stdout is None:
            raise CutError("Could not read ffmpeg progress output")
        for line in process.stdout:
            _report_progress(line, duration_ms, job_id)
        code = process.wait()
        if code != 0:
            error_log.seek(0)
            raise CutError(f"ffmpeg exited with code {code}: {error_log.read().strip()}")


def _report_progress(line: str, duration_ms: int, job_id: str) -> None:
    """Translate one ffmpeg progress line into a job progress update."""
    if not line.startswith(PROGRESS_PREFIX) or duration_ms <= 0:
        return
    raw = line[len(PROGRESS_PREFIX):].strip()
    if not raw.isdigit():
        return
    done_ms = int(raw) / 1000.0
    registry.update_progress(job_id, done_ms / duration_ms, "Cutting clip")
