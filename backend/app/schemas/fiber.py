from __future__ import annotations
from typing import Literal, Union, Annotated
from pydantic import BaseModel, Field


MaterialKind = Literal["silica", "germanosilicate", "phosphate", "constant"]
IonKind = Literal["yb", "er", "tm"]


class MaterialConfig(BaseModel):
    """Material specification.

    - silica/phosphate use Sellmeier dispersion
    - germanosilicate requires `geo2_fraction` in [0, 1]
    - constant uses a fixed refractive index value
    """
    kind: MaterialKind
    geo2_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    index: float | None = Field(default=None, ge=1.0, le=3.0,
                                description="Used only when kind == 'constant'")


class StepIndexConfig(BaseModel):
    kind: Literal["step"] = "step"
    core_radius_um: float = Field(..., gt=0.0, le=500.0)
    cladding_radius_um: float = Field(..., gt=0.0, le=2000.0)
    core_material: MaterialConfig
    cladding_material: MaterialConfig


class GradedIndexConfig(BaseModel):
    kind: Literal["graded"] = "graded"
    core_radius_um: float = Field(..., gt=0.0, le=500.0)
    cladding_radius_um: float = Field(..., gt=0.0, le=2000.0)
    core_material: MaterialConfig
    cladding_material: MaterialConfig
    alpha: float = Field(2.0, gt=0.0, le=20.0)


class DoubleCladConfig(BaseModel):
    kind: Literal["double_clad"] = "double_clad"
    core_radius_um: float = Field(..., gt=0.0, le=500.0)
    inner_cladding_radius_um: float = Field(..., gt=0.0, le=2000.0)
    outer_cladding_radius_um: float = Field(..., gt=0.0, le=2000.0)
    core_material: MaterialConfig
    inner_cladding_material: MaterialConfig
    outer_cladding_material: MaterialConfig


FiberConfig = Annotated[
    Union[StepIndexConfig, GradedIndexConfig, DoubleCladConfig],
    Field(discriminator="kind"),
]


class ActiveFiberConfig(BaseModel):
    geometry: FiberConfig
    ion: IonKind = "yb"
    dopant_density_per_m3: float = Field(..., gt=0.0)
    doping_profile: Literal["uniform", "gaussian"] = "uniform"


class IndexProfilePreviewRequest(BaseModel):
    fiber: FiberConfig
    wavelength_nm: float = Field(1550.0, gt=200.0, lt=20000.0)
    num_points: int = Field(400, ge=50, le=4000)


class IndexProfilePreviewResponse(BaseModel):
    r_um: list[float]
    n: list[float]
    n_core: float
    n_cladding: float
    v_number: float | None = None


class IonCrossSectionRequest(BaseModel):
    ion: IonKind = "yb"
    wavelengths_nm: list[float] = Field(..., min_length=1, max_length=20)


class IonCrossSectionResponse(BaseModel):
    sigma_abs_m2: list[float]
    sigma_em_m2: list[float]
