"""ASE power simulation — long-running, returns job_id, push results via WS."""
from __future__ import annotations
from fastapi import APIRouter

from backend.app.schemas.power import PowerASERequest
from backend.app.schemas.jobs import JobCreatedResponse, JobKind, JobStatus
from backend.app.services.runners import run_ase
from backend.app.jobs import manager

router = APIRouter(prefix="/api/power", tags=["power"])


@router.post("/ase", response_model=JobCreatedResponse)
async def post_ase(req: PowerASERequest) -> JobCreatedResponse:
    summary = {
        "length_m": req.length_m,
        "num_pumps": len(req.pumps),
        "num_signals": len(req.signals),
        "ase_enabled": req.ase.enabled,
    }
    job_id = await manager.create_and_run(
        kind=JobKind.ase,
        runner=run_ase,
        request=req,
        request_summary=summary,
    )
    return JobCreatedResponse(job_id=job_id, status=JobStatus.queued)
