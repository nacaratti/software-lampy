"""Steady-state rate-equation solver tests (migrated from verification/verify_fibersim.py)."""
import pytest

from fibersim.solvers.power.steady_state import OpticalChannel, solve_steady_state

# YDFA reference case from the original verification script
LENGTH = 5.0
N_TOTAL = 4e25
TAU = 1e-3
CORE_RADIUS = 3e-6
PUMP_IN = 10.0
SIGNAL_IN = 1e-3


def _ydfa_channels():
    return [
        OpticalChannel(
            name="Forward_Pump",
            wavelength=976e-9,
            power_in=PUMP_IN,
            direction="forward",
            sigma_abs=2.5e-25,
            sigma_em=2.7e-25,
            overlap=0.8,
            loss=0.01,
        ),
        OpticalChannel(
            name="Forward_Signal",
            wavelength=1030e-9,
            power_in=SIGNAL_IN,
            direction="forward",
            sigma_abs=0.4e-25,
            sigma_em=4.5e-25,
            overlap=0.9,
            loss=0.01,
        ),
    ]


@pytest.fixture(scope="module")
def ydfa_result():
    return solve_steady_state(
        length=LENGTH,
        N_total=N_TOTAL,
        tau=TAU,
        core_radius=CORE_RADIUS,
        channels=_ydfa_channels(),
        num_points=200,
    )


def test_signal_is_amplified(ydfa_result):
    signal_out = ydfa_result["output_powers"]["Forward_Signal"]
    assert signal_out > SIGNAL_IN
    assert ydfa_result["gain_db"]["Forward_Signal"] > 0.0


def test_pump_is_absorbed(ydfa_result):
    pump_out = ydfa_result["output_powers"]["Forward_Pump"]
    assert 0.0 <= pump_out < PUMP_IN


def test_efficiency_bounds(ydfa_result):
    assert 0.0 <= ydfa_result["efficiency"] <= 1.0


def test_photon_conservation(ydfa_result):
    """Extracted signal photons cannot exceed absorbed pump photons.

    Photon rate is proportional to P * lambda, so the quantum-limited bound is
    dP_signal * lambda_signal <= dP_pump_absorbed * lambda_pump (with slack for
    numerical discretization).
    """
    pump_out = ydfa_result["output_powers"]["Forward_Pump"]
    signal_out = ydfa_result["output_powers"]["Forward_Signal"]
    signal_photons = (signal_out - SIGNAL_IN) * 1030e-9
    pump_photons = (PUMP_IN - pump_out) * 976e-9
    assert signal_photons <= pump_photons * 1.05


def test_population_fractions_physical(ydfa_result):
    n2 = ydfa_result["N2"]
    assert (n2 >= 0).all()
    assert (n2 <= N_TOTAL).all()
