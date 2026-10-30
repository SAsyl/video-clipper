"""Filesystem lookups for downloaded sources and generated clips."""

import re
from pathlib import Path

from app.config import CLIP_DIR, SAFE_ID_PATTERN, SOURCE_DIR
from app.errors import InvalidIdentifierError, MediaNotFoundError

SAFE_ID: re.Pattern[str] = re.compile(SAFE_ID_PATTERN)
SAFE_CLIP_NAME: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_\-]{1,96}\.mp4$")


def validate_source_id(source_id: str) -> str:
    """Reject identifiers that could escape the media directory."""
    if SAFE_ID.match(source_id) is None:
        raise InvalidIdentifierError(f"Unsafe source id {source_id!r}")
    return source_id


def resolve_source(source_id: str) -> Path:
    """Return the on-disk path of a downloaded source."""
    validate_source_id(source_id)
    matches = sorted(SOURCE_DIR.glob(f"{source_id}.*"))
    if not matches:
        raise MediaNotFoundError(f"No downloaded source named {source_id!r}")
    return matches[0]


def resolve_clip(name: str) -> Path:
    """Return the on-disk path of a generated clip."""
    if SAFE_CLIP_NAME.match(name) is None:
        raise InvalidIdentifierError(f"Unsafe clip name {name!r}")
    path = CLIP_DIR / name
    if not path.is_file():
        raise MediaNotFoundError(f"No clip named {name!r}")
    return path
