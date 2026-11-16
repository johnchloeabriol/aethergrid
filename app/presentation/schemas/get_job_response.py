from datetime import datetime

from pydantic import BaseModel


class GetJobResponse(BaseModel):
    """
    Response returned when retrieving a job.

    Deliberately excludes `command`. As of ADR 0028,
    command IS settable through the public API, but reading
    it back through this response would let any caller
    browsing jobs by ID inspect a command they didn't
    necessarily set. ADR 0020 scoped command *reads* to only
    the worker currently assigned that exact job, via
    GET /workers/{worker_id}. This schema intentionally
    does not widen that.
    """

    id: str
    status: str
    cpu_cores: int
    memory_mib: int
    vram_mib: int
    exit_code: int | None
    max_retries: int
    retry_count: int
    """
    The retry budget and how much of it is spent (ADR 0102). A
    caller can tell from these two why POST /jobs/{id}/retry left
    a FAILED job unchanged: retry_count has reached max_retries.
    """
    submitted_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
