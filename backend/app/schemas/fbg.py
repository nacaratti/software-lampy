from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class FBGCalculationRequest(BaseModel):
    grating_type: Literal["uniform", "chirped", "apodized", "tilted", "lpg"] = "uniform"
    
    # Core attributes
    n_eff: float = Field(1.45, gt=1.0, lt=3.0, description="Core effective refractive index (n_eff_core)")
    length_mm: float = Field(10.0, gt=0.0, lt=100.0, description="Grating length in mm")
    dn: float = Field(1e-4, gt=0.0, lt=0.01, description="Index modulation amplitude")
    
    # Period options
    period_nm: float = Field(535.0, gt=100.0, lt=2000.0, description="Grating period in nm (for FBG)")
    period_um: float = Field(500.0, gt=10.0, lt=2000.0, description="Grating period in um (for LPG)")
    
    # Chirp options
    period_end_nm: float = Field(536.0, gt=100.0, lt=2000.0, description="End grating period in nm")
    chirp_type: Literal["linear", "quadratic"] = "linear"
    
    # Apodization options
    apodization_profile: Literal["gaussian", "raised_cosine", "tanh", "hamming"] = "gaussian"
    profile_strength: float = Field(1.0, ge=0.0, le=1.0, description="Apodization profile strength/width")
    
    # Tilted options
    n_eff_cladding_base: float = Field(1.44, gt=1.0, lt=3.0, description="Base cladding index for cladding modes")
    tilt_angle_deg: float = Field(2.0, ge=0.0, le=45.0, description="Tilt angle in degrees")
    num_cladding_modes: int = Field(10, ge=1, le=50, description="Number of cladding modes to solve")
    
    # LPG options
    n_eff_cladding: float = Field(1.44, gt=1.0, lt=3.0, description="Cladding mode effective index")
    target_mode_order: int = Field(2, ge=1, le=20, description="Target cladding mode order")

    # Simulation range
    wl_start_nm: Optional[float] = Field(None, description="Start wavelength (nm)")
    wl_end_nm: Optional[float] = Field(None, description="End wavelength (nm)")
    num_points: int = Field(1000, ge=100, le=5000)
    num_sections: int = Field(200, ge=10, le=1000)


class FBGCalculationResponse(BaseModel):
    wavelengths_nm: list[float]
    spectrum: list[float]  # Reflectivity or Transmission
    metadata: dict


class PhaseMaskRequest(BaseModel):
    grating_type: Literal["uniform", "chirped", "apodized", "tilted", "lpg"] = "uniform"
    n_eff: float = Field(1.45, gt=1.0, lt=3.0)
    length_mm: float = Field(10.0, gt=0.0, lt=100.0)
    dn: float = Field(1e-4, gt=0.0, lt=0.01)
    period_nm: float = Field(535.0, gt=100.0, lt=2000.0)
    period_end_nm: float = Field(536.0, gt=100.0, lt=2000.0)
    chirp_type: Literal["linear", "quadratic"] = "linear"
    apodization_profile: Literal["gaussian", "raised_cosine", "tanh", "hamming"] = "gaussian"
    profile_strength: float = Field(1.0, ge=0.0, le=1.0)
    lambda_uv_nm: float = Field(248.0, gt=100.0, lt=400.0, description="UV writing laser wavelength (nm)")
    num_sections: int = Field(500, ge=50, le=2000)


class PhaseMaskResponse(BaseModel):
    z_mm: list[float]
    period_pm_nm: list[float]
    dn_profile: list[float]
    kappa_profile: list[float]
    phase_rad: list[float]
    params: dict
