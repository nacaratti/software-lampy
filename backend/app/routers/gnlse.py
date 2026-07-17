"""GNLSE endpoint — long-running pulse propagation, returns job_id, push results via WS."""
from __future__ import annotations
from fastapi import APIRouter

from backend.app.schemas.gnlse import GNLSERequest
from backend.app.schemas.jobs import JobCreatedResponse, JobKind, JobStatus
from backend.app.services.runners import run_gnlse
from backend.app.jobs import manager

router = APIRouter(prefix="/api/gnlse", tags=["gnlse"])


@router.post("", response_model=JobCreatedResponse)
async def post_gnlse(req: GNLSERequest) -> JobCreatedResponse:
    summary = {
        "length_mm": req.length_mm,
        "duration_fs": req.duration_fs,
        "peak_power_w": req.peak_power_w,
        "enable_gain": req.enable_gain,
    }
    job_id = await manager.create_and_run(
        kind=JobKind.gnlse,
        runner=run_gnlse,
        request=req,
        request_summary=summary,
    )
    return JobCreatedResponse(job_id=job_id, status=JobStatus.queued)
