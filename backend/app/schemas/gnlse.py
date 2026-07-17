from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from .common import EncodedArray


class GNLSERequest(BaseModel):
    # Pulse
    pulse_shape: Literal["gaussian", "sech2"] = "sech2"
    wavelength_nm: float = Field(1550.0, gt=200.0, lt=20000.0)
    peak_power_w: float = Field(1000.0, gt=0.0, le=1e9)
    duration_fs: float = Field(100.0, gt=0.1, le=1e6, description="FWHM pulse duration")
    time_window_ps: float = Field(20.0, gt=0.01, le=1e4)
    num_points: int = Field(2048, ge=128, le=8192)

    # Fiber
    length_mm: float = Field(10.0, gt=0.0, le=1e6)
    gamma_per_w_per_km: float = Field(1.3, ge=0.0, le=1e5, description="Nonlinear coefficient γ")
    beta2_ps2_per_km: float = Field(-20.0, ge=-1e6, le=1e6)
    beta3_ps3_per_km: float = Field(0.0, ge=-1e6, le=1e6)
    loss_db_per_m: float = Field(0.0, ge=0.0, le=1000.0)
    self_steepening: bool = True
    raman: bool = True

    # Optional saturable gain (pulsed amplifier) — see fibersim.solvers.propagation.gnlse
    # for why gain is frozen (energy-saturated) for the whole single pass.
    enable_gain: bool = False
    small_signal_gain_db_per_m: float = Field(0.0, ge=0.0, le=1000.0)
    saturation_energy_nj: float | None = Field(None, gt=0.0, le=1e6)
    gain_bandwidth_nm: float | None = Field(None, gt=0.0, le=1000.0)

    z_steps: int = Field(200, ge=20, le=2000)
    save_z_slices: int = Field(60, ge=10, le=400,
                               description="Number of z-slices kept in the response")


class GNLSEResponse(BaseModel):
    z_mm: list[float]
    t_ps: list[float]
    wavelength_nm: list[float]
    temporal_power_slices: EncodedArray  # shape (Nz_saved, N), W
    spectral_power_slices: EncodedArray  # shape (Nz_saved, N), a.u.
    input_temporal_power_w: list[float]
    output_temporal_power_w: list[float]
    input_spectral_power: list[float]
    output_spectral_power: list[float]
    input_energy_nj: float
    output_energy_nj: float
    saturated_gain_db_per_m: float | None = None
