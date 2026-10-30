"""HTTP Range aware file responses so the browser can seek inside a video."""

import mimetypes
import re
from collections.abc import Iterator
from pathlib import Path

from starlette.responses import FileResponse, Response, StreamingResponse

from app.config import STREAM_CHUNK_BYTES

RANGE_PATTERN: re.Pattern[str] = re.compile(r"bytes=(\d*)-(\d*)")


def media_response(path: Path, range_header: str | None, as_attachment: bool) -> Response:
    """Serve ``path`` whole, or as a single byte range when the client asks for one."""
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    disposition = "attachment" if as_attachment else "inline"
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'{disposition}; filename="{path.name}"',
    }

    span = _parse_range(range_header, path.stat().st_size)
    if span is None:
        return FileResponse(path, media_type=media_type, headers=headers)

    start, end, total = span
    headers["Content-Range"] = f"bytes {start}-{end}/{total}"
    return StreamingResponse(
        _iter_range(path, start, end),
        status_code=206,
        media_type=media_type,
        headers={**headers, "Content-Length": str(end - start + 1)},
    )


def _parse_range(range_header: str | None, total: int) -> tuple[int, int, int] | None:
    """Resolve a Range header into inclusive start/end offsets."""
    if not range_header or total == 0:
        return None
    match = RANGE_PATTERN.fullmatch(range_header.strip())
    if match is None:
        return None

    raw_start, raw_end = match.groups()
    if raw_start:
        start = int(raw_start)
        end = int(raw_end) if raw_end else total - 1
    elif raw_end:
        start = max(total - int(raw_end), 0)
        end = total - 1
    else:
        return None

    end = min(end, total - 1)
    if start > end:
        return None
    return start, end, total


def _iter_range(path: Path, start: int, end: int) -> Iterator[bytes]:
    """Yield the requested byte range in chunks."""
    remaining = end - start + 1
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining > 0:
            chunk = handle.read(min(STREAM_CHUNK_BYTES, remaining))
            if not chunk:
                return
            remaining -= len(chunk)
            yield chunk
