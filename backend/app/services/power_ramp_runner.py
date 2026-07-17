"""Power Ramp runner: sweeps pump power over a canonical single-fiber graph
(seed -> pump -> WDM -> fiber_active -> power_meter) and reads off the same
nonlinear-effect diagnostics the System Builder engine already computes at
each step, via `fibersim.system.simulate_system` — no new physics here, only
orchestration, so results are guaranteed consistent with what a user would
see building the same fiber by hand in the System Builder.

Scope note (same framing as `nonlinear_thresholds.py`/`tmi_threshold.py`):
each step re-solves a single fiber in isolation with fixed co-propagating
pump/seed, not a full cavity or multi-stage system — a fast "effects
explorer" for one fiber design, not a validated re-simulation of an
arbitrary system.

Each effect gets the analysis appropriate to its own physics rather than a
single normalized number: SRS/SBS are compared against their own Watts
thresholds (constant across the sweep — they don't depend on pump power),
photodarkening is reported in its native dB unit, TMI gets a real ISO 11146
M^2 estimate (and a synthesizable near-field cross-section) built from an
LP01/LP11 mode mixture blended by the risk fraction, and ESA/upconversion is
an activity indicator (Tm cross-relaxation yield, or Er peak inversion)
rather than a Watts threshold, since the engine doesn't expose one for it.
"""
from __future__ import annotations

from typing import Callable, Optional

import numpy as np

from fibersim.core.fiber import DoubleCladFiber, FiberGeometry, StepIndexFiber
from fibersim.system import SystemEdge, SystemGraph, SystemNode, simulate_system
from fibersim.system.beam import mix_fields_and_measure_m2, solve_lp01_lp11_fields
from fibersim.system.graph import GraphValidationError

from backend.app.schemas.power_ramp import EffectSeries, PowerRampRequest, PowerRampResponse
from backend.app.services.encoders import encode_array

_PHOTODARKENING_WARNING_DB = 1.0  # mirrors fibersim.system.engine._PHOTODARKENING_WARNING_DB
_TM_PUMP_CUTOFF_NM = 900.0  # mirrors fibersim.system.engine._TM_CROSS_RELAXATION_PUMP_CUTOFF_M
_OUTER_CLADDING_INDEX_DEFAULT = 1.375  # mirrors fibersim.system.engine._OUTER_CLADDING_INDEX_DEFAULT

# Heuristic saturating map from TMI risk fraction to an LP11 power-coupling
# fraction: f = TMI_COUPLING_CAP * risk/(1+risk). f=0 at risk=0, f=cap/2 at
# risk=1 (at threshold), f -> cap asymptotically at high risk. TMI is a
# dynamic, time-varying instability, not a one-way full conversion, so even
# well past threshold the time-averaged mode content saturates well below
# 100% LP11 — this is a documented approximation for visualization, not a
# validated coupled-mode dynamics simulation (see tmi_threshold.py).
_TMI_COUPLING_CAP = 0.5


def _build_fiber_geometry(fiber_params) -> FiberGeometry:
    core_r = fiber_params.core_radius_um * 1e-6
    clad_r = fiber_params.clad_radius_um * 1e-6
    n_core = fiber_params.n_core
    n_clad = fiber_params.n_clad
    if fiber_params.inner_cladding_radius_um is not None:
        return DoubleCladFiber(
            core_r, fiber_params.inner_cladding_radius_um * 1e-6, clad_r,
            n_core, n_clad, _OUTER_CLADDING_INDEX_DEFAULT,
        )
    return StepIndexFiber(core_r, clad_r, n_core, n_clad)


def _build_ramp_graph(req: PowerRampRequest, pump_power_w: float) -> SystemGraph:
    fiber_params = req.fiber.model_dump()
    nodes = [
        SystemNode(id="seed", kind="seed", label="seed",
                   params={"wavelength_nm": req.seed_wavelength_nm, "power_w": req.seed_power_w}),
        SystemNode(id="pump", kind="pump_source", label="pump",
                   params={"wavelength_nm": req.pump_wavelength_nm, "power_w": pump_power_w}),
        SystemNode(id="wdm", kind="coupler_wdm", label="wdm", params={}),
        SystemNode(id="fiber", kind="fiber_active", label="fiber", params=fiber_params),
        SystemNode(id="out", kind="power_meter", label="out", params={}),
    ]
    edges = [
        SystemEdge(id="e0", source="seed", target="wdm"),
        SystemEdge(id="e1", source="pump", target="wdm", target_port="pump"),
        SystemEdge(id="e2", source="wdm", target="fiber"),
        SystemEdge(id="e3", source="fiber", target="out"),
    ]
    return SystemGraph(nodes, edges)


def run_power_ramp(
    req: PowerRampRequest,
    progress_callback: Optional[Callable[[float], Optional[bool]]] = None,
) -> PowerRampResponse:
    pump_powers = np.linspace(req.pump_power_min_w, req.pump_power_max_w, req.num_steps)

    peak_signal_power_w: list[float] = []
    gain_db: list[Optional[float]] = []
    warnings_by_step: list[list[str]] = []

    srs_threshold_w: Optional[float] = None
    sbs_threshold_w: Optional[float] = None
    srs_applicable: Optional[bool] = None
    pd_values: list[Optional[float]] = []
    tmi_values: list[Optional[float]] = []
    tmi_applicable: Optional[bool] = None
    esa_values: list[Optional[float]] = []

    pd_applicable = req.fiber.ion == "yb"
    esa_applicable = (req.fiber.ion == "tm" and req.pump_wavelength_nm < _TM_PUMP_CUTOFF_NM) or req.fiber.ion == "er"

    for i, pump_power in enumerate(pump_powers):
        graph = _build_ramp_graph(req, float(pump_power))
        try:
            result = simulate_system(graph)
        except GraphValidationError as exc:
            raise ValueError("; ".join(exc.issues)) from exc

        nr = result.nodes["fiber"]
        warnings_by_step.append(list(result.warnings))
        peak_signal_power_w.append(float(nr.get("signal_out_w", 0.0)))
        gain_db.append(nr.get("gain_db"))

        srs_th = nr.get("srs_threshold_w")
        sbs_th = nr.get("sbs_threshold_w")
        if srs_th is not None:
            srs_threshold_w = srs_th
            sbs_threshold_w = sbs_th
            srs_applicable = True
        elif srs_applicable is None:
            srs_applicable = False

        pd_extra = nr.get("photodarkening_extra_loss_db_saturated")
        pd_values.append(pd_extra if pd_extra is not None else None)

        tmi_frac = nr.get("tmi_risk_fraction")
        if tmi_frac is not None:
            tmi_values.append(tmi_frac)
            tmi_applicable = True
        else:
            tmi_values.append(None)
            if tmi_applicable is None:
                tmi_applicable = False

        tm_yield = nr.get("tm_cross_relaxation_yield")
        er_n2_peak = None
        if req.fiber.ion == "er":
            n2_fraction = nr.get("n2_fraction")
            if n2_fraction:
                er_n2_peak = float(max(n2_fraction))
        if tm_yield is not None:
            esa_values.append(tm_yield)
        elif er_n2_peak is not None:
            esa_values.append(er_n2_peak)
        else:
            esa_values.append(None)

        if progress_callback is not None:
            progress_callback((i + 1) / len(pump_powers))

    srs_reason = None if srs_applicable else (
        "No guided fundamental mode at the signal wavelength for this fiber geometry "
        "(effective area undefined) — SRS/SBS thresholds can't be estimated."
    )

    # TMI: real ISO 11146 M^2 vs power, from an LP01/LP11 mode mixture
    # blended by a coupling fraction derived from the risk fraction, plus a
    # pair of pure-mode images for the frontend to blend interactively.
    tmi_m2x: list[float] = []
    tmi_m2y: list[float] = []
    tmi_coupling_fraction: list[float] = []
    tmi_lp01_image = None
    tmi_lp11_image = None
    tmi_image_x_um: list[float] = []
    tmi_image_y_um: list[float] = []
    tmi_reason = None

    if tmi_applicable:
        geometry = _build_fiber_geometry(req.fiber)
        signal_wl_m = req.seed_wavelength_nm * 1e-9
        half_width = 4.0 * geometry.core_radius
        x, y, psi01, psi11 = solve_lp01_lp11_fields(geometry, signal_wl_m, grid_n=64, half_width=half_width)
        for risk in tmi_values:
            f = _TMI_COUPLING_CAP * risk / (1.0 + risk) if risk is not None else 0.0
            m2x, m2y, _ = mix_fields_and_measure_m2(x, y, psi01, psi11, f, signal_wl_m)
            tmi_m2x.append(m2x)
            tmi_m2y.append(m2y)
            tmi_coupling_fraction.append(f)
        i01 = (psi01 ** 2).astype(np.float32)
        i01 = i01 / max(float(np.max(i01)), 1e-30)
        tmi_lp01_image = encode_array(i01)
        if psi11 is not None:
            i11 = (psi11 ** 2).astype(np.float32)
            i11 = i11 / max(float(np.max(i11)), 1e-30)
            tmi_lp11_image = encode_array(i11)
        tmi_image_x_um = (x * 1e6).tolist()
        tmi_image_y_um = (y * 1e6).tolist()
    else:
        if req.fiber.ion != "yb":
            tmi_reason = "TMI diagnostic is only implemented for Yb3+ fibers in this simulator."
        else:
            tmi_reason = (
                "Fiber is single-mode at this wavelength (doesn't guide a distinct LP11) — "
                "structurally not TMI-prone in the usual sense."
            )

    esa_label = "Nonlinear effect"
    esa_unit = ""
    esa_reason = None
    if req.fiber.ion == "tm":
        if esa_applicable:
            esa_label = "Tm cross-relaxation yield"
            esa_unit = "×"
        else:
            esa_reason = (
                f"Tm cross-relaxation requires pumping below {_TM_PUMP_CUTOFF_NM:.0f} nm "
                f"(current pump: {req.pump_wavelength_nm:.0f} nm)."
            )
    elif req.fiber.ion == "er":
        esa_label = "Er upconversion activity (peak N2 fraction)"
        esa_unit = ""
    else:
        esa_reason = "ESA/upconversion diagnostics are only implemented for Tm3+ and Er3+ fibers."

    effects = [
        EffectSeries(
            key="srs", label="SRS threshold fraction", applicable=bool(srs_applicable),
            reason=srs_reason,
            values=[p / srs_threshold_w for p in peak_signal_power_w] if srs_applicable and srs_threshold_w else [],
            threshold=1.0 if srs_applicable else None, unit="",
        ),
        EffectSeries(
            key="sbs", label="SBS threshold fraction", applicable=bool(srs_applicable),
            reason=srs_reason,
            values=[p / sbs_threshold_w for p in peak_signal_power_w] if srs_applicable and sbs_threshold_w else [],
            threshold=1.0 if srs_applicable else None, unit="",
        ),
        EffectSeries(
            key="photodarkening", label="Photodarkening extra loss", applicable=pd_applicable,
            reason=None if pd_applicable else "Photodarkening is only modeled for Yb3+ fibers.",
            values=pd_values if pd_applicable else [],
            threshold=_PHOTODARKENING_WARNING_DB if pd_applicable else None, unit="dB",
        ),
        EffectSeries(
            key="tmi", label="TMI risk fraction", applicable=bool(tmi_applicable),
            reason=tmi_reason, values=tmi_values if tmi_applicable else [],
            threshold=1.0 if tmi_applicable else None, unit="",
        ),
        EffectSeries(
            key="esa_upconversion", label=esa_label, applicable=esa_applicable,
            reason=esa_reason, values=esa_values if esa_applicable else [],
            threshold=None, unit=esa_unit,
        ),
    ]

    return PowerRampResponse(
        pump_power_w=pump_powers.tolist(),
        peak_signal_power_w=peak_signal_power_w,
        gain_db=gain_db,
        effects=effects,
        warnings_by_step=warnings_by_step,
        srs_threshold_w=srs_threshold_w,
        sbs_threshold_w=sbs_threshold_w,
        tmi_m2x=tmi_m2x,
        tmi_m2y=tmi_m2y,
        tmi_coupling_fraction=tmi_coupling_fraction,
        tmi_lp01_image=tmi_lp01_image,
        tmi_lp11_image=tmi_lp11_image,
        tmi_image_x_um=tmi_image_x_um,
        tmi_image_y_um=tmi_image_y_um,
    )
