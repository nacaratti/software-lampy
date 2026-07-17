from __future__ import annotations
from pydantic import BaseModel, Field


class CouplerCalculationRequest(BaseModel):
    # Fiber geometry (symmetric coupler — same fiber for both arms)
    core_radius_um: float = Field(4.0, gt=0.5, lt=50.0, description="Core radius (μm)")
    n_core: float = Field(1.4508, gt=1.0, lt=3.0, description="Core refractive index")
    n_clad: float = Field(1.45, gt=1.0, lt=3.0, description="Cladding refractive index")

    # Coupling geometry
    fiber_separation_um: float = Field(
        10.0, gt=0.0, lt=500.0,
        description="Surface-to-surface gap between the two fiber cores (μm)"
    )
    coupling_length_mm: float = Field(
        10.0, gt=0.01, lt=500.0,
        description="Interaction (coupling) region length (mm)"
    )

    # Optical excitation
    lambda_center_nm: float = Field(1550.0, gt=600.0, lt=3000.0, description="Center wavelength (nm)")
    P1_in_w: float = Field(1.0, ge=0.0, lt=1e6, description="Input power port 1 (W)")
    P2_in_w: float = Field(0.0, ge=0.0, lt=1e6, description="Input power port 2 (W)")

    # Asymmetric coupler: phase mismatch Δβ/2 (rad/m)
    delta_rad_per_m: float = Field(
        0.0, ge=0.0, lt=1e6,
        description="Phase mismatch δ = Δβ/2 (rad/m). Zero for symmetric (identical) coupler."
    )

    # Wavelength sweep for spectral response
    lambda_min_nm: float = Field(1450.0, gt=600.0, lt=3000.0)
    lambda_max_nm: float = Field(1650.0, gt=600.0, lt=3000.0)

    # Grid sizes
    num_z: int = Field(500, ge=50, le=2000, description="Longitudinal grid points")
    num_lambda: int = Field(200, ge=20, le=1000, description="Wavelength sweep points")


class CouplerCalculationResponse(BaseModel):
    # Longitudinal power evolution
    z_mm: list[float]
    P1_z: list[float]
    P2_z: list[float]

    # Spectral response
    lambda_nm: list[float]
    P1_lambda: list[float]
    P2_lambda: list[float]
    kappa_lambda: list[float]
    splitting_ratio_lambda: list[float]

    # Summary metrics
    kappa_c: float          # coupling coefficient at center wavelength (1/m)
    coupling_length_mm: float   # full coupling length L_c = π/(2κ) (mm)
    splitting_ratio: float      # P2_out / (P1_out + P2_out) at z=L
    throughput_db: float        # through port power relative to input (dB)
    cross_db: float             # cross port power relative to input (dB)
    P1_out: float
    P2_out: float
