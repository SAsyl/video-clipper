"""FastAPI application exposing the download, trim and cut workflow."""

from functools import partial
from pathlib import Path

from fastapi import FastAPI, File, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import SOURCE_DIR, WEB_DIR, ensure_dirs
from app.cutter import cut_clip
from app.downloader import download_source
from app.errors import (
    CutError,
    DownloadError,
    InvalidIdentifierError,
    InvalidTimecodeError,
    JobNotFoundError,
    MediaNotFoundError,
    ProbeError,
    UnsupportedMediaError,
    VideoClipperError,
)
from app.jobs import registry, run_in_background
from app.models import CutRequest, DownloadRequest, JobKind, JobStatus
from app.sources import describe_source
from app.storage import resolve_clip, resolve_source, validate_source_id
from app.streaming import media_response
from app.uploads import ingest_upload

STATUS_BY_ERROR: dict[type[VideoClipperError], int] = {
    InvalidIdentifierError: 400,
    InvalidTimecodeError: 400,
    UnsupportedMediaError: 415,
    JobNotFoundError: 404,
    MediaNotFoundError: 404,
    DownloadError: 502,
    ProbeError: 500,
    CutError: 500,
}

ensure_dirs()

app = FastAPI(title="Video Clipper", version="0.1.0")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.exception_handler(VideoClipperError)
async def handle_app_error(request: Request, error: Exception) -> JSONResponse:
    """Map application errors onto HTTP status codes."""
    status = STATUS_BY_ERROR.get(type(error), 400)
    return JSONResponse(status_code=status, content={"error": str(error)})


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve the single page UI."""
    return FileResponse(WEB_DIR / "index.html")


@app.post("/api/download", response_model=JobStatus)
async def start_download(payload: DownloadRequest) -> JobStatus:
    """Queue a download job for the given link."""
    job = registry.create(JobKind.DOWNLOAD, "Queued")
    run_in_background(
        job.id, partial(download_source, job.id, str(payload.url), payload.max_height)
    )
    return job


@app.post("/api/upload", response_model=JobStatus)
async def upload_source(file: UploadFile = File(...)) -> JobStatus:
    """Import a video the user already has, delivered by drag and drop."""
    source = await ingest_upload(file)
    job = registry.create(JobKind.UPLOAD, "Imported")
    registry.mark_downloaded(job.id, source)
    return registry.get(job.id)


@app.post("/api/cut", response_model=JobStatus)
async def start_cut(payload: CutRequest) -> JobStatus:
    """Queue a cut job for an already downloaded source."""
    validate_source_id(payload.source_id)
    job = registry.create(JobKind.CUT, "Queued")
    run_in_background(job.id, partial(cut_clip, job.id, payload))
    return job


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def job_status(job_id: str) -> JobStatus:
    """Return the current state of a job."""
    return registry.get(job_id)


@app.get("/api/sources/{source_id}", response_model=JobStatus)
async def source_status(source_id: str) -> JobStatus:
    """Describe a previously downloaded source without re-downloading it."""
    path = resolve_source(source_id)
    job = registry.create(JobKind.DOWNLOAD, "Ready")
    registry.mark_downloaded(job.id, describe_source(path))
    return registry.get(job.id)


@app.get("/api/sources", response_model=list[str])
async def list_sources() -> list[str]:
    """List identifiers of sources already present on disk."""
    return sorted(path.stem for path in SOURCE_DIR.iterdir() if path.is_file())


@app.get("/media/source/{name}", include_in_schema=False)
async def stream_source(name: str, range: str | None = Header(default=None)) -> Response:
    """Stream a downloaded source for the preview player."""
    path = resolve_source(Path(name).stem)
    return media_response(path, range, as_attachment=False)


@app.get("/media/clips/{name}", include_in_schema=False)
async def stream_clip(
    name: str,
    download: int = Query(default=0),
    range: str | None = Header(default=None),
) -> Response:
    """Stream or download a generated clip."""
    path = resolve_clip(name)
    return media_response(path, range, as_attachment=bool(download))
