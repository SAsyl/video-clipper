"""yt-dlp wrapper that downloads a source video into the media directory."""

from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from app.config import SOURCE_DIR
from app.errors import DownloadError
from app.jobs import registry
from app.sources import describe_source

# Progress is reserved for the download itself; probing finishes the job.
DOWNLOAD_PROGRESS_CEILING: float = 0.95


def format_selector(max_height: int) -> str:
    """Prefer browser friendly H.264/AAC, falling back to whatever exists."""
    return (
        f"bv*[vcodec^=avc1][height<=?{max_height}]+ba[acodec^=mp4a]/"
        f"b[ext=mp4][height<=?{max_height}]/"
        f"bv*[height<=?{max_height}]+ba/b"
    )


def download_source(job_id: str, url: str, max_height: int) -> None:
    """Download ``url`` and record the resulting source on the job."""
    registry.mark_running(job_id, "Reading video information")
    info = _run_yt_dlp(job_id, url, max_height)
    path = _downloaded_path(info)

    registry.update_progress(job_id, DOWNLOAD_PROGRESS_CEILING, "Inspecting file")
    title = info.get("title")
    source = describe_source(path, str(title) if title else None)
    registry.mark_downloaded(job_id, source)


def _run_yt_dlp(job_id: str, url: str, max_height: int) -> dict[str, Any]:
    options: dict[str, Any] = {
        "format": format_selector(max_height),
        "outtmpl": str(SOURCE_DIR / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [_make_hook(job_id)],
        "retries": 3,
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
    except YtDlpDownloadError as error:
        raise DownloadError(f"yt-dlp could not download the video: {error}") from error
    if info is None:
        raise DownloadError("yt-dlp returned no information for this link")
    return info


def _make_hook(job_id: str):
    """Build a yt-dlp progress hook bound to one job."""

    def hook(status: dict[str, Any]) -> None:
        if status.get("status") != "downloading":
            return
        total = status.get("total_bytes") or status.get("total_bytes_estimate")
        if not total:
            return
        done = float(status.get("downloaded_bytes") or 0)
        fraction = min(done / float(total), 1.0) * DOWNLOAD_PROGRESS_CEILING
        registry.update_progress(job_id, fraction, "Downloading video")

    return hook


def _downloaded_path(info: dict[str, Any]) -> Path:
    """Resolve the final merged file path reported by yt-dlp."""
    downloads = info.get("requested_downloads") or []
    for entry in downloads:
        filepath = entry.get("filepath")
        if filepath:
            return Path(filepath)
    raise DownloadError("yt-dlp did not report a downloaded file path")
