"""BPM endpoint — long-running, returns job_id, push results via WS."""
from __future__ import annotations
from fastapi import APIRouter

from backend.app.schemas.bpm import BPMRequest
from backend.app.schemas.jobs import JobCreatedResponse, JobKind, JobStatus
from backend.app.services.runners import run_bpm
from backend.app.jobs import manager

router = APIRouter(prefix="/api/bpm", tags=["bpm"])


@router.post("", response_model=JobCreatedResponse)
async def post_bpm(req: BPMRequest) -> JobCreatedResponse:
    summary = {
        "length_mm": req.length_mm,
        "grid_size": req.grid_size,
        "z_steps": req.z_steps,
        "wavelength_nm": req.wavelength_nm,
    }
    job_id = await manager.create_and_run(
        kind=JobKind.bpm,
        runner=run_bpm,
        request=req,
        request_summary=summary,
    )
    return JobCreatedResponse(job_id=job_id, status=JobStatus.queued)
