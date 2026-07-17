"""Automatic Γ overlap factor tests: mode/dopant integral and cladding-pump ratio."""
import math

import pytest

from fibersim.core.fiber import ActiveFiber, DoubleCladFiber, StepIndexFiber
from fibersim.core.ions import ActiveIon
from fibersim.system.overlap import (
    cladding_pump_overlap,
    effective_mode_area,
    mode_dopant_overlap,
    pump_overlap,
)

WAVELENGTH = 1030e-9


def _step_index_active(core_radius_um=2.5, n_core=1.46, n_clad=1.454, profile="uniform"):
    geometry = StepIndexFiber(core_radius_um * 1e-6, 62.5e-6, n_core, n_clad)
    return ActiveFiber(geometry, ActiveIon.create_yb3(), 3e25, dopant_profile_type=profile)


def test_uniform_core_doping_gives_high_overlap_below_cutoff():
    # V ~ 1.4 at 1030nm for a 2.5um core -> deeply single-mode, most power in core
    fiber = _step_index_active(core_radius_um=2.5)
    gamma = mode_dopant_overlap(fiber, WAVELENGTH)
    assert 0.5 < gamma <= 1.0


def test_overlap_increases_with_core_size_up_to_a_point():
    """A larger core confines the fundamental mode more tightly relative to
    the doped region, so overlap should not decrease as the core grows from
    a very small, weakly-guiding size (mode spreads well beyond the core)."""
    small = mode_dopant_overlap(_step_index_active(core_radius_um=1.0), WAVELENGTH)
    mid = mode_dopant_overlap(_step_index_active(core_radius_um=3.0), WAVELENGTH)
    assert mid > small


def test_gaussian_doping_profile_gives_different_overlap_than_uniform():
    uniform = mode_dopant_overlap(_step_index_active(profile="uniform"), WAVELENGTH)
    gaussian = mode_dopant_overlap(_step_index_active(profile="gaussian"), WAVELENGTH)
    # Different profiles integrate against the same mode differently — they
    # should not coincidentally match to high precision.
    assert uniform != pytest.approx(gaussian, rel=1e-3)
    assert 0.0 < gaussian <= 1.0


def test_overlap_zero_beyond_cutoff():
    # A wavelength far too long for this tiny core to guide anything.
    fiber = _step_index_active(core_radius_um=1.0)
    gamma = mode_dopant_overlap(fiber, 5000e-9)
    assert gamma == 0.0


def test_cladding_pump_overlap_matches_area_ratio():
    geometry = DoubleCladFiber(7.5e-6, 100e-6, 125e-6, 1.46, 1.4547, 1.375)
    fiber = ActiveFiber(geometry, ActiveIon.create_yb3(), 6e25)
    gamma = cladding_pump_overlap(fiber)
    expected = (7.5 / 100.0) ** 2
    assert gamma == pytest.approx(expected, rel=1e-9)


def test_cladding_pump_overlap_is_much_smaller_than_core_overlap():
    geometry = DoubleCladFiber(7.5e-6, 100e-6, 125e-6, 1.46, 1.4547, 1.375)
    fiber = ActiveFiber(geometry, ActiveIon.create_yb3(), 6e25)
    gamma_pump = cladding_pump_overlap(fiber)
    gamma_signal = mode_dopant_overlap(fiber, 1030e-9)
    assert gamma_pump < 0.05
    assert gamma_signal > 0.3
    assert gamma_pump < gamma_signal


def test_effective_mode_area_reasonable_for_small_core():
    fiber = _step_index_active(core_radius_um=2.5)
    a_eff = effective_mode_area(fiber, WAVELENGTH)
    assert a_eff is not None
    core_area_m2 = math.pi * (2.5e-6) ** 2
    # A_eff for a well-guided fundamental mode is typically within a factor
    # of a few of the core's own geometric area.
    assert 0.3 * core_area_m2 < a_eff < 5.0 * core_area_m2


def test_effective_mode_area_grows_with_core_size():
    small = effective_mode_area(_step_index_active(core_radius_um=2.0), WAVELENGTH)
    large = effective_mode_area(_step_index_active(core_radius_um=6.0), WAVELENGTH)
    assert large > small


def test_effective_mode_area_none_beyond_cutoff():
    fiber = _step_index_active(core_radius_um=1.0)
    assert effective_mode_area(fiber, 5000e-9) is None


def test_pump_overlap_dispatches_by_geometry():
    single_clad = _step_index_active()
    assert pump_overlap(single_clad, WAVELENGTH) == pytest.approx(
        mode_dopant_overlap(single_clad, WAVELENGTH), rel=1e-6
    )

    dc_geometry = DoubleCladFiber(7.5e-6, 100e-6, 125e-6, 1.46, 1.4547, 1.375)
    dc_fiber = ActiveFiber(dc_geometry, ActiveIon.create_yb3(), 6e25)
    assert pump_overlap(dc_fiber, 976e-9) == cladding_pump_overlap(dc_fiber)
