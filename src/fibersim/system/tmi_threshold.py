"""Transverse Mode Instability (TMI) risk estimator.

TMI is a dynamic, thermally-induced coupling between the fundamental
(LP01) and a higher-order (typically LP11) guided mode in high-power fiber
amplifiers: quantum-defect heat deposited via the beating interference
pattern between LP01 and LP11 creates a periodic (long-period-grating-like)
temperature -> refractive-index modulation along the fiber. Above a
threshold power this thermal grating becomes strong enough to continuously
scatter power between the two modes in real time, degrading beam quality
(Smith & Smith, "Mode instability in high power fiber amplifiers",
Opt. Express 2011; Jauregui, Limpert & Tünnermann review, Nature Photonics
2020).

A first-principles threshold power (in Watts) depends on details this
simulator doesn't model self-consistently — the LP01/LP11 beat-note heat
source, gain-saturation dynamics, and the thermo-optic response time versus
the quantum-defect heat modulation depth — so reproducing the exact Smith &
Smith coupled-mode threshold derivation isn't attempted here. Instead, this
module gives a physically-grounded *risk indicator*: how large the
thermally-induced index perturbation (built on system/thermal_lensing.py)
is relative to the fiber's own intrinsic LP01-LP11 effective-index
separation. TMI's core physical requirement is that the thermal grating's
index modulation be strong enough to phase-match/couple the two modes — so
as this ratio approaches 1, the design has the qualitative ingredients for
TMI. This is "how close is this design to the TMI regime", not a validated
Watts threshold.
"""
from __future__ import annotations

from typing import Callable, Optional

import numpy as np

from fibersim.core.fiber import FiberGeometry
from fibersim.solvers.modes.fd import solve_modes_fd
from fibersim.system.thermal_lensing import ROOM_TEMPERATURE_K, SILICA_DN_DT_PER_K


def lp01_lp11_effective_index_gap(
    geometry: FiberGeometry, wavelength_m: float, *, grid_points: int = 400,
) -> Optional[float]:
    """n_eff(LP01) - n_eff(LP11) on the unperturbed (cold) geometry. Returns
    None if the fiber doesn't guide a distinct LP11 at this wavelength (e.g.
    a deeply single-mode fiber, which structurally can't support the
    LP01/LP11 beat note TMI relies on)."""
    lp01_modes = solve_modes_fd(geometry, wavelength_m, l=0, grid_points=grid_points)
    lp11_modes = solve_modes_fd(geometry, wavelength_m, l=1, grid_points=grid_points)
    if not lp01_modes or not lp11_modes:
        return None
    gap = lp01_modes[0].n_eff - lp11_modes[0].n_eff
    return gap if gap > 0.0 else None


def tmi_risk_fraction(delta_n_thermal: float, delta_n_lp01_lp11_gap: float) -> float:
    """Ratio of the thermally-induced index perturbation to the intrinsic
    LP01-LP11 effective-index separation. Approaching/exceeding 1 indicates
    the fiber has the ingredients for TMI mode coupling (see module
    docstring) — a qualitative risk indicator, not a Watts threshold."""
    if delta_n_lp01_lp11_gap <= 0.0:
        return float("inf") if delta_n_thermal > 0.0 else 0.0
    return abs(delta_n_thermal) / delta_n_lp01_lp11_gap


def estimate_tmi_risk(
    geometry: FiberGeometry,
    wavelength_m: float,
    temperature_profile_k: Callable[[np.ndarray], np.ndarray],
    *,
    dn_dt_per_k: float = SILICA_DN_DT_PER_K,
    t_ref_k: float = ROOM_TEMPERATURE_K,
    grid_points: int = 400,
) -> Optional[dict]:
    """Estimates the TMI risk fraction for a fiber under a given radial
    on-axis heating. Returns None if the fiber is deeply single-mode (no
    distinct LP11 to couple to — structurally not TMI-prone in the usual
    sense)."""
    gap = lp01_lp11_effective_index_gap(geometry, wavelength_m, grid_points=grid_points)
    if gap is None:
        return None
    t_core = float(np.asarray(temperature_profile_k(0.0)))
    delta_n_thermal = dn_dt_per_k * (t_core - t_ref_k)
    return {
        "delta_n_thermal": delta_n_thermal,
        "delta_n_lp01_lp11_gap": gap,
        "tmi_risk_fraction": tmi_risk_fraction(delta_n_thermal, gap),
    }
