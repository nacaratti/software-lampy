"""Power Ramp endpoint — sweeps pump power over a single fiber, returns
job_id, pushes results via WS (each step re-solves the fiber, so it's a
moderate numerical job, run async like ASE/BPM/GNLSE/system)."""
from __future__ import annotations
from fastapi import APIRouter

from backend.app.schemas.power_ramp import PowerRampRequest
from backend.app.schemas.jobs import JobCreatedResponse, JobKind, JobStatus
from backend.app.services.power_ramp_runner import run_power_ramp
from backend.app.jobs import manager

router = APIRouter(prefix="/api/power-ramp", tags=["power-ramp"])


@router.post("", response_model=JobCreatedResponse)
async def post_power_ramp(req: PowerRampRequest) -> JobCreatedResponse:
    summary = {
        "ion": req.fiber.ion,
        "pump_power_min_w": req.pump_power_min_w,
        "pump_power_max_w": req.pump_power_max_w,
        "num_steps": req.num_steps,
    }
    job_id = await manager.create_and_run(
        kind=JobKind.power_ramp,
        runner=run_power_ramp,
        request=req,
        request_summary=summary,
    )
    return JobCreatedResponse(job_id=job_id, status=JobStatus.queued)
