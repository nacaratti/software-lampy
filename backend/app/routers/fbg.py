from fastapi import APIRouter, HTTPException
from backend.app.schemas.fbg import (
    FBGCalculationRequest, FBGCalculationResponse,
    PhaseMaskRequest, PhaseMaskResponse,
)
from fibersim.solvers.fbg.solver import (
    calculate_uniform_fbg,
    calculate_chirped_fbg,
    calculate_apodized_fbg,
    calculate_tilted_fbg,
    calculate_lpg,
    calculate_phase_mask,
)

router = APIRouter(prefix="/api/fbg", tags=["fbg"])

@router.post("/calculate", response_model=FBGCalculationResponse)
def calculate_fbg(req: FBGCalculationRequest) -> FBGCalculationResponse:
    try:
        if req.grating_type == "uniform":
            wl_start = req.wl_start_nm if req.wl_start_nm is not None else (2 * req.n_eff * req.period_nm * 1e-9) * 1e9 - 5.0
            wl_end = req.wl_end_nm if req.wl_end_nm is not None else (2 * req.n_eff * req.period_nm * 1e-9) * 1e9 + 5.0
            wls, spec, meta = calculate_uniform_fbg(
                n_eff=req.n_eff,
                period_nm=req.period_nm,
                length_mm=req.length_mm,
                dn=req.dn,
                wl_start_nm=wl_start,
                wl_end_nm=wl_end,
                num_points=req.num_points,
            )
        elif req.grating_type == "chirped":
            wls, spec, meta = calculate_chirped_fbg(
                n_eff=req.n_eff,
                period_start_nm=req.period_nm,
                period_end_nm=req.period_end_nm,
                length_mm=req.length_mm,
                dn=req.dn,
                chirp_type=req.chirp_type,
                wl_start_nm=req.wl_start_nm,
                wl_end_nm=req.wl_end_nm,
                num_points=req.num_points,
                num_sections=req.num_sections,
            )
        elif req.grating_type == "apodized":
            wls, spec, meta = calculate_apodized_fbg(
                n_eff=req.n_eff,
                period_nm=req.period_nm,
                length_mm=req.length_mm,
                dn_peak=req.dn,
                apodization_profile=req.apodization_profile,
                profile_strength=req.profile_strength,
                wl_start_nm=req.wl_start_nm,
                wl_end_nm=req.wl_end_nm,
                num_points=req.num_points,
                num_sections=req.num_sections,
            )
        elif req.grating_type == "tilted":
            wls, spec, meta = calculate_tilted_fbg(
                n_eff_core=req.n_eff,
                n_eff_cladding_base=req.n_eff_cladding_base,
                period_nm=req.period_nm,
                length_mm=req.length_mm,
                dn=req.dn,
                tilt_angle_deg=req.tilt_angle_deg,
                num_cladding_modes=req.num_cladding_modes,
                wl_start_nm=req.wl_start_nm,
                wl_end_nm=req.wl_end_nm,
                num_points=req.num_points,
            )
        elif req.grating_type == "lpg":
            wls, spec, meta = calculate_lpg(
                n_eff_core=req.n_eff,
                n_eff_cladding=req.n_eff_cladding,
                period_um=req.period_um,
                length_mm=req.length_mm,
                dn=req.dn,
                target_mode_order=req.target_mode_order,
                wl_start_nm=req.wl_start_nm,
                wl_end_nm=req.wl_end_nm,
                num_points=req.num_points,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported grating type: {req.grating_type}")
        
        return FBGCalculationResponse(
            wavelengths_nm=wls.tolist(),
            spectrum=spec.tolist(),
            metadata=meta,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FBG simulation error: {str(e)}")


@router.post("/phase-mask", response_model=PhaseMaskResponse)
def get_phase_mask(req: PhaseMaskRequest) -> PhaseMaskResponse:
    try:
        result = calculate_phase_mask(
            grating_type=req.grating_type,
            n_eff=req.n_eff,
            length_mm=req.length_mm,
            dn=req.dn,
            period_nm=req.period_nm,
            period_end_nm=req.period_end_nm,
            chirp_type=req.chirp_type,
            apodization_profile=req.apodization_profile,
            profile_strength=req.profile_strength,
            lambda_uv_nm=req.lambda_uv_nm,
            num_sections=req.num_sections,
        )
        return PhaseMaskResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Phase mask error: {str(e)}")
