from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from .fiber import FiberConfig
from .common import EncodedArray


class InitialFieldConfig(BaseModel):
    kind: Literal["gaussian", "fundamental_mode"] = "gaussian"
    waist_um: float = Field(5.0, gt=0.1, le=200.0)
    x_offset_um: float = Field(0.0, ge=-200.0, le=200.0)
    y_offset_um: float = Field(0.0, ge=-200.0, le=200.0)
    tilt_x_mrad: float = Field(0.0, ge=-100.0, le=100.0)
    tilt_y_mrad: float = Field(0.0, ge=-100.0, le=100.0)


class BPMRequest(BaseModel):
    fiber: FiberConfig
    wavelength_nm: float = Field(1550.0, gt=200.0, lt=20000.0)
    length_mm: float = Field(10.0, gt=0.0, le=10000.0)
    initial_field: InitialFieldConfig
    grid_size: int = Field(64, ge=32, le=192)
    z_steps: int = Field(200, ge=20, le=2000)
    grid_width_factor: float = Field(3.0, gt=0.5, le=10.0)
    save_z_slices: int = Field(60, ge=10, le=400,
                               description="Number of z-slices kept in the response")


class BPMResponse(BaseModel):
    z_mm: list[float]
    x_um: list[float]
    y_um: list[float]
    intensity_slices: EncodedArray  # shape (Nz_saved, Nx, Ny) float32
    power_vs_z: list[float]
    z_step_indices: list[int]
