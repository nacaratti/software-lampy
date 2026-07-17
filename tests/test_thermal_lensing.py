"""Coupled thermal lensing (Fase 4b.4): dn/dT-perturbed mode solve."""
import numpy as np
import pytest

from fibersim.core.fiber import StepIndexFiber
from fibersim.system.thermal_lensing import (
    SILICA_DN_DT_PER_K,
    ThermallyPerturbedGeometry,
    radial_temperature_profile_from_thermal_result,
    solve_thermally_lensed_mode,
)
from fibersim.solvers.thermal.cavity import calculate_thermal_cavity, solve_laser_rate_equations

WAVELENGTH = 1030e-9
CORE_RADIUS = 5e-6
CLAD_RADIUS = 62.5e-6


def _geometry():
    return StepIndexFiber(CORE_RADIUS, CLAD_RADIUS, 1.46, 1.454)


def _uniform_hot_core(t_core_k=350.0, t_ref_k=294.15):
    def _t_of_r(r):
        r = np.asarray(r, dtype=float)
        return np.where(np.abs(r) <= CORE_RADIUS, t_core_k, t_ref_k)
    return _t_of_r


def test_hot_core_increases_effective_index():
    """A hotter core (dn/dT > 0) adds positive index, so n_eff of the
    perturbed mode should exceed the unperturbed (cold) one."""
    cold, hot = solve_thermally_lensed_mode(_geometry(), WAVELENGTH, _uniform_hot_core())
    assert cold is not None and hot is not None
    assert hot.n_eff > cold.n_eff


def test_no_heating_reproduces_cold_mode():
    """A temperature profile pinned at the reference temperature everywhere
    should leave the mode effectively unchanged."""
    room_temp = lambda r: np.full_like(np.asarray(r, dtype=float), 294.15)
    cold, hot = solve_thermally_lensed_mode(_geometry(), WAVELENGTH, room_temp)
    assert hot.n_eff == pytest.approx(cold.n_eff, abs=1e-9)


def test_hotter_core_gives_larger_index_shift():
    _, hot_low = solve_thermally_lensed_mode(_geometry(), WAVELENGTH, _uniform_hot_core(t_core_k=320.0))
    cold, hot_high = solve_thermally_lensed_mode(_geometry(), WAVELENGTH, _uniform_hot_core(t_core_k=400.0))
    assert (hot_high.n_eff - cold.n_eff) > (hot_low.n_eff - cold.n_eff)


def test_perturbed_geometry_matches_manual_dn_dt_formula():
    geom = ThermallyPerturbedGeometry(_geometry(), _uniform_hot_core(t_core_k=350.0))
    n_center = geom.refractive_index_profile(0.0, WAVELENGTH)
    n_base_center = _geometry().refractive_index_profile(0.0, WAVELENGTH)
    expected = n_base_center + SILICA_DN_DT_PER_K * (350.0 - 294.15)
    assert n_center == pytest.approx(expected)


def test_radial_temperature_profile_from_real_thermal_solver():
    """End-to-end: build T(r) from the actual thermal cavity solver's
    output and confirm it feeds a sane, hotter-than-reference on-axis
    temperature into the mode solver."""
    laser_res = solve_laser_rate_equations(
        fiber_length=5.0, core_radius=CORE_RADIUS, clad_radius=CLAD_RADIUS,
        P_pump_forward=20.0, pumping="forward", method="analytical", num_points=200,
    )
    thermal_res = calculate_thermal_cavity(
        laser_res, core_radius=CORE_RADIUS, clad_radius=CLAD_RADIUS, coating_radius=87.5e-6,
        T_ambient=294.15,
    )
    t_of_r = radial_temperature_profile_from_thermal_result(thermal_res)
    assert t_of_r(0.0) > 294.15

    cold, hot = solve_thermally_lensed_mode(_geometry(), WAVELENGTH, t_of_r)
    assert cold is not None and hot is not None
    assert hot.n_eff >= cold.n_eff
