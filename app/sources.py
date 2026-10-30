"""Shared description of a downloaded source file."""

from pathlib import Path

from app.models import SourceInfo
from app.probe import probe_media


def describe_source(path: Path, title: str | None = None) -> SourceInfo:
    """Probe ``path`` and build the payload the UI needs to preview it."""
    media = probe_media(path)
    return SourceInfo(
        id=path.stem,
        title=title or path.stem,
        duration_ms=media.duration_ms,
        width=media.width,
        height=media.height,
        fps=media.fps,
        size_bytes=path.stat().st_size,
        media_url=f"/media/source/{path.name}",
    )
