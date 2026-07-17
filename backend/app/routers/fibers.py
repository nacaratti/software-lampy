"""Live preview endpoint: refractive index profile n(r)."""
from __future__ import annotations
import math
import numpy as np
from fastapi import APIRouter

from backend.app.errors import run_solver
from backend.app.schemas.fiber import (
    IndexProfilePreviewRequest,
    IndexProfilePreviewResponse,
)
from backend.app.services.fiber_builder import build_fiber

router = APIRouter(prefix="/api/fibers", tags=["fibers"])


@router.post("/preview-index", response_model=IndexProfilePreviewResponse)
def preview_index(req: IndexProfilePreviewRequest) -> IndexProfilePreviewResponse:
    return run_solver(_preview_index_impl, req)


def _preview_index_impl(req: IndexProfilePreviewRequest) -> IndexProfilePreviewResponse:
    fiber = build_fiber(req.fiber)
    wl_m = req.wavelength_nm * 1e-9
    r = np.linspace(0.0, fiber.cladding_radius, req.num_points)
    n = fiber.refractive_index_profile(r, wl_m)
    n_co = float(fiber.refractive_index_profile(0.0, wl_m))
    n_cl = float(fiber.refractive_index_profile(fiber.mode_solving_cladding_radius(), wl_m))

    vn: float | None = None
    if n_co > n_cl:
        na = math.sqrt(max(n_co ** 2 - n_cl ** 2, 0.0))
        vn = (2.0 * math.pi / wl_m) * fiber.core_radius * na

    return IndexProfilePreviewResponse(
        r_um=(r * 1e6).tolist(),
        n=n.tolist(),
        n_core=n_co,
        n_cladding=n_cl,
        v_number=vn,
    )
