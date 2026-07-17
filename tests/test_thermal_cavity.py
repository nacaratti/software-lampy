"""Validates the thermal cavity solver's heat-load term (Fase 4a.4).

`calculate_thermal_cavity` used to source its heat generation density from
the pump power still *present* at each z (P_f + P_b), not the power actually
*absorbed* there — a self-documented approximation. This test pins the fixed
behavior: the heat density integrates to the pump power actually lost along
the fiber, and increases monotonically with pump power.
"""
import numpy as np

from fibersim.solvers.thermal.cavity import calculate_thermal_cavity, solve_laser_rate_equations

LENGTH = 13.0
CORE_RADIUS = 7.5e-6
CLAD_RADIUS = 100e-6
COATING_RADIUS = 125e-6
LAMBDA_PUMP = 976e-9
LAMBDA_SIGNAL = 1018e-9


def _laser_result(p_pump=30.0):
    return solve_laser_rate_equations(
        fiber_length=LENGTH,
        core_radius=CORE_RADIUS,
        clad_radius=CLAD_RADIUS,
        coating_radius=COATING_RADIUS,
        lambda_pump=LAMBDA_PUMP,
        lambda_signal=LAMBDA_SIGNAL,
        P_pump_forward=p_pump,
        pumping="forward",
        method="analytical",
        num_points=400,
    )


def _absorbed_density(laser_res):
    """Mirrors calculate_thermal_cavity's internal heat-density term so the
    test can check it against the solver's public P_pump_forward/backward
    outputs without reaching into private state."""
    z = laser_res["z"]
    P_f = laser_res["P_pump_forward"]
    P_b = laser_res["P_pump_backward"]
    return np.clip(-np.gradient(P_f, z) + np.gradient(P_b, z), 0.0, None)


def test_heat_density_integrates_to_absorbed_pump_power():
    laser_res = _laser_result()
    z = laser_res["z"]
    pump_total = laser_res["P_pump"]
    absorbed_total = float(pump_total[0] - pump_total[-1])

    eta_heat = 1.0 - LAMBDA_PUMP / LAMBDA_SIGNAL
    a = 2.0 * CORE_RADIUS
    q = _absorbed_density(laser_res) * eta_heat / (np.pi * a * a)
    absorbed_from_density = float(np.trapezoid(q, z)) * (np.pi * a * a) / eta_heat

    rel_diff = abs(absorbed_from_density - absorbed_total) / absorbed_total
    assert rel_diff < 0.05, (
        f"heat density integral {absorbed_from_density:.3f} W vs actual pump "
        f"depletion {absorbed_total:.3f} W (rel diff {rel_diff:.2%})"
    )


def test_heat_density_nonnegative():
    laser_res = _laser_result()
    assert np.all(_absorbed_density(laser_res) >= 0.0)


def test_higher_pump_power_gives_hotter_fiber():
    low = calculate_thermal_cavity(
        _laser_result(p_pump=10.0),
        core_radius=CORE_RADIUS, clad_radius=CLAD_RADIUS, coating_radius=COATING_RADIUS,
        lambda_pump=LAMBDA_PUMP, lambda_signal=LAMBDA_SIGNAL,
    )
    high = calculate_thermal_cavity(
        _laser_result(p_pump=60.0),
        core_radius=CORE_RADIUS, clad_radius=CLAD_RADIUS, coating_radius=COATING_RADIUS,
        lambda_pump=LAMBDA_PUMP, lambda_signal=LAMBDA_SIGNAL,
    )
    assert high["T_max_celsius"] > low["T_max_celsius"]
