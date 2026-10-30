"""Static application configuration and filesystem layout."""

from pathlib import Path

BASE_DIR: Path = Path(__file__).resolve().parent.parent
WEB_DIR: Path = BASE_DIR / "web"
MEDIA_DIR: Path = BASE_DIR / "media"
SOURCE_DIR: Path = MEDIA_DIR / "source"
CLIP_DIR: Path = MEDIA_DIR / "clips"

FFMPEG_BIN: str = "ffmpeg"
FFPROBE_BIN: str = "ffprobe"

# Chunk size used when streaming media byte ranges to the browser.
STREAM_CHUNK_BYTES: int = 512 * 1024

# Chunk size used when writing an uploaded file to disk.
UPLOAD_CHUNK_BYTES: int = 1024 * 1024

# Containers accepted by drag and drop import.
ALLOWED_UPLOAD_SUFFIXES: frozenset[str] = frozenset(
    {".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi", ".ts", ".flv", ".mpg", ".mpeg", ".wmv"}
)

# Longest identifier derived from an uploaded filename, before uniqueness suffixes.
MAX_UPLOAD_STEM_LENGTH: int = 48

# Identifiers are reused as filenames, so keep them strictly alphanumeric.
SAFE_ID_PATTERN: str = r"^[A-Za-z0-9_\-]{1,64}$"


def ensure_dirs() -> None:
    """Create the media directories the app writes into."""
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    CLIP_DIR.mkdir(parents=True, exist_ok=True)
