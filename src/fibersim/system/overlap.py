"""Automatic modal overlap factor Gamma.

Replaces the manual Γ scalar the user used to have to guess with a real
overlap integral between the guided mode intensity and the dopant profile —
the standard definition used throughout the rate-equation literature
(Paschotta, Giles & Desurvire): the local gain/absorption per unit length is
Γ·σ·N, where N is the peak dopant density and Γ folds in how much of the
mode's power actually sees that density.

Two regimes:
- Core-guided light (signals, and pumps in a single-clad/core-pumped fiber):
  Γ = ∫ |ψ(r)|² · [N(r)/N_max] · 2πr dr for the fundamental (l=0) mode, using
  the FD mode solver's own cylindrical normalization (∫|ψ|²2πr dr = 1).
- Cladding-pumped light in a double-clad fiber: pump light fills the entire
  (highly multimode) inner cladding rather than occupying a single clean
  mode, so the standard engineering approximation is the geometric brightness
  ratio Γ_pump ≈ A_core / A_inner_cladding.
"""
from __future__ import annotations

import math

import numpy as np

from fibersim.core.fiber import ActiveFiber, DoubleCladFiber
from fibersim.solvers.modes.fd import solve_modes_fd


def mode_dopant_overlap(fiber: ActiveFiber, wavelength_m: float, *, grid_points: int = 400) -> float:
    """Fundamental-mode/dopant overlap Γ for core-guided light.

    Returns 0.0 if no guided fundamental mode exists at this wavelength
    (e.g. wavelength beyond the fiber's guiding cutoff) rather than raising,
    so the caller can turn that into a clear warning instead of a crash.
    """
    modes = solve_modes_fd(fiber.geometry, wavelength_m, l=0, grid_points=grid_points)
    if not modes:
        return 0.0
    mode = modes[0]  # sorted by descending n_eff; [0] is the fundamental
    r = mode.r_grid
    dr = r[1] - r[0]
    density_frac = np.asarray(fiber.dopant_density_profile(r)) / fiber.N_max
    integrand = (mode.psi ** 2) * density_frac * 2.0 * math.pi * r * dr
    return float(np.clip(np.sum(integrand), 0.0, 1.0))


def cladding_pump_overlap(fiber: ActiveFiber) -> float:
    """Geometric brightness overlap Γ_pump ≈ A_core / A_inner_cladding for a
    cladding-pumped double-clad fiber. Falls back to 1.0 (fully overlapped)
    for non-double-clad geometries, which callers should not normally hit —
    core-pumped fibers should use `mode_dopant_overlap` instead."""
    geom = fiber.geometry
    if not isinstance(geom, DoubleCladFiber):
        return 1.0
    return float(np.clip((geom.core_radius / geom.inner_cladding_radius) ** 2, 0.0, 1.0))


def pump_overlap(fiber: ActiveFiber, wavelength_m: float) -> float:
    """Dispatches to the right Γ model for the pump channel based on geometry."""
    if isinstance(fiber.geometry, DoubleCladFiber):
        return cladding_pump_overlap(fiber)
    return mode_dopant_overlap(fiber, wavelength_m)


def effective_mode_area(fiber: ActiveFiber, wavelength_m: float, *, grid_points: int = 400) -> float | None:
    """Nonlinear effective area A_eff = 1 / ∫|ψ|⁴ 2πr dr for the fundamental
    (l=0) mode, using the FD solver's ∫|ψ|²2πr dr = 1 normalization. This is
    the standard definition used for nonlinear-threshold estimates (SRS/SBS).

    Returns None if no guided fundamental mode exists at this wavelength.
    """
    modes = solve_modes_fd(fiber.geometry, wavelength_m, l=0, grid_points=grid_points)
    if not modes:
        return None
    mode = modes[0]
    r = mode.r_grid
    dr = r[1] - r[0]
    integral_psi4 = float(np.sum((mode.psi ** 4) * 2.0 * math.pi * r * dr))
    if integral_psi4 <= 0.0:
        return None
    return 1.0 / integral_psi4
