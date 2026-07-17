"""Mode solver endpoints — synchronous (analytical+FD are fast enough)."""
from __future__ import annotations
from fastapi import APIRouter

from backend.app.errors import heavy_solvers, run_solver
from backend.app.schemas.modes import (
    ModeAnalyticalRequest,
    ModeFDRequest,
    Mode2DRequest,
    ModesResponse,
)
from backend.app.services.runners import (
    run_modes_analytical,
    run_modes_fd,
    run_modes_2d,
)

router = APIRouter(prefix="/api/modes", tags=["modes"])


@router.post("/analytical", response_model=ModesResponse)
def post_modes_analytical(req: ModeAnalyticalRequest) -> ModesResponse:
    return run_solver(run_modes_analytical, req)


@router.post("/fd", response_model=ModesResponse)
def post_modes_fd(req: ModeFDRequest) -> ModesResponse:
    return run_solver(run_modes_fd, req)


@router.post("/2d", response_model=ModesResponse)
def post_modes_2d(req: Mode2DRequest) -> ModesResponse:
    with heavy_solvers.slot("2D mode-solving"):
        return run_solver(run_modes_2d, req)
