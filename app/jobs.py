"""Thread safe in-memory registry of background jobs."""

import threading
import uuid
from collections.abc import Callable

from app.errors import JobNotFoundError
from app.models import ClipInfo, JobKind, JobState, JobStatus, SourceInfo


class JobRegistry:
    """Tracks the state of download and cut jobs running in worker threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobStatus] = {}

    def create(self, kind: JobKind, message: str) -> JobStatus:
        job = JobStatus(id=uuid.uuid4().hex, kind=kind, state=JobState.PENDING, message=message)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> JobStatus:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(f"Unknown job id {job_id!r}")
        return job

    def mark_running(self, job_id: str, message: str) -> None:
        self._mutate(job_id, state=JobState.RUNNING, message=message)

    def update_progress(self, job_id: str, progress: float, message: str) -> None:
        clamped = min(max(progress, 0.0), 1.0)
        self._mutate(job_id, state=JobState.RUNNING, progress=clamped, message=message)

    def mark_downloaded(self, job_id: str, source: SourceInfo) -> None:
        self._mutate(job_id, state=JobState.DONE, progress=1.0, message="Ready", source=source)

    def mark_cut(self, job_id: str, clip: ClipInfo) -> None:
        self._mutate(job_id, state=JobState.DONE, progress=1.0, message="Clip ready", clip=clip)

    def mark_failed(self, job_id: str, error: str) -> None:
        self._mutate(job_id, state=JobState.FAILED, message="Failed", error=error)

    def _mutate(self, job_id: str, **changes: object) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"Unknown job id {job_id!r}")
            self._jobs[job_id] = job.model_copy(update=changes)


registry: JobRegistry = JobRegistry()


def run_in_background(job_id: str, work: Callable[[], None]) -> None:
    """Run ``work`` in a daemon thread, recording any failure on the job."""

    def runner() -> None:
        try:
            work()
        except Exception as error:  # Surface every failure through the job state.
            registry.mark_failed(job_id, str(error))

    threading.Thread(target=runner, name=f"job-{job_id}", daemon=True).start()
