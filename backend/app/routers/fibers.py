"""Live preview endpoints: refractive index profile n(r), ion cross-sections."""
from __future__ import annotations
import math
import numpy as np
from fastapi import APIRouter

from backend.app.errors import run_solver
from backend.app.schemas.fiber import (
    IndexProfilePreviewRequest,
    IndexProfilePreviewResponse,
    IonCrossSectionRequest,
    IonCrossSectionResponse,
)
from backend.app.services.fiber_builder import build_fiber
from fibersim.core.ions import ActiveIon

router = APIRouter(prefix="/api/fibers", tags=["fibers"])

_ION_FACTORIES = {"yb": ActiveIon.create_yb3, "er": ActiveIon.create_er3, "tm": ActiveIon.create_tm3}


@router.post("/preview-index", response_model=IndexProfilePreviewResponse)
def preview_index(req: IndexProfilePreviewRequest) -> IndexProfilePreviewResponse:
    return run_solver(_preview_index_impl, req)


@router.post("/ion-cross-sections", response_model=IonCrossSectionResponse)
def ion_cross_sections(req: IonCrossSectionRequest) -> IonCrossSectionResponse:
    return run_solver(_ion_cross_sections_impl, req)


def _ion_cross_sections_impl(req: IonCrossSectionRequest) -> IonCrossSectionResponse:
    """Single source of truth for ion absorption/emission cross-sections — the
    same McCumber-derived (Yb/Er) / measured-band (Tm) model used by the
    System Builder and Power & ASE solver, so pages like the Thermal
    Simulator that let users override these values get a physically
    consistent recommendation instead of an independently-hand-tuned table."""
    ion = _ION_FACTORIES[req.ion]()
    sig_abs, sig_em = [], []
    for wl_nm in req.wavelengths_nm:
        a, e = ion.get_cross_sections(wl_nm * 1e-9)
        sig_abs.append(a)
        sig_em.append(e)
    return IonCrossSectionResponse(sigma_abs_m2=sig_abs, sigma_em_m2=sig_em)


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
