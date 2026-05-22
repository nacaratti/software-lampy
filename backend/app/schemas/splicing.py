from __future__ import annotations
from pydantic import BaseModel, Field
from backend.app.schemas.common import EncodedArray


class SplicingCalculationRequest(BaseModel):
    # Fiber 1 (Source)
    core_n1: float = Field(1.45, gt=1.0, lt=2.0)
    cladding_n1: float = Field(1.444, gt=1.0, lt=2.0)
    radius_um1: float = Field(5.0, gt=0.1, lt=100.0)
    
    # Fiber 2 (Destination)
    core_n2: float = Field(1.45, gt=1.0, lt=2.0)
    cladding_n2: float = Field(1.444, gt=1.0, lt=2.0)
    radius_um2: float = Field(5.0, gt=0.1, lt=100.0)
    
    # Wavelength
    wavelength_nm: float = Field(1550.0, gt=300.0, lt=3000.0)
    
    # Misalignment
    offset_x_um: float = Field(0.0, ge=-20.0, le=20.0)
    offset_y_um: float = Field(0.0, ge=-20.0, le=20.0)
    tilt_x_mrad: float = Field(0.0, ge=-50.0, le=50.0)
    tilt_y_mrad: float = Field(0.0, ge=-50.0, le=50.0)
    
    # Computation Grid
    grid_size: int = Field(128, ge=32, le=256)


class SplicingCalculationResponse(BaseModel):
    coupling_coefficient: float
    loss_db: float
    total_coupling: float
    total_loss_db: float
    field_1: EncodedArray
    field_2: EncodedArray
    extent_um: float
