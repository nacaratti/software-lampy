"""ESA/upconversion physics (Fase 4b.3):
- Tm3+ cross-relaxation ("2-for-1") pump quantum yield in solve_ase.
- Er3+ cooperative-upconversion concentration quenching in solve_ase.
"""
import numpy as np
import pytest

from fibersim.core.fiber import ActiveFiber, StepIndexFiber
from fibersim.core.ions import ActiveIon
from fibersim.solvers.power.ase import solve_ase

N_TOTAL = 4e24
CORE_RADIUS = 3e-6


def _fiber(ion):
    geometry = StepIndexFiber(CORE_RADIUS, 62.5e-6, 1.451, 1.445)
    return ActiveFiber(geometry, ion, N_TOTAL)


def _tm_amplifier(quantum_yield):
    ion = ActiveIon.create_tm3()
    return solve_ase(
        active_fiber=_fiber(ion),
        length=0.3,
        pumps=[{"wavelength": 790e-9, "power_in_f": 3.0, "loss": 0.0, "overlap": 0.8,
                "quantum_yield": quantum_yield}],
        signals=[{"wavelength": 1900e-9, "power_in_f": 10e-3, "loss": 0.0, "overlap": 0.9}],
        ase_config={"wl_min": 1850e-9, "wl_max": 2050e-9, "num_channels": 10, "overlap": 0.9},
        num_z_points=300,
        max_iterations=300,
    )


def test_tm_cross_relaxation_yield_increases_gain():
    """A pump quantum yield > 1 (cross-relaxation) should populate more upper-
    level ions per absorbed photon, giving strictly more signal gain for the
    same input pump power than the yield=1 (no cross-relaxation) case."""
    baseline = _tm_amplifier(quantum_yield=1.0)
    boosted = _tm_amplifier(quantum_yield=1.6)
    assert boosted.signals_f[0, -1] > baseline.signals_f[0, -1]
    assert np.max(boosted.n2_fraction) > np.max(baseline.n2_fraction)


def test_tm_cross_relaxation_yield_barely_changes_pump_depletion():
    """The yield directly affects only the population balance, not the pump's
    own photon accounting (cross-relaxation doesn't consume extra pump
    photons) — so pump depletion should be nearly identical between yields,
    save for a small second-order bleaching correction from the higher N2
    slightly reducing further ground-state pump absorption."""
    baseline = _tm_amplifier(quantum_yield=1.0)
    boosted = _tm_amplifier(quantum_yield=1.6)
    assert boosted.pumps_f[0, -1] == pytest.approx(baseline.pumps_f[0, -1], rel=0.02)


def _er_amplifier(upconversion_coeff, pump_power=50.0):
    ion = ActiveIon(
        name="Er3+ (test)",
        lifetime=10e-3,
        wavelengths=np.array([980e-9, 1530e-9]),
        sigma_abs=np.array([2.5e-25, 3.0e-25]),
        sigma_em=np.array([0.0, 3.0e-25]),
        upconversion_coeff_m3_s=upconversion_coeff,
    )
    return solve_ase(
        active_fiber=_fiber(ion),
        length=5.0,
        pumps=[{"wavelength": 980e-9, "power_in_f": pump_power, "loss": 0.0, "overlap": 0.5}],
        signals=[{"wavelength": 1530e-9, "power_in_f": 1e-3, "loss": 0.0, "overlap": 0.6}],
        ase_config={"wl_min": 1520e-9, "wl_max": 1560e-9, "num_channels": 8, "overlap": 0.6},
        num_z_points=300,
        max_iterations=300,
    )


def test_er_upconversion_reduces_peak_inversion_at_high_pump_power():
    """Cooperative upconversion (C_up > 0) opens an extra N2-dependent decay
    path, so at high pump power the achievable inversion — and hence gain —
    should be measurably lower than the C_up=0 (ideal two-level) case."""
    ideal = _er_amplifier(upconversion_coeff=0.0)
    quenched = _er_amplifier(upconversion_coeff=8e-24)
    assert np.max(quenched.n2_fraction) < np.max(ideal.n2_fraction)
    assert quenched.signals_f[0, -1] < ideal.signals_f[0, -1]


def test_er_upconversion_negligible_at_low_pump_power():
    """At low inversion, C_up*N2^2 is small relative to N2/tau, so the
    quenching effect should be minor (this pins the physical crossover, not
    an exact number)."""
    ideal = _er_amplifier(upconversion_coeff=0.0, pump_power=0.5)
    quenched = _er_amplifier(upconversion_coeff=8e-24, pump_power=0.5)
    rel_diff = abs(quenched.signals_f[0, -1] - ideal.signals_f[0, -1]) / ideal.signals_f[0, -1]
    assert rel_diff < 0.1
