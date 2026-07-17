from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from backend.app.schemas.common import EncodedArray


class ThermalCalculationRequest(BaseModel):
    # Fiber geometry
    fiber_length_m: float = Field(5.0, gt=0.1, lt=50.0)
    core_radius_um: float = Field(3.0, gt=0.5, lt=20.0)
    clad_radius_um: float = Field(62.5, gt=10.0, lt=500.0)
    coating_radius_um: float = Field(125.0, gt=20.0, lt=1000.0)
    
    # Active ion doping
    N_total: float = Field(4e25, gt=1e24, lt=1e27, description="Yb3+ concentration (ions/m3)")
    tau_ms: float = Field(1.0, gt=0.1, lt=10.0, description="Upper state lifetime (ms)")
    
    # Wavelengths (nm)
    lambda_pump_nm: float = Field(976.0, gt=800.0, lt=1100.0)
    lambda_signal_nm: float = Field(1018.0, gt=950.0, lt=1200.0)
    
    # Overlap factors
    gamma_pump: float = Field(0.8, gt=0.01, lt=1.0)
    gamma_signal: float = Field(0.9, gt=0.01, lt=1.0)
    
    # Pump powers (W)
    P_pump_forward_w: float = Field(10.0, ge=0.0, le=1000.0)
    P_pump_backward_w: float = Field(0.0, ge=0.0, le=1000.0)
    P_signal_seed_w: float = Field(1e-6, gt=0.0, lt=1.0)

    # Pumping type
    pumping: Literal["forward", "backward", "bidirectional"] = "forward"

    # Solver method: analytical (forward-Euler) or RK4 (scipy.solve_ivp)
    method: Literal["analytical", "rk4"] = "analytical"

    # Stimulated emission/absorption cross-sections (m²)
    sigma_abs_pump: float = Field(2.5e-25, gt=0.0, description="Pump absorption cross-section σ_abs_p (m²)")
    sigma_em_pump: float = Field(2.7e-25, gt=0.0, description="Pump emission cross-section σ_em_p (m²)")
    sigma_abs_signal: float = Field(0.4e-25, gt=0.0, description="Signal absorption cross-section σ_abs_s (m²)")
    sigma_em_signal: float = Field(4.5e-25, gt=0.0, description="Signal emission cross-section σ_em_s (m²)")

    # Thermal conductivities (W/m.K)
    k_core: float = Field(1.38, gt=0.1, lt=10.0)
    k_clad: float = Field(1.38, gt=0.1, lt=10.0)
    k_coat: float = Field(0.2, gt=0.01, lt=5.0)

    # Cooling boundary
    h_conv: float = Field(10.0, gt=0.1, lt=1000.0, description="Convective heat transfer (W/m2.K)")
    epsilon: float = Field(0.9, ge=0.0, le=1.0, description="Fiber surface emissivity for radiative cooling")
    T_ambient_celsius: float = Field(25.0, ge=-50.0, le=100.0)
    
    # Grid size
    num_z_points: int = Field(200, ge=50, le=1000)
    num_r_points: int = Field(50, ge=10, le=200)


class ThermalCalculationResponse(BaseModel):
    # Longitudinal coordinate (m)
    z_m: list[float]
    # Power distributions (W)
    pumps_forward: list[float]
    pumps_backward: list[float]
    pumps_total: list[float]
    signals_forward: list[float]
    signals_backward: list[float]
    pump_output_w: list[float]
    # Inversion level
    n2_fraction: list[float]
    
    # Thermal radial coordinates (um)
    r_um: list[float]
    # Temperatures along z
    T_center_celsius: list[float]
    T_surface_celsius: list[float]
    # Encoded 2D Temperature profile array (r_points x z_points) in Kelvin
    T_2d: EncodedArray
    
    # Performance summary
    gain_db: float
    efficiency: float
    output_power_w: float
    T_max_celsius: float

    # Solver that was actually used (rk4 falls back to analytical for backward/bidirectional)
    method_used: str
