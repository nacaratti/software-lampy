from __future__ import annotations
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    cancelled = "cancelled"
    error = "error"


class JobKind(str, Enum):
    ase = "ase"
    bpm = "bpm"


class JobInfo(BaseModel):
    job_id: str
    kind: JobKind
    status: JobStatus
    progress: float = Field(0.0, ge=0.0, le=1.0)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    request: dict[str, Any] | None = None


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobListResponse(BaseModel):
    jobs: list[JobInfo]


# WebSocket message envelopes

class WsStatusEvent(BaseModel):
    type: Literal["status"] = "status"
    status: JobStatus


class WsProgressEvent(BaseModel):
    type: Literal["progress"] = "progress"
    value: float = Field(..., ge=0.0, le=1.0)


class WsResultEvent(BaseModel):
    type: Literal["result"] = "result"
    data: dict[str, Any]


class WsErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class WsCancelledEvent(BaseModel):
    type: Literal["cancelled"] = "cancelled"
