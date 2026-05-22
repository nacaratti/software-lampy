"""In-memory async job manager with WebSocket-friendly event streams."""
from __future__ import annotations
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import anyio

from backend.app.config import settings
from backend.app.schemas.jobs import JobInfo, JobKind, JobStatus


@dataclass
class JobState:
    job_id: str
    kind: JobKind
    status: JobStatus = JobStatus.queued
    progress: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    request_summary: Optional[dict[str, Any]] = None
    cancel_flag: bool = False
    # Each subscribed websocket gets its own queue
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    last_progress_emitted: float = 0.0

    def to_info(self) -> JobInfo:
        return JobInfo(
            job_id=self.job_id,
            kind=self.kind,
            status=self.status,
            progress=self.progress,
            created_at=self.created_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            error_message=self.error_message,
            request=self.request_summary,
        )


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def get(self, job_id: str) -> Optional[JobState]:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[JobInfo]:
        # Most-recent first
        items = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return [j.to_info() for j in items]

    async def subscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        # Wait up to 500ms for the job to register (handles race with POST)
        for _ in range(10):
            if job_id in self._jobs:
                break
            await asyncio.sleep(0.05)
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        job.subscribers.append(queue)
        # Send the current snapshot so the client immediately sees recent state
        await queue.put({"type": "status", "status": job.status.value})
        if job.progress > 0:
            await queue.put({"type": "progress", "value": job.progress})
        if job.status == JobStatus.completed and job.result is not None:
            await queue.put({"type": "result", "data": job.result})
        elif job.status == JobStatus.error:
            await queue.put({"type": "error", "message": job.error_message or "unknown"})
        elif job.status == JobStatus.cancelled:
            await queue.put({"type": "cancelled"})

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        job = self._jobs.get(job_id)
        if job and queue in job.subscribers:
            job.subscribers.remove(queue)

    def _broadcast(self, job: JobState, message: dict[str, Any]) -> None:
        for q in list(job.subscribers):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                pass

    async def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.status in (JobStatus.completed, JobStatus.error, JobStatus.cancelled):
            return False
        job.cancel_flag = True
        return True

    def _make_progress_callback(self, job: JobState):
        """Build the throttled, thread-safe progress callback the solver will call."""
        loop = self._loop
        min_dt = settings.progress_min_interval_seconds
        state = {"last_emit": 0.0}

        def callback(value: float):
            if job.cancel_flag:
                return False
            now = time.monotonic()
            if now - state["last_emit"] < min_dt and value < 1.0:
                return None
            state["last_emit"] = now
            job.progress = float(value)
            if loop is not None:
                loop.call_soon_threadsafe(
                    self._broadcast, job, {"type": "progress", "value": float(value)}
                )
            return None

        return callback

    async def create_and_run(
        self,
        kind: JobKind,
        runner: Callable[..., Any],
        request: Any,
        request_summary: Optional[dict[str, Any]] = None,
    ) -> str:
        job_id = uuid.uuid4().hex
        job = JobState(job_id=job_id, kind=kind, request_summary=request_summary)
        self._jobs[job_id] = job
        # Fire the worker task; do not await completion here
        asyncio.create_task(self._run(job, runner, request))
        # Schedule TTL cleanup
        asyncio.create_task(self._gc_after_ttl(job_id))
        return job_id

    async def _run(self, job: JobState, runner: Callable[..., Any], request: Any) -> None:
        async with self._semaphore:
            job.status = JobStatus.running
            job.started_at = datetime.now(timezone.utc)
            self._broadcast(job, {"type": "status", "status": JobStatus.running.value})

            progress_cb = self._make_progress_callback(job)
            try:
                # Run the CPU-heavy solver in a worker thread so the event loop stays free
                result = await anyio.to_thread.run_sync(
                    lambda: runner(request, progress_callback=progress_cb)
                )
                # result is a Pydantic BaseModel
                payload = result.model_dump(mode="json")
                job.result = payload
                job.progress = 1.0
                job.status = JobStatus.completed
                job.finished_at = datetime.now(timezone.utc)
                self._broadcast(job, {"type": "result", "data": payload})
                self._broadcast(job, {"type": "status", "status": JobStatus.completed.value})
            except Exception as exc:  # noqa: BLE001
                from fibersim.solvers.power.ase import JobCancelled
                if isinstance(exc, JobCancelled):
                    job.status = JobStatus.cancelled
                    job.finished_at = datetime.now(timezone.utc)
                    self._broadcast(job, {"type": "cancelled"})
                    self._broadcast(job, {"type": "status", "status": JobStatus.cancelled.value})
                else:
                    job.status = JobStatus.error
                    job.error_message = f"{type(exc).__name__}: {exc}"
                    job.finished_at = datetime.now(timezone.utc)
                    self._broadcast(job, {"type": "error", "message": job.error_message})
                    self._broadcast(job, {"type": "status", "status": JobStatus.error.value})

    async def _gc_after_ttl(self, job_id: str) -> None:
        await asyncio.sleep(settings.job_ttl_seconds)
        job = self._jobs.pop(job_id, None)
        if job:
            for q in job.subscribers:
                try:
                    q.put_nowait({"type": "expired"})
                except Exception:
                    pass


# Global instance
manager = JobManager()
