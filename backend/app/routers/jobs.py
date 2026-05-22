"""Job lifecycle endpoints: list, get, cancel."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException

from backend.app.schemas.jobs import JobInfo, JobListResponse
from backend.app.jobs import manager

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
def list_jobs() -> JobListResponse:
    return JobListResponse(jobs=manager.list_jobs())


@router.get("/{job_id}", response_model=JobInfo)
def get_job(job_id: str) -> JobInfo:
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_info()


@router.get("/{job_id}/result")
def get_job_result(job_id: str):
    """Fallback: clients that miss the WS message can fetch the full result here."""
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.result is None:
        raise HTTPException(status_code=409, detail=f"Job state: {job.status.value}, no result yet")
    return job.result


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    ok = await manager.cancel(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found or already finished")
    return {"job_id": job_id, "status": "cancelling"}
