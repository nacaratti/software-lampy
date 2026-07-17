from fastapi import APIRouter, HTTPException
from backend.app.errors import run_solver
from backend.app.schemas.taper import TaperCalculationRequest, TaperCalculationResponse
from fibersim.solvers.taper import solve_taper

router = APIRouter(prefix="/api/taper", tags=["taper"])


@router.post("/calculate", response_model=TaperCalculationResponse)
def calculate_taper(req: TaperCalculationRequest) -> TaperCalculationResponse:
    if req.n_core <= req.n_clad:
        raise HTTPException(status_code=422, detail="n_core must be greater than n_clad")
    if req.clad_radius_um <= req.core_radius_um:
        raise HTTPException(status_code=422, detail="Cladding radius must exceed core radius")

    return run_solver(_calculate_taper_impl, req)


def _calculate_taper_impl(req: TaperCalculationRequest) -> TaperCalculationResponse:
        res = solve_taper(
            core_radius_um=req.core_radius_um,
            clad_radius_um=req.clad_radius_um,
            n_core=req.n_core,
            n_clad=req.n_clad,
            taper_ratio=req.taper_ratio,
            L_taper_mm=req.L_taper_mm,
            L_waist_mm=req.L_waist_mm,
            taper_shape=req.taper_shape,
            lambda_nm=req.lambda_nm,
            num_z=req.num_z,
        )
        return TaperCalculationResponse(
            z_mm             = res['z_mm'].tolist(),
            r_core_um        = res['r_core_um'].tolist(),
            r_clad_um        = res['r_clad_um'].tolist(),
            V_core           = res['V_core'].tolist(),
            V_clad           = res['V_clad'].tolist(),
            mfd_w2_um        = res['mfd_w2_um'].tolist(),
            mfd_weff_um      = res['mfd_weff_um'].tolist(),
            mfd_hwhm_um      = res['mfd_hwhm_um'].tolist(),
            A_eff_um2        = res['A_eff_um2'].tolist(),
            taper_angle_mrad = res['taper_angle_mrad'].tolist(),
            omega_c_mrad     = res['omega_c_mrad'].tolist(),
            eta              = res['eta'].tolist(),
            z_beat_mm        = res['z_beat_mm'].tolist(),
            is_lp11          = res['is_lp11'].tolist(),
            in_cladding_mode = res['in_cladding_mode'].tolist(),
            V_input          = res['V_input'],
            V_waist          = res['V_waist'],
            V_clad_input     = res['V_clad_input'],
            V_clad_waist     = res['V_clad_waist'],
            mfd_input_um     = res['mfd_input_um'],
            mfd_waist_um     = res['mfd_waist_um'],
            max_eta          = res['max_eta'],
            is_adiabatic     = res['is_adiabatic'],
            transmission     = res['transmission'],
            transmission_db  = res['transmission_db'],
            L_total_mm       = res['L_total_mm'],
            lp11_filtered    = res['lp11_filtered'],
        )
