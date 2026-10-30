"""Drag and drop import of a video file that already exists on the user's machine."""

import re
from pathlib import Path

from fastapi import UploadFile

from app.config import (
    ALLOWED_UPLOAD_SUFFIXES,
    MAX_UPLOAD_STEM_LENGTH,
    SOURCE_DIR,
    UPLOAD_CHUNK_BYTES,
)
from app.errors import ProbeError, UnsupportedMediaError, VideoClipperError
from app.models import SourceInfo
from app.sources import describe_source

UNSAFE_CHARS: re.Pattern[str] = re.compile(r"[^A-Za-z0-9_-]+")
FALLBACK_STEM: str = "upload"


async def ingest_upload(upload: UploadFile) -> SourceInfo:
    """Store an uploaded file and describe it, discarding anything unreadable."""
    path = await _store(upload)
    display_name = Path(upload.filename or path.name).name
    try:
        return describe_source(path, Path(display_name).stem)
    except ProbeError as error:
        # A wrong extension is the user's problem, not a server fault, and the
        # ffprobe message would leak server paths.
        path.unlink(missing_ok=True)
        raise UnsupportedMediaError(
            f"{display_name} is not a readable video file"
        ) from error
    except VideoClipperError:
        path.unlink(missing_ok=True)
        raise


def safe_stem(filename: str | None) -> str:
    """Reduce a client supplied filename to a filesystem safe identifier."""
    stem = Path(filename or "").stem
    cleaned = UNSAFE_CHARS.sub("-", stem).strip("-")[:MAX_UPLOAD_STEM_LENGTH].strip("-")
    return cleaned or FALLBACK_STEM


def validate_suffix(filename: str | None) -> str:
    """Return the lowercased container suffix, rejecting unsupported ones."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        supported = ", ".join(sorted(ALLOWED_UPLOAD_SUFFIXES))
        raise UnsupportedMediaError(
            f"{suffix or 'That file'} is not a supported video container. Supported: {supported}"
        )
    return suffix


def unique_source_path(stem: str, suffix: str) -> Path:
    """Pick a free path under the source directory, never overwriting an existing file."""
    candidate = SOURCE_DIR / f"{stem}{suffix}"
    counter = 2
    while next(SOURCE_DIR.glob(f"{candidate.stem}.*"), None) is not None:
        candidate = SOURCE_DIR / f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate


async def _store(upload: UploadFile) -> Path:
    """Stream the upload to disk in chunks so large files stay off the heap."""
    suffix = validate_suffix(upload.filename)
    path = unique_source_path(safe_stem(upload.filename), suffix)
    try:
        with path.open("wb") as handle:
            while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
                handle.write(chunk)
    except OSError as error:
        path.unlink(missing_ok=True)
        raise UnsupportedMediaError(f"Could not save the upload: {error}") from error

    if path.stat().st_size == 0:
        path.unlink(missing_ok=True)
        raise UnsupportedMediaError("The uploaded file is empty")
    return path
