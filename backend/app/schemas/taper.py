from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class TaperCalculationRequest(BaseModel):
    # Fiber geometry
    core_radius_um: float = Field(4.0, gt=0.1, lt=100.0)
    clad_radius_um: float = Field(62.5, gt=5.0, lt=2000.0)
    n_core: float = Field(1.4681, gt=1.0, lt=3.0)
    n_clad: float = Field(1.4629, gt=1.0, lt=3.0)

    # Taper geometry
    taper_ratio: float = Field(
        0.1, gt=0.0, le=1.0,
        description="r_waist / r₀ — taper down factor (0.1 = 10 × diameter reduction)"
    )
    L_taper_mm: float = Field(30.0, gt=0.01, lt=2000.0, description="Length of each taper arm (mm)")
    L_waist_mm: float = Field(5.0, ge=0.0, lt=500.0, description="Flat waist length (mm)")
    taper_shape: Literal["cosine", "linear", "exponential"] = "cosine"

    # Optical
    lambda_nm: float = Field(1550.0, gt=200.0, lt=5000.0)

    # Grid
    num_z: int = Field(800, ge=100, le=3000)


class TaperCalculationResponse(BaseModel):
    # z-dependent arrays
    z_mm:             list[float]
    r_core_um:        list[float]
    r_clad_um:        list[float]
    V_core:           list[float]
    V_clad:           list[float]
    mfd_w2_um:        list[float]   # Petermann I / 2nd moment
    mfd_weff_um:      list[float]   # Petermann II / A_eff
    mfd_hwhm_um:      list[float]   # HWHM
    A_eff_um2:        list[float]
    taper_angle_mrad: list[float]
    omega_c_mrad:     list[float]
    eta:              list[float]
    z_beat_mm:        list[float]
    is_lp11:          list[bool]
    in_cladding_mode: list[bool]

    # Scalars
    V_input:          float
    V_waist:          float
    V_clad_input:     float
    V_clad_waist:     float
    mfd_input_um:     float
    mfd_waist_um:     float
    max_eta:          float
    is_adiabatic:     bool
    transmission:     float
    transmission_db:  float
    L_total_mm:       float
    lp11_filtered:    bool
