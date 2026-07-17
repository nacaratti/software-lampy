from fastapi import APIRouter, HTTPException
from backend.app.errors import run_solver
from backend.app.schemas.coupler import CouplerCalculationRequest, CouplerCalculationResponse
from fibersim.solvers.coupler import solve_coupler

router = APIRouter(prefix="/api/coupler", tags=["coupler"])


@router.post("/calculate", response_model=CouplerCalculationResponse)
def calculate_coupler(req: CouplerCalculationRequest) -> CouplerCalculationResponse:
    if req.n_core <= req.n_clad:
        raise HTTPException(status_code=422, detail="Core index must be greater than cladding index")
    if req.lambda_min_nm >= req.lambda_max_nm:
        raise HTTPException(status_code=422, detail="lambda_min_nm must be less than lambda_max_nm")

    return run_solver(_calculate_coupler_impl, req)


def _calculate_coupler_impl(req: CouplerCalculationRequest) -> CouplerCalculationResponse:
        res = solve_coupler(
            core_radius_um=req.core_radius_um,
            n_core=req.n_core,
            n_clad=req.n_clad,
            fiber_separation_um=req.fiber_separation_um,
            coupling_length_mm=req.coupling_length_mm,
            lambda_center_nm=req.lambda_center_nm,
            P1_in_w=req.P1_in_w,
            P2_in_w=req.P2_in_w,
            delta_rad_per_m=req.delta_rad_per_m,
            num_z=req.num_z,
            lambda_min_nm=req.lambda_min_nm,
            lambda_max_nm=req.lambda_max_nm,
            num_lambda=req.num_lambda,
        )
        return CouplerCalculationResponse(
            z_mm=res['z_mm'].tolist(),
            P1_z=res['P1_z'].tolist(),
            P2_z=res['P2_z'].tolist(),
            lambda_nm=res['lambda_nm'].tolist(),
            P1_lambda=res['P1_lambda'].tolist(),
            P2_lambda=res['P2_lambda'].tolist(),
            kappa_lambda=res['kappa_lambda'].tolist(),
            splitting_ratio_lambda=res['splitting_ratio_lambda'].tolist(),
            kappa_c=res['kappa_c'],
            coupling_length_mm=res['coupling_length_mm'],
            splitting_ratio=res['splitting_ratio'],
            throughput_db=res['throughput_db'],
            cross_db=res['cross_db'],
            P1_out=res['P1_out'],
            P2_out=res['P2_out'],
        )
