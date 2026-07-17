"""TMI risk-fraction estimator (Fase 4b.5)."""
import numpy as np
import pytest

from fibersim.core.fiber import StepIndexFiber
from fibersim.system.tmi_threshold import (
    estimate_tmi_risk,
    lp01_lp11_effective_index_gap,
    tmi_risk_fraction,
)

WAVELENGTH = 1030e-9


def _multimode_geometry(core_radius_um=15.0):
    # Large, high-NA core: comfortably supports a distinct LP11 at 1030nm.
    return StepIndexFiber(core_radius_um * 1e-6, 62.5e-6, 1.46, 1.445)


def _singlemode_geometry():
    # Small core / low NA: deeply single-mode at 1030nm, no distinct LP11.
    return StepIndexFiber(2.0e-6, 62.5e-6, 1.4501, 1.45)


def _hot_core(t_core_k):
    def _t_of_r(r):
        r = np.asarray(r, dtype=float)
        return np.where(np.abs(r) <= 15e-6, t_core_k, 294.15)
    return _t_of_r


def test_lp01_lp11_gap_positive_for_multimode_fiber():
    gap = lp01_lp11_effective_index_gap(_multimode_geometry(), WAVELENGTH)
    assert gap is not None and gap > 0.0


def test_lp01_lp11_gap_none_for_singlemode_fiber():
    gap = lp01_lp11_effective_index_gap(_singlemode_geometry(), WAVELENGTH)
    assert gap is None


def test_risk_fraction_zero_at_no_heating():
    assert tmi_risk_fraction(0.0, 1e-4) == 0.0


def test_risk_fraction_scales_with_thermal_perturbation():
    low = tmi_risk_fraction(1e-6, 1e-4)
    high = tmi_risk_fraction(1e-5, 1e-4)
    assert high > low


def test_estimate_tmi_risk_increases_with_core_temperature():
    geom = _multimode_geometry()
    low = estimate_tmi_risk(geom, WAVELENGTH, _hot_core(310.0))
    high = estimate_tmi_risk(geom, WAVELENGTH, _hot_core(420.0))
    assert low is not None and high is not None
    assert high["tmi_risk_fraction"] > low["tmi_risk_fraction"]


def test_estimate_tmi_risk_none_for_singlemode_fiber():
    result = estimate_tmi_risk(_singlemode_geometry(), WAVELENGTH, _hot_core(350.0))
    assert result is None
