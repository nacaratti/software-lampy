"""Component solver tests: FBG, coupler, taper, splicing, thermal."""
import numpy as np
import pytest

from fibersim.solvers.coupler.solver import solve_coupler
from fibersim.solvers.fbg.solver import calculate_uniform_fbg
from fibersim.solvers.modes.splicing import calculate_splicing_overlap
from fibersim.solvers.taper.solver import solve_taper
from fibersim.solvers.thermal.steady_state import solve_thermal_3layer


# ---------------------------------------------------------------------------
# FBG — uniform grating against closed-form CMT values
# ---------------------------------------------------------------------------

def test_uniform_fbg_matches_cmt_theory():
    n_eff, period_nm, length_mm, dn = 1.447, 535.5, 10.0, 1e-4
    bragg_nm = 2 * n_eff * period_nm  # 1549.74 nm
    kappa = np.pi * dn / (bragg_nm * 1e-9)
    expected_peak = np.tanh(kappa * length_mm * 1e-3) ** 2

    wl_nm, refl, meta = calculate_uniform_fbg(
        n_eff, period_nm, length_mm, dn,
        wl_start_nm=bragg_nm - 4, wl_end_nm=bragg_nm + 4, num_points=4001,
    )
    assert meta["bragg_wavelength_nm"] == pytest.approx(bragg_nm, abs=1e-6)
    assert meta["peak_reflectivity"] == pytest.approx(expected_peak, rel=1e-3)
    assert meta["kappa"] == pytest.approx(kappa, rel=1e-9)
    assert (refl >= 0).all() and (refl <= 1).all()
    # Peak sits at the Bragg wavelength on the sampled grid
    assert wl_nm[np.argmax(refl)] == pytest.approx(bragg_nm, abs=0.01)


# ---------------------------------------------------------------------------
# Coupler — CMT power exchange
# ---------------------------------------------------------------------------

def test_coupler_conserves_power():
    res = solve_coupler()
    total = res["P1_z"] + res["P2_z"]
    assert np.allclose(total, total[0], rtol=1e-12)


def test_coupler_full_transfer_at_coupling_length():
    ref = solve_coupler()
    lc_mm = ref["coupling_length_mm"]
    res = solve_coupler(coupling_length_mm=lc_mm)
    # At z = Lc with delta=0 all power crosses to port 2
    assert res["splitting_ratio"] == pytest.approx(1.0, abs=1e-6)
    assert res["P1_out"] == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Taper — adiabaticity analyzer sanity
# ---------------------------------------------------------------------------

def test_taper_gentle_is_adiabatic():
    res = solve_taper(taper_ratio=0.5, L_taper_mm=60.0, L_waist_mm=5.0)
    assert res["is_adiabatic"], f"max_eta={res['max_eta']:.3f}"
    assert 0.9 <= res["transmission"] <= 1.0
    assert np.isfinite(res["mfd_w2_um"]).all()


def test_taper_aggressive_has_higher_eta():
    """The Love & Henry adiabaticity factor must grow as the taper gets steeper."""
    gentle = solve_taper(taper_ratio=0.5, L_taper_mm=60.0)
    medium = solve_taper(taper_ratio=0.5, L_taper_mm=30.0)
    aggressive = solve_taper(taper_ratio=0.05, L_taper_mm=1.0)
    assert gentle["max_eta"] < medium["max_eta"] < aggressive["max_eta"]
    for res in (gentle, medium, aggressive):
        assert 0.0 <= res["transmission"] <= 1.0


def test_taper_rejects_invalid_ratio():
    with pytest.raises(ValueError):
        solve_taper(taper_ratio=1.5)
    with pytest.raises(ValueError):
        solve_taper(n_core=1.44, n_clad=1.45)


# ---------------------------------------------------------------------------
# Splicing — overlap-integral loss (NOTE: um/nm-based API, see plan Fase 0)
# ---------------------------------------------------------------------------

def test_identical_fibers_zero_offset_lossless():
    res = calculate_splicing_overlap(
        1.45, 1.444, 5.0,
        1.45, 1.444, 5.0,
        wavelength_nm=1030.0,
        grid_size=128,
    )
    assert res["coupling_coefficient"] > 0.999
    assert res["loss_db"] < 0.005


def test_offset_increases_loss_monotonically():
    losses = []
    for offset in (0.0, 1.0, 2.0, 4.0):
        res = calculate_splicing_overlap(
            1.45, 1.444, 5.0,
            1.45, 1.444, 5.0,
            wavelength_nm=1030.0,
            offset_x_um=offset,
            grid_size=128,
        )
        losses.append(res["loss_db"])
    assert losses == sorted(losses)
    assert losses[-1] > 0.5


def test_tilt_increases_loss():
    aligned = calculate_splicing_overlap(
        1.45, 1.444, 5.0, 1.45, 1.444, 5.0, wavelength_nm=1030.0, grid_size=128
    )
    tilted = calculate_splicing_overlap(
        1.45, 1.444, 5.0, 1.45, 1.444, 5.0,
        wavelength_nm=1030.0, tilt_x_mrad=10.0, grid_size=128,
    )
    assert tilted["loss_db"] > aligned["loss_db"]


# ---------------------------------------------------------------------------
# Thermal — 3-layer analytic solution
# ---------------------------------------------------------------------------

def test_thermal_surface_temperature_analytic():
    z = np.linspace(0.0, 1.0, 11)
    q_l = np.full_like(z, 10.0)  # 10 W/m uniform heat load
    a, b, c = 10e-6, 62.5e-6, 125e-6
    h_conv, t_amb = 100.0, 293.15
    res = solve_thermal_3layer(z, q_l, a, b, c, h_conv=h_conv, T_ambient=t_amb)
    expected_surface = t_amb + 10.0 / (2 * np.pi * h_conv * c)
    assert res["T_surface"][0] == pytest.approx(expected_surface, rel=1e-12)
    assert (res["T0"] > res["T_surface"]).all()
    assert (res["T_surface"] > t_amb).all()


def test_thermal_radial_profile_monotonic():
    z = np.linspace(0.0, 1.0, 5)
    q_l = np.full_like(z, 20.0)
    res = solve_thermal_3layer(z, q_l, 10e-6, 62.5e-6, 125e-6)
    r, t_r = res["get_radial_profile"](0)
    assert (np.diff(t_r) <= 1e-9).all(), "temperature must decrease with radius"
    assert t_r[0] == pytest.approx(res["T0"][0], rel=1e-9)
