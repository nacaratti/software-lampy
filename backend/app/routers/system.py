"""System Builder: graph validation, async simulation job, and project persistence."""
from __future__ import annotations
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.errors import run_solver
from backend.app.jobs import manager
from backend.app.models.system import LaserSystem
from backend.app.schemas.jobs import JobCreatedResponse, JobKind, JobStatus
from backend.app.schemas.system import (
    SystemCreate,
    SystemOut,
    SystemSimulateRequest,
    SystemSummary,
    SystemUpdate,
    SystemValidateResponse,
)
from backend.app.services.system_runner import run_system_simulation, validate_system

router = APIRouter(tags=["system"])


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

@router.post("/api/system/validate", response_model=SystemValidateResponse)
def post_system_validate(req: SystemSimulateRequest) -> SystemValidateResponse:
    issues = run_solver(validate_system, req)
    return SystemValidateResponse(valid=not issues, issues=issues)


@router.post("/api/system/simulate", response_model=JobCreatedResponse)
async def post_system_simulate(req: SystemSimulateRequest) -> JobCreatedResponse:
    summary = {"num_nodes": len(req.nodes), "num_edges": len(req.edges)}
    job_id = await manager.create_and_run(
        kind=JobKind.system,
        runner=run_system_simulation,
        request=req,
        request_summary=summary,
    )
    return JobCreatedResponse(job_id=job_id, status=JobStatus.queued)


# ---------------------------------------------------------------------------
# Saved systems (multi-project persistence)
# ---------------------------------------------------------------------------

def _row_to_out(s: LaserSystem) -> SystemOut:
    return SystemOut(
        id=s.id,
        name=s.name,
        description=s.description,
        graph=json.loads(s.graph) if isinstance(s.graph, str) else s.graph,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _row_to_summary(s: LaserSystem) -> SystemSummary:
    graph = json.loads(s.graph) if isinstance(s.graph, str) else s.graph
    node_count = len(graph.get("nodes", [])) if isinstance(graph, dict) else 0
    return SystemSummary(
        id=s.id,
        name=s.name,
        description=s.description,
        node_count=node_count,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("/api/systems", response_model=list[SystemSummary])
def list_systems(db: Session = Depends(get_db)):
    rows = db.query(LaserSystem).order_by(LaserSystem.updated_at.desc()).all()
    return [_row_to_summary(r) for r in rows]


@router.post("/api/systems", response_model=SystemOut, status_code=201)
def create_system(body: SystemCreate, db: Session = Depends(get_db)):
    row = LaserSystem(
        name=body.name,
        description=body.description,
        graph=json.dumps(body.graph),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_out(row)


@router.get("/api/systems/{system_id}", response_model=SystemOut)
def get_system(system_id: str, db: Session = Depends(get_db)):
    row = db.get(LaserSystem, system_id)
    if not row:
        raise HTTPException(status_code=404, detail="System not found")
    return _row_to_out(row)


@router.put("/api/systems/{system_id}", response_model=SystemOut)
def update_system(system_id: str, body: SystemUpdate, db: Session = Depends(get_db)):
    row = db.get(LaserSystem, system_id)
    if not row:
        raise HTTPException(status_code=404, detail="System not found")
    if body.name is not None:
        row.name = body.name
    if body.description is not None:
        row.description = body.description
    if body.graph is not None:
        row.graph = json.dumps(body.graph)
    db.commit()
    db.refresh(row)
    return _row_to_out(row)


@router.delete("/api/systems/{system_id}", status_code=204)
def delete_system(system_id: str, db: Session = Depends(get_db)):
    row = db.get(LaserSystem, system_id)
    if not row:
        raise HTTPException(status_code=404, detail="System not found")
    db.delete(row)
    db.commit()


@router.post("/api/systems/{system_id}/duplicate", response_model=SystemOut, status_code=201)
def duplicate_system(system_id: str, db: Session = Depends(get_db)):
    row = db.get(LaserSystem, system_id)
    if not row:
        raise HTTPException(status_code=404, detail="System not found")
    copy = LaserSystem(
        name=f"{row.name} (copy)",
        description=row.description,
        graph=row.graph,
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return _row_to_out(copy)
