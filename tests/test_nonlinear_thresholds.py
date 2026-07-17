"""SRS/SBS threshold estimator tests (Smith 1972 criteria)."""
import math

import pytest

from fibersim.solvers.nonlinear_thresholds import (
    brillouin_gain_coefficient,
    effective_length,
    raman_gain_coefficient,
    sbs_threshold_power,
    srs_threshold_power,
)


def test_effective_length_reduces_to_physical_length_when_lossless():
    assert effective_length(10.0, 0.0) == 10.0


def test_effective_length_saturates_for_long_lossy_fiber():
    # A very lossy fiber's effective length approaches 1/alpha once alpha*L >> 1,
    # regardless of how much longer L keeps growing beyond that point.
    alpha = 0.5
    l_eff_at_5_over_alpha = effective_length(5.0 / alpha, loss_per_m=alpha)
    l_eff_much_longer = effective_length(100.0, loss_per_m=alpha)
    assert l_eff_much_longer == pytest.approx(l_eff_at_5_over_alpha, rel=0.01)
    assert l_eff_much_longer < 1.0 / alpha * 1.01


def test_raman_gain_scales_inversely_with_wavelength():
    g_short = raman_gain_coefficient(1000e-9)
    g_long = raman_gain_coefficient(1550e-9)
    assert g_short > g_long
    assert g_long == pytest.approx(1.0e-13, rel=1e-9)


def test_srs_threshold_decreases_with_length():
    a_eff = 50e-12  # ~50 um^2, typical single-mode core
    p_short = srs_threshold_power(1064e-9, a_eff, length_m=1.0)
    p_long = srs_threshold_power(1064e-9, a_eff, length_m=10.0)
    assert p_long < p_short


def test_srs_threshold_increases_with_mode_area():
    small_area = srs_threshold_power(1064e-9, 50e-12, length_m=5.0)
    large_area = srs_threshold_power(1064e-9, 500e-12, length_m=5.0)
    assert large_area > small_area
    assert large_area == pytest.approx(small_area * 10.0, rel=1e-9)


def test_srs_threshold_matches_smith_formula_reference_case():
    # Reference case: A_eff=50 um^2, L=1 km, 1550nm -> P_th of order a few watts
    # (widely-cited SRS thresholds for km-length telecom fiber are ~1-10 W).
    a_eff = 50e-12
    p_th = srs_threshold_power(1550e-9, a_eff, length_m=1000.0, loss_per_m=0.2e-3)
    assert 0.5 < p_th < 50.0


def test_sbs_threshold_lower_than_srs_for_narrowband_signal():
    """SBS has a much narrower gain bandwidth than SRS, so for a narrow-linewidth
    signal its threshold is typically far lower — the classic reason SBS (not
    SRS) usually limits narrow-linewidth high-power fiber amplifiers first."""
    a_eff = 50e-12
    length = 10.0
    srs = srs_threshold_power(1064e-9, a_eff, length_m=length)
    sbs = sbs_threshold_power(a_eff, length_m=length, signal_linewidth_hz=1e6)
    assert sbs < srs


def test_sbs_threshold_rises_with_signal_linewidth():
    a_eff = 50e-12
    narrow = sbs_threshold_power(a_eff, length_m=10.0, signal_linewidth_hz=1e6)
    broad = sbs_threshold_power(a_eff, length_m=10.0, signal_linewidth_hz=1e10)
    assert broad > narrow


def test_thresholds_are_infinite_for_zero_length():
    assert math.isinf(srs_threshold_power(1064e-9, 50e-12, length_m=0.0))
    assert math.isinf(sbs_threshold_power(50e-12, length_m=0.0))


def test_brillouin_gain_coefficient_is_positive_constant():
    assert brillouin_gain_coefficient() > 0
