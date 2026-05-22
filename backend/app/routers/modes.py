"""Mode solver endpoints — synchronous (analytical+FD are fast enough)."""
from __future__ import annotations
import logging
import traceback
from fastapi import APIRouter, HTTPException

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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/modes", tags=["modes"])


def _wrap(fn, req):
    try:
        return fn(req)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Mode solver failed: %s", fn.__name__)
        detail = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        raise HTTPException(status_code=400, detail=detail)


@router.post("/analytical", response_model=ModesResponse)
def post_modes_analytical(req: ModeAnalyticalRequest) -> ModesResponse:
    return _wrap(run_modes_analytical, req)


@router.post("/fd", response_model=ModesResponse)
def post_modes_fd(req: ModeFDRequest) -> ModesResponse:
    return _wrap(run_modes_fd, req)


@router.post("/2d", response_model=ModesResponse)
def post_modes_2d(req: Mode2DRequest) -> ModesResponse:
    return _wrap(run_modes_2d, req)
