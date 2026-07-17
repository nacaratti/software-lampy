"""Mode solver tests: analytical LP theory, FD cross-checks, normalization."""
import numpy as np
import pytest

from fibersim.core.fiber import StepIndexFiber
from fibersim.solvers.modes.analytical import (
    Mode,
    est_num_modes,
    find_mode,
    find_modes,
    num_rotated_modes,
    v_number,
)
from fibersim.solvers.modes.fd import solve_modes_fd

# Reference step-index fiber: a = 5 um, n_core = 1.45, n_clad = 1.4407, lambda = 1.03 um
# V = 5.00 -> guided LP modes: LP01, LP02, LP11, LP21 (LP31 cutoff V = 5.136 not guided).
# All four sit comfortably away from cutoff, where the analytical root search is reliable.
A_UM, N_CORE, N_CLAD, WL_UM = 5.0, 1.45, 1.4407, 1.03


def test_v_number_reference():
    v = v_number(A_UM, N_CORE, N_CLAD, WL_UM)
    na = np.sqrt(N_CORE**2 - N_CLAD**2)
    assert v == pytest.approx(2 * np.pi * A_UM * na / WL_UM, rel=1e-12)
    assert v == pytest.approx(5.001, abs=0.01)


def test_analytical_finds_expected_lp_modes():
    modes = find_modes(A_UM, N_CORE, N_CLAD, WL_UM)
    labels = {(m.l, m.m) for m in modes}
    assert labels == {(0, 1), (0, 2), (1, 1), (2, 1)}
    # All effective indices bounded by cladding/core indices
    for m in modes:
        assert N_CLAD < m.n_eff < N_CORE
    # LP01 has the highest n_eff
    lp01 = find_mode(modes, 0, 1)
    assert lp01.n_eff == pytest.approx(max(m.n_eff for m in modes))
    # Rotational degeneracy count: 4 modes, 2 have l>0
    assert num_rotated_modes(modes) == 6


def test_analytical_is_unit_agnostic():
    """find_modes only needs consistent units; um and m inputs must agree."""
    modes_um = find_modes(A_UM, N_CORE, N_CLAD, WL_UM)
    modes_m = find_modes(A_UM * 1e-6, N_CORE, N_CLAD, WL_UM * 1e-6)
    assert len(modes_um) == len(modes_m)
    for mu, mm in zip(modes_um, modes_m):
        assert mu.n_eff == pytest.approx(mm.n_eff, abs=1e-9)


def test_single_mode_below_lp11_cutoff():
    # V < 2.405 -> only LP01
    modes = find_modes(2.0, 1.45, 1.444, 1.03)  # V ~ 1.6
    assert {(m.l, m.m) for m in modes} == {(0, 1)}


def test_fd_matches_analytical_step_index():
    fiber = StepIndexFiber(A_UM * 1e-6, 62.5e-6, N_CORE, N_CLAD)
    wl = WL_UM * 1e-6
    analytical = find_modes(A_UM, N_CORE, N_CLAD, WL_UM)

    for l in (0, 1, 2):
        fd_modes = solve_modes_fd(fiber, wl, l=l, grid_points=1200)
        ref = [m for m in analytical if m.l == l]
        assert len(fd_modes) == len(ref), f"l={l}: FD found {len(fd_modes)}, expected {len(ref)}"
        for fd, an in zip(fd_modes, ref):
            assert fd.n_eff == pytest.approx(an.n_eff, abs=5e-5), f"l={l} m={an.m}"


def test_fd_mode_normalization():
    """FD modes must satisfy the cylindrical normalization Int(psi^2 * 2*pi*r dr) = 1."""
    fiber = StepIndexFiber(A_UM * 1e-6, 62.5e-6, N_CORE, N_CLAD)
    modes = solve_modes_fd(fiber, WL_UM * 1e-6, l=0, grid_points=800)
    assert modes
    for mode in modes:
        dr = mode.r_grid[1] - mode.r_grid[0]
        norm = np.sum(mode.psi**2 * 2.0 * np.pi * mode.r_grid * dr)
        assert norm == pytest.approx(1.0, rel=1e-9)


@pytest.mark.xfail(
    reason="Known limitation: find_modes truncates the root search at u <= V - 0.1, "
    "missing modes within 0.1 of cutoff (e.g. LP02 at V = 4.02).",
    strict=True,
)
def test_analytical_near_cutoff_modes():
    modes = find_modes(5.0, 1.45, 1.444, 1.03)  # V = 4.019; LP02 has u ~ 3.95 > V - 0.1
    assert {(m.l, m.m) for m in modes} == {(0, 1), (0, 2), (1, 1), (2, 1)}


def test_est_num_modes_scaling():
    assert est_num_modes(A_UM, N_CORE, N_CLAD, WL_UM) == pytest.approx(
        v_number(A_UM, N_CORE, N_CLAD, WL_UM) ** 2 / 2, abs=0.51
    )
