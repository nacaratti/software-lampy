"""Power Ramp / Nonlinear Effects Explorer schemas.

Sweeps pump power for a single fiber (seed -> pump -> WDM -> fiber_active ->
power_meter, built internally) and reports the same diagnostic fields the
System Builder engine already computes at each fiber_active node (SRS/SBS
thresholds, photodarkening, Tm/Er ESA-upconversion, TMI risk) as a function
of power, plus an explicit "not applicable" reason when a fiber structurally
can't exhibit a given effect (e.g. TMI on a single-mode fiber) rather than
silently omitting it.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .common import EncodedArray
from .system import ActiveFiberParams


class PowerRampRequest(BaseModel):
    fiber: ActiveFiberParams

    pump_wavelength_nm: float = Field(976.0, gt=200.0, lt=20000.0)
    seed_wavelength_nm: float = Field(1064.0, gt=200.0, lt=20000.0)
    seed_power_w: float = Field(0.01, gt=0.0, le=1000.0)

    pump_power_min_w: float = Field(0.1, gt=0.0, le=1e6)
    pump_power_max_w: float = Field(50.0, gt=0.0, le=1e6)
    num_steps: int = Field(20, ge=5, le=60)


class EffectSeries(BaseModel):
    """One nonlinear-effect trace across the power sweep.

    `applicable=False` means this fiber structurally cannot exhibit the
    effect (e.g. TMI on a single-mode fiber, ESA on a non-Tm/Er ion) — values
    are then empty and `reason` explains why, instead of silently vanishing.
    """
    key: str
    label: str
    applicable: bool
    reason: str | None = None
    values: list[float | None] = Field(default_factory=list)
    threshold: float | None = None  # value of `values` that marks "at threshold" (1.0 for pre-normalized fractions)
    unit: str = ""


class PowerRampResponse(BaseModel):
    pump_power_w: list[float]
    peak_signal_power_w: list[float]
    gain_db: list[float | None]
    effects: list[EffectSeries]
    warnings_by_step: list[list[str]]

    # SRS/SBS: the fiber-geometry-dependent thresholds themselves (constant
    # across the sweep — they don't depend on pump power) so the frontend can
    # plot peak_signal_power_w directly against them in native Watts.
    srs_threshold_w: float | None = None
    sbs_threshold_w: float | None = None

    # TMI: rigorous per-step M^2 (ISO 11146) of an LP01+LP11 mode mixture
    # blended by a coupling fraction derived from tmi_risk_fraction (see
    # power_ramp_runner.py), plus the two pure-mode near-field images so the
    # frontend can render an interactive "watch the coupling happen"
    # cross-section by blending them client-side at any swept power step.
    # All None/empty when TMI isn't applicable to this fiber.
    tmi_m2x: list[float] = Field(default_factory=list)
    tmi_m2y: list[float] = Field(default_factory=list)
    tmi_coupling_fraction: list[float] = Field(default_factory=list)
    tmi_lp01_image: EncodedArray | None = None
    tmi_lp11_image: EncodedArray | None = None
    tmi_image_x_um: list[float] = Field(default_factory=list)
    tmi_image_y_um: list[float] = Field(default_factory=list)
