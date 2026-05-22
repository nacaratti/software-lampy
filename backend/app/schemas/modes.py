from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from .fiber import FiberConfig
from .common import EncodedArray


class ModeAnalyticalRequest(BaseModel):
    fiber: FiberConfig
    wavelength_nm: float = Field(1550.0, gt=200.0, lt=20000.0)
    grid_size: int = Field(128, ge=32, le=512)
    max_plot_radius_factor: float = Field(2.0, gt=0.5, le=10.0,
                                          description="Plot radius as multiple of core_radius")


class ModeFDRequest(BaseModel):
    fiber: FiberConfig
    wavelength_nm: float = Field(1550.0, gt=200.0, lt=20000.0)
    l: int = Field(0, ge=0, le=10)
    grid_points: int = Field(400, ge=50, le=2000)
    plot_grid_size: int = Field(128, ge=32, le=512)
    max_plot_radius_factor: float = Field(2.0, gt=0.5, le=10.0)


class Mode2DRequest(BaseModel):
    fiber: FiberConfig
    wavelength_nm: float = Field(1550.0, gt=200.0, lt=20000.0)
    grid_size: int = Field(80, ge=32, le=200)
    grid_width_factor: float = Field(3.0, gt=0.5, le=10.0)
    num_modes: int = Field(6, ge=1, le=20)


class ModeResult(BaseModel):
    l: int
    m: int
    n_eff: float
    beta: float
    u: float | None = None
    w: float | None = None
    a_eff_um2: float | None = None
    power_core_pct: float | None = None
    intensity_2d: EncodedArray
    extent_um: float


class ModesResponse(BaseModel):
    method: Literal["analytical", "fd", "2d"]
    wavelength_nm: float
    n_core: float
    n_cladding: float
    v_number: float | None = None
    num_modes: int
    modes: list[ModeResult]
