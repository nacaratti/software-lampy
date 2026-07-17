"""Bidirectional ASE solver tests: amplifier, cavity lasing, cancellation."""
import numpy as np
import pytest

from fibersim.core.fiber import ActiveFiber, StepIndexFiber
from fibersim.core.ions import ActiveIon
from fibersim.solvers.power.ase import JobCancelled, solve_ase


# NOTE: parameters chosen so the z-grid resolves the pump absorption length.
# With N = 4e25 the pump absorption is ~80/m and a coarse grid makes the
# first-order relaxation scheme non-conservative (documented limitation —
# see plan Fase 4a: grid-adequacy warning / adaptive stepping).
N_TOTAL = 4e24
PUMP_IN = 5.0
SIGNAL_IN = 10e-3


def _yb_fiber(core_radius=3e-6, n_total=N_TOTAL):
    geometry = StepIndexFiber(core_radius, 62.5e-6, 1.451, 1.445)
    return ActiveFiber(geometry, ActiveIon.create_yb3(), n_total)


@pytest.fixture(scope="module")
def amplifier_result():
    return solve_ase(
        active_fiber=_yb_fiber(),
        length=0.5,
        pumps=[{"wavelength": 976e-9, "power_in_f": PUMP_IN, "loss": 0.0, "overlap": 0.8}],
        signals=[{"wavelength": 1030e-9, "power_in_f": SIGNAL_IN, "loss": 0.0, "overlap": 0.9}],
        ase_config={"wl_min": 1000e-9, "wl_max": 1100e-9, "num_channels": 20, "overlap": 0.9},
        num_z_points=400,
        max_iterations=200,
    )


def test_amplifier_gain(amplifier_result):
    res = amplifier_result
    assert res.signals_f[0, -1] > SIGNAL_IN, "signal should be amplified"
    assert res.pumps_f[0, -1] < PUMP_IN, "pump should be depleted"


def test_amplifier_physical_outputs(amplifier_result):
    res = amplifier_result
    for arr in (res.pumps_f, res.pumps_b, res.signals_f, res.signals_b, res.ase_f, res.ase_b):
        assert np.isfinite(arr).all()
        assert (arr >= 0).all()
    assert (res.n2_fraction >= 0).all() and (res.n2_fraction <= 1).all()


def test_amplifier_energy_conservation(amplifier_result):
    """Total optical power out cannot exceed total power in (on a resolved grid)."""
    res = amplifier_result
    total_in = PUMP_IN + SIGNAL_IN
    total_out = (
        res.pumps_f[0, -1]
        + res.signals_f[0, -1]
        + float(np.sum(res.ase_f[:, -1]) + np.sum(res.ase_b[:, 0]))
    )
    assert total_out <= total_in * 1.02


def test_amplifier_quantum_limit(amplifier_result):
    res = amplifier_result
    signal_gain_power = res.signals_f[0, -1] - res.signals_f[0, 0]
    ase_power = float(np.sum(res.ase_f[:, -1]) + np.sum(res.ase_b[:, 0]))
    pump_absorbed = res.pumps_f[0, 0] - res.pumps_f[0, -1]
    # Extracted photons (signal + ASE) cannot exceed absorbed pump photons
    extracted = signal_gain_power * 1030e-9 + ase_power * 1050e-9
    assert extracted <= pump_absorbed * 976e-9 * 1.10


def test_cavity_lasing_from_ase():
    """A pumped fiber between R1=0.99 / R2=0.1 reflectors must build up laser power."""
    pump_in = 10.0
    res = solve_ase(
        active_fiber=_yb_fiber(),
        length=1.0,
        pumps=[{"wavelength": 976e-9, "power_in_f": pump_in, "loss": 0.0, "overlap": 0.8}],
        signals=[],
        ase_config={
            "wl_min": 1020e-9,
            "wl_max": 1090e-9,
            "num_channels": 30,
            "overlap": 0.9,
            "R1": 0.99,
            "R2": 0.1,
        },
        num_z_points=400,
        max_iterations=400,
        tolerance=1e-5,
    )
    output_power = (1.0 - 0.1) * float(np.sum(res.ase_f[:, -1]))
    assert output_power > 0.5, f"cavity should lase, got {output_power:.3f} W out"
    # Efficiency below quantum limit
    assert output_power < pump_in * (976.0 / 1020.0)


def test_progress_callback_cancellation():
    with pytest.raises(JobCancelled):
        solve_ase(
            active_fiber=_yb_fiber(),
            length=3.0,
            pumps=[{"wavelength": 976e-9, "power_in_f": 5.0, "overlap": 0.8}],
            signals=[{"wavelength": 1030e-9, "power_in_f": 10e-3, "overlap": 0.9}],
            ase_config={"wl_min": 1000e-9, "wl_max": 1100e-9, "num_channels": 10},
            num_z_points=50,
            progress_callback=lambda _v: False,
        )
