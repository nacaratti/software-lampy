"""Adapters that turn API schemas into fibersim domain objects."""
from __future__ import annotations
from fibersim.core.materials import Material, Silica, Germanosilicate, Phosphate
from fibersim.core.fiber import (
    FiberGeometry,
    StepIndexFiber,
    GradedIndexFiber,
    DoubleCladFiber,
    ActiveFiber,
)
from fibersim.core.ions import ActiveIon

from backend.app.schemas.fiber import (
    MaterialConfig,
    StepIndexConfig,
    GradedIndexConfig,
    DoubleCladConfig,
    ActiveFiberConfig,
)


def build_material(cfg: MaterialConfig) -> Material | float:
    if cfg.kind == "silica":
        return Silica()
    if cfg.kind == "germanosilicate":
        frac = cfg.geo2_fraction if cfg.geo2_fraction is not None else 0.03
        return Germanosilicate(frac)
    if cfg.kind == "phosphate":
        return Phosphate()
    if cfg.kind == "constant":
        if cfg.index is None:
            raise ValueError("constant material requires 'index'")
        return float(cfg.index)
    raise ValueError(f"Unknown material kind: {cfg.kind}")


def build_fiber(cfg) -> FiberGeometry:
    if isinstance(cfg, StepIndexConfig):
        return StepIndexFiber(
            core_radius=cfg.core_radius_um * 1e-6,
            cladding_radius=cfg.cladding_radius_um * 1e-6,
            core_material=build_material(cfg.core_material),
            cladding_material=build_material(cfg.cladding_material),
        )
    if isinstance(cfg, GradedIndexConfig):
        return GradedIndexFiber(
            core_radius=cfg.core_radius_um * 1e-6,
            cladding_radius=cfg.cladding_radius_um * 1e-6,
            n_peak=build_material(cfg.core_material),
            n_cladding=build_material(cfg.cladding_material),
            alpha=cfg.alpha,
        )
    if isinstance(cfg, DoubleCladConfig):
        return DoubleCladFiber(
            core_radius=cfg.core_radius_um * 1e-6,
            inner_cladding_radius=cfg.inner_cladding_radius_um * 1e-6,
            outer_cladding_radius=cfg.outer_cladding_radius_um * 1e-6,
            core_material=build_material(cfg.core_material),
            inner_cladding_material=build_material(cfg.inner_cladding_material),
            outer_cladding_material=build_material(cfg.outer_cladding_material),
        )
    raise ValueError(f"Unknown fiber config type: {type(cfg)}")


def build_active_ion(kind: str) -> ActiveIon:
    if kind == "yb":
        return ActiveIon.create_yb3()
    if kind == "er":
        return ActiveIon.create_er3()
    if kind == "tm":
        return ActiveIon.create_tm3()
    raise ValueError(f"Unknown ion kind: {kind}")


def build_active_fiber(cfg: ActiveFiberConfig) -> ActiveFiber:
    geometry = build_fiber(cfg.geometry)
    ion = build_active_ion(cfg.ion)
    return ActiveFiber(
        geometry=geometry,
        ion=ion,
        dopant_density_core=cfg.dopant_density_per_m3,
        dopant_profile_type=cfg.doping_profile,
    )
