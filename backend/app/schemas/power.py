from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from .fiber import ActiveFiberConfig
from .common import EncodedArray


class PumpConfig(BaseModel):
    name: str = "Pump"
    wavelength_nm: float = Field(976.0, gt=200.0, lt=20000.0)
    power_forward_w: float = Field(0.0, ge=0.0)
    power_backward_w: float = Field(0.0, ge=0.0)
    overlap: float = Field(0.85, gt=0.0, le=1.0)
    loss_db_per_m: float = Field(0.0, ge=0.0)


class SignalConfig(BaseModel):
    name: str = "Signal"
    wavelength_nm: float = Field(1064.0, gt=200.0, lt=20000.0)
    power_forward_w: float = Field(0.0, ge=0.0)
    power_backward_w: float = Field(0.0, ge=0.0)
    overlap: float = Field(0.85, gt=0.0, le=1.0)
    loss_db_per_m: float = Field(0.0, ge=0.0)
    reflectivity_input: float = Field(0.0, ge=0.0, le=1.0)
    reflectivity_output: float = Field(0.0, ge=0.0, le=1.0)


class ASEConfig(BaseModel):
    enabled: bool = True
    wavelength_min_nm: float = Field(1020.0, gt=200.0)
    wavelength_max_nm: float = Field(1100.0, lt=20000.0)
    num_channels: int = Field(40, ge=4, le=200)
    overlap: float = Field(0.85, gt=0.0, le=1.0)
    loss_db_per_m: float = Field(0.0, ge=0.0)


class PowerASERequest(BaseModel):
    active_fiber: ActiveFiberConfig
    length_m: float = Field(..., gt=0.0, le=500.0)
    pumps: list[PumpConfig] = Field(default_factory=list, max_length=4)
    signals: list[SignalConfig] = Field(default_factory=list, max_length=4)
    ase: ASEConfig
    num_z_points: int = Field(150, ge=30, le=2000)
    max_iterations: int = Field(100, ge=10, le=1000)
    tolerance: float = Field(1e-5, gt=0.0, lt=1.0)
    relaxation_factor: float = Field(0.6, gt=0.0, le=1.0)


class PowerASEResponse(BaseModel):
    z_m: list[float]
    pump_wavelengths_nm: list[float]
    signal_wavelengths_nm: list[float]
    ase_wavelengths_nm: list[float]
    pumps_forward: EncodedArray  # shape (num_pumps, num_z)
    pumps_backward: EncodedArray
    signals_forward: EncodedArray
    signals_backward: EncodedArray
    ase_forward: EncodedArray
    ase_backward: EncodedArray
    n2_fraction: EncodedArray  # shape (num_z,)
    summary: dict[str, float]
