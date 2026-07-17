"""Coupled thermal lensing: refractive-index perturbation from fiber core
heating, and its effect on the guided fundamental mode.

High-power fiber lasers develop a radial temperature gradient from
quantum-defect heating (hottest on-axis, cooling outward through
cladding/coating — see solvers/thermal/cavity.py). Since silica-based glass
has a positive thermo-optic coefficient (dn/dT > 0), this superimposes a
weak positive lens (a GRIN-like index bump, roughly parabolic near the
axis) on top of the fiber's own step-index guiding profile. At high power
this measurably shrinks the effective mode area and shifts the effective
index — the "thermal lensing" that limits achievable beam quality/output
power in high-power fiber lasers and amplifiers.

This module perturbs an existing FiberGeometry's index profile with a
radial temperature profile T(r) and re-solves the guided mode via the FD
solver (fibersim.solvers.modes.fd.solve_modes_fd already accepts any
FiberGeometry subclass's arbitrary radial index profile, so no solver
changes are needed).

Note this is a *one-way* T -> n(r) -> mode coupling, not an iterated
fixed-point loop: heat generation in this simulator's thermal model
(solvers/thermal/cavity.py) is driven by the absorbed pump power
distribution, which doesn't depend on the guided mode's own shape — so
there is no feedback path from the mode back to T(r) to iterate over. A
single solve *is* this model's fully self-consistent answer; iterating
further would not change the result.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

from fibersim.core.fiber import FiberGeometry
from fibersim.solvers.modes.analytical import Mode
from fibersim.solvers.modes.fd import solve_modes_fd

# Thermo-optic coefficient dn/dT for silica-based fiber glass (core and
# cladding; doping-level dependence is second-order for this purpose).
# Widely-cited value for fused silica in the near-IR, e.g. Ghosh,
# "Temperature dispersion of refractive indices in some silicate fiber
# glasses", IEEE Photon. Technol. Lett. 1994.
SILICA_DN_DT_PER_K = 1.1e-5

ROOM_TEMPERATURE_K = 294.15  # 21 C reference


class ThermallyPerturbedGeometry(FiberGeometry):
    """Wraps a base FiberGeometry, adding a temperature-dependent index bump
    n(r) += dn_dT * (T(r) - T_ref) on top of the base step/graded profile."""

    def __init__(
        self,
        base: FiberGeometry,
        temperature_profile_k: Callable[[np.ndarray], np.ndarray],
        dn_dt_per_k: float = SILICA_DN_DT_PER_K,
        t_ref_k: float = ROOM_TEMPERATURE_K,
    ):
        self.base = base
        self.temperature_profile_k = temperature_profile_k
        self.dn_dt_per_k = dn_dt_per_k
        self.t_ref_k = t_ref_k
        self.core_radius = base.core_radius
        self.cladding_radius = base.cladding_radius

    def refractive_index_profile(self, r, wavelength):
        n_base = self.base.refractive_index_profile(r, wavelength)
        r_arr = np.asarray(r, dtype=float)
        t_local = np.asarray(self.temperature_profile_k(r_arr), dtype=float)
        return n_base + self.dn_dt_per_k * (t_local - self.t_ref_k)

    def mode_solving_cladding_radius(self) -> float:
        return self.base.mode_solving_cladding_radius()


def radial_temperature_profile_from_thermal_result(thermal_result: dict) -> Callable[[np.ndarray], np.ndarray]:
    """Builds a T(r) [Kelvin] function from a `calculate_thermal_cavity`
    result, sampled at its hottest z-slice (z=0, where quantum-defect
    heating peaks for forward pumping), for use with
    `ThermallyPerturbedGeometry`. Interpolates the solver's own radial grid,
    holding the boundary temperature beyond the coating radius."""
    r_grid = np.asarray(thermal_result["r"], dtype=float)
    T_2d = np.asarray(thermal_result["T_2d"], dtype=float)
    t_hot = T_2d[:, 0]

    def _t_of_r(r: np.ndarray) -> np.ndarray:
        return np.interp(np.abs(r), r_grid, t_hot, left=t_hot[0], right=t_hot[-1])

    return _t_of_r


def solve_thermally_lensed_mode(
    base_geometry: FiberGeometry,
    wavelength_m: float,
    temperature_profile_k: Callable[[np.ndarray], np.ndarray],
    *,
    dn_dt_per_k: float = SILICA_DN_DT_PER_K,
    grid_points: int = 400,
) -> tuple[Mode | None, Mode | None]:
    """Solves the fundamental (l=0) guided mode both without (`cold`) and
    with (`hot`) the thermal lens, so callers can compare effective mode
    area / n_eff shift under load. Either element is None if that state
    doesn't guide a fundamental mode at this wavelength."""
    cold_modes = solve_modes_fd(base_geometry, wavelength_m, l=0, grid_points=grid_points)
    hot_geometry = ThermallyPerturbedGeometry(base_geometry, temperature_profile_k, dn_dt_per_k)
    hot_modes = solve_modes_fd(hot_geometry, wavelength_m, l=0, grid_points=grid_points)
    cold_mode = cold_modes[0] if cold_modes else None
    hot_mode = hot_modes[0] if hot_modes else None
    return cold_mode, hot_mode
