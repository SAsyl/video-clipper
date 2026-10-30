"""Request, response and job payload schemas."""

from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, model_validator


class JobKind(StrEnum):
    DOWNLOAD = "download"
    UPLOAD = "upload"
    CUT = "cut"


class JobState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class CutMode(StrEnum):
    PRECISE = "precise"
    FAST = "fast"


class DownloadRequest(BaseModel):
    url: HttpUrl
    max_height: int = Field(default=1080, ge=240, le=2160)


class CutRequest(BaseModel):
    source_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    mode: CutMode = CutMode.PRECISE

    @model_validator(mode="after")
    def check_range(self) -> "CutRequest":
        """Reject an empty or inverted selection before queueing work."""
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class SourceInfo(BaseModel):
    id: str
    title: str
    duration_ms: int
    width: int
    height: int
    fps: float
    size_bytes: int
    media_url: str


class ClipInfo(BaseModel):
    name: str
    start_ms: int
    end_ms: int
    duration_ms: int
    size_bytes: int
    media_url: str
    download_url: str


class JobStatus(BaseModel):
    id: str
    kind: JobKind
    state: JobState
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str = ""
    source: SourceInfo | None = None
    clip: ClipInfo | None = None
    error: str | None = None
