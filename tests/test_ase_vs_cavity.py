"""Cross-validation between the two independent rate-equation implementations.

The repo has two solvers modeling the same physics:
- fibersim.solvers.power.ase.solve_ase (relaxation grid, generic channels)
- fibersim.solvers.thermal.cavity.solve_laser_rate_equations (MATLAB port, closed-form)

They should agree on a canonical cladding-pumped Yb FBG-cavity laser. This test pins
the current level of agreement so future unification work (plan Fase 4a) can tighten it.
"""
import numpy as np
import pytest

from fibersim.core.fiber import ActiveFiber, StepIndexFiber
from fibersim.core.ions import ActiveIon
from fibersim.solvers.power.ase import solve_ase
from fibersim.solvers.thermal.cavity import solve_laser_rate_equations

# Canonical case — matches solve_laser_rate_equations defaults
LENGTH = 13.0
CORE_RADIUS = 7.5e-6
N_TOTAL = 6e25
TAU = 1e-3
LAMBDA_PUMP = 976e-9
LAMBDA_SIGNAL = 1018e-9
SIG_ABS_P, SIG_EM_P = 2.8e-24, 1.8e-27
SIG_ABS_S, SIG_EM_S = 3.5e-27, 6.5e-25
GAMMA_P, GAMMA_S = 0.0025, 0.82
LOSS_P, LOSS_S = 0.003, 0.005
R1, R2 = 0.99, 0.04
P_PUMP = 30.0


def _matched_ion():
    """Two-point ion whose interpolated cross-sections reproduce the MATLAB defaults."""
    return ActiveIon(
        name="Yb3+ (matched)",
        lifetime=TAU,
        wavelengths=np.array([LAMBDA_PUMP, LAMBDA_SIGNAL]),
        sigma_abs=np.array([SIG_ABS_P, SIG_ABS_S]),
        sigma_em=np.array([SIG_EM_P, SIG_EM_S]),
    )


@pytest.fixture(scope="module")
def cavity_result():
    return solve_laser_rate_equations(
        fiber_length=LENGTH,
        core_radius=CORE_RADIUS,
        N_total=N_TOTAL,
        tau=TAU,
        lambda_pump=LAMBDA_PUMP,
        lambda_signal=LAMBDA_SIGNAL,
        sigma_abs_pump=SIG_ABS_P,
        sigma_em_pump=SIG_EM_P,
        sigma_abs_signal=SIG_ABS_S,
        sigma_em_signal=SIG_EM_S,
        gamma_pump=GAMMA_P,
        gamma_signal=GAMMA_S,
        alpha_p_bg=LOSS_P,
        alpha_s_bg=LOSS_S,
        R1=R1,
        R2=R2,
        P_pump_forward=P_PUMP,
        pumping="forward",
        method="analytical",
    )


@pytest.fixture(scope="module")
def ase_result():
    geometry = StepIndexFiber(CORE_RADIUS, 100e-6, 1.451, 1.445)
    fiber = ActiveFiber(geometry, _matched_ion(), N_TOTAL)
    return solve_ase(
        active_fiber=fiber,
        length=LENGTH,
        pumps=[{
            "wavelength": LAMBDA_PUMP,
            "power_in_f": P_PUMP,
            "loss": LOSS_P,
            "overlap": GAMMA_P,
        }],
        signals=[{
            "wavelength": LAMBDA_SIGNAL,
            "power_in_f": 1e-6,  # tiny seed to start the cavity field
            "loss": LOSS_S,
            "overlap": GAMMA_S,
            "R1": R1,
            "R2": R2,
        }],
        # ASE band neutralized (zero overlap): compare pure cavity signal physics
        ase_config={"wl_min": LAMBDA_PUMP, "wl_max": LAMBDA_SIGNAL, "num_channels": 2, "overlap": 0.0},
        num_z_points=300,
        max_iterations=500,
        tolerance=1e-6,
    )


def test_both_solvers_lase(cavity_result, ase_result):
    assert cavity_result["output_power"] > 1.0
    ase_out = (1.0 - R2) * float(ase_result.signals_f[0, -1])
    assert ase_out > 1.0


def test_solvers_agree_on_output_power(cavity_result, ase_result):
    """Documents current agreement between the duplicated implementations."""
    ase_out = (1.0 - R2) * float(ase_result.signals_f[0, -1])
    cavity_out = cavity_result["output_power"]
    rel_diff = abs(ase_out - cavity_out) / max(cavity_out, 1e-12)
    assert rel_diff < 0.35, (
        f"solve_ase={ase_out:.2f} W vs cavity={cavity_out:.2f} W (rel diff {rel_diff:.2%})"
    )


def test_efficiencies_below_quantum_limit(cavity_result, ase_result):
    quantum_limit = LAMBDA_PUMP / LAMBDA_SIGNAL
    assert 0.0 < cavity_result["efficiency"] <= quantum_limit
    ase_out = (1.0 - R2) * float(ase_result.signals_f[0, -1])
    assert 0.0 < ase_out / P_PUMP <= quantum_limit
