"""Virtual CCD beam profiler tests: M^2 (ISO 11146) sanity checks."""
import numpy as np
import pytest

from fibersim.core.fiber import StepIndexFiber
from fibersim.system.beam import analyze_beam, mix_fields_and_measure_m2, solve_lp01_lp11_fields

WAVELENGTH = 1064e-9


def _fiber(core_radius_um, n_core=1.46, n_clad=1.454):
    return StepIndexFiber(core_radius_um * 1e-6, 62.5e-6, n_core, n_clad)


def test_single_mode_fiber_has_near_diffraction_limited_m2():
    fiber = _fiber(2.5)  # V ~ 1.7 at 1064nm -> single mode
    result = analyze_beam(fiber, WAVELENGTH, grid_n=96, num_z=25)
    assert result.is_single_mode
    assert result.v_number < 2.405
    assert 1.0 <= result.m2x < 1.5
    assert 1.0 <= result.m2y < 1.5
    # x/y symmetric near-field (circular fiber) -> M2x ~ M2y
    assert result.m2x == pytest.approx(result.m2y, rel=0.2)


def test_multimode_fiber_has_worse_m2_than_single_mode():
    single = analyze_beam(_fiber(2.5), WAVELENGTH, grid_n=96, num_z=25)
    multi = analyze_beam(_fiber(15.0), WAVELENGTH, grid_n=96, num_z=25)
    assert not multi.is_single_mode
    assert multi.v_number > 2.405
    assert multi.m2x > single.m2x
    assert multi.m2y > single.m2y


def test_waist_is_physically_reasonable():
    fiber = _fiber(2.5)
    result = analyze_beam(fiber, WAVELENGTH, grid_n=96, num_z=25)
    # Waist radius should be on the order of the core radius (within a factor of ~3
    # given the near-field-to-waist mapping and finite grid).
    assert 0.3e-6 < result.w0x_m < 15e-6
    assert 0.3e-6 < result.w0y_m < 15e-6
    # The camera sweep must actually bracket the fitted waist.
    assert result.z_m[0] <= result.z0x_m <= result.z_m[-1]
    assert 0 <= result.waist_index < len(result.z_m)


def test_images_are_peak_normalized_and_finite():
    fiber = _fiber(2.5)
    result = analyze_beam(fiber, WAVELENGTH, grid_n=64, num_z=11)
    assert result.images.shape == (11, 64, 64)
    assert np.isfinite(result.images).all()
    assert (result.images >= 0).all()
    peaks = result.images.reshape(11, -1).max(axis=1)
    assert np.allclose(peaks, 1.0, atol=1e-6)


def test_divergence_and_bpp_positive():
    fiber = _fiber(2.5)
    result = analyze_beam(fiber, WAVELENGTH, grid_n=96, num_z=25)
    assert result.divergence_x_mrad > 0
    assert result.divergence_y_mrad > 0
    assert result.bpp_mm_mrad > 0


def test_beam_widths_grow_away_from_waist():
    fiber = _fiber(2.5)
    result = analyze_beam(fiber, WAVELENGTH, grid_n=96, num_z=25)
    w_at_waist = result.wx_m[result.waist_index]
    w_at_far_end = result.wx_m[-1]
    assert w_at_far_end > w_at_waist


# ---------------------------------------------------------------------------
# LP01/LP11 mixing (Power Ramp explorer's mode-coupling-vs-power visualization)
# ---------------------------------------------------------------------------

def test_pure_lp01_gives_diffraction_limited_m2():
    fiber = _fiber(15.0)
    x, y, psi01, psi11 = solve_lp01_lp11_fields(fiber, WAVELENGTH, grid_n=96, half_width=4 * fiber.core_radius)
    assert psi11 is not None  # this core is comfortably multimode
    m2x, m2y, _ = mix_fields_and_measure_m2(x, y, psi01, psi11, 0.0, WAVELENGTH)
    assert 1.0 <= m2x < 1.5
    assert 1.0 <= m2y < 1.5


def test_m2_increases_with_lp11_admixture():
    fiber = _fiber(15.0)
    x, y, psi01, psi11 = solve_lp01_lp11_fields(fiber, WAVELENGTH, grid_n=96, half_width=4 * fiber.core_radius)
    m2x_low, m2y_low, _ = mix_fields_and_measure_m2(x, y, psi01, psi11, 0.05, WAVELENGTH)
    m2x_high, m2y_high, _ = mix_fields_and_measure_m2(x, y, psi01, psi11, 0.4, WAVELENGTH)
    assert m2x_high > m2x_low
    assert m2y_high > m2y_low


def test_singlemode_fiber_has_no_lp11():
    fiber = _fiber(2.5)
    _, _, _, psi11 = solve_lp01_lp11_fields(fiber, WAVELENGTH, grid_n=96, half_width=4 * fiber.core_radius)
    assert psi11 is None


def test_mixed_field_is_finite_and_peak_sane():
    fiber = _fiber(15.0)
    x, y, psi01, psi11 = solve_lp01_lp11_fields(fiber, WAVELENGTH, grid_n=64, half_width=4 * fiber.core_radius)
    _, _, field = mix_fields_and_measure_m2(x, y, psi01, psi11, 0.3, WAVELENGTH)
    assert np.isfinite(field).all()
    assert np.max(np.abs(field) ** 2) > 0
