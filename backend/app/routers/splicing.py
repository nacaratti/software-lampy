from fastapi import APIRouter, HTTPException
from backend.app.schemas.splicing import SplicingCalculationRequest, SplicingCalculationResponse
from backend.app.services.encoders import encode_array
from fibersim.solvers.modes.splicing import calculate_splicing_overlap

router = APIRouter(prefix="/api/splicing", tags=["splicing"])

@router.post("/calculate", response_model=SplicingCalculationResponse)
def calculate_splicing(req: SplicingCalculationRequest) -> SplicingCalculationResponse:
    try:
        res = calculate_splicing_overlap(
            core_n1=req.core_n1,
            cladding_n1=req.cladding_n1,
            radius_um1=req.radius_um1,
            core_n2=req.core_n2,
            cladding_n2=req.cladding_n2,
            radius_um2=req.radius_um2,
            wavelength_nm=req.wavelength_nm,
            offset_x_um=req.offset_x_um,
            offset_y_um=req.offset_y_um,
            tilt_x_mrad=req.tilt_x_mrad,
            tilt_y_mrad=req.tilt_y_mrad,
            grid_size=req.grid_size,
        )
        
        return SplicingCalculationResponse(
            coupling_coefficient=res['coupling_coefficient'],
            loss_db=res['loss_db'],
            total_coupling=res['total_coupling'],
            total_loss_db=res['total_loss_db'],
            field_1=encode_array(res['field_1']),
            field_2=encode_array(res['field_2']),
            extent_um=res['extent_um'],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Splicing simulation error: {str(e)}")
