"""Yb photodarkening induced-loss estimator (Fase 4b.2)."""
import numpy as np
import pytest

from fibersim.solvers.photodarkening import photodarkening_extra_loss_db, photodarkening_loss_db_m


def test_loss_zero_at_zero_inversion():
    assert photodarkening_loss_db_m(0.0) == 0.0


def test_loss_increases_with_inversion():
    low = photodarkening_loss_db_m(0.1)
    high = photodarkening_loss_db_m(0.8)
    assert high > low


def test_loss_scales_quadratically_by_default():
    """Default model: loss ∝ N2², i.e. doubling N2 quadruples the loss."""
    a = photodarkening_loss_db_m(0.2)
    b = photodarkening_loss_db_m(0.4)
    assert b == pytest.approx(4.0 * a, rel=1e-9)


def test_loss_clips_out_of_range_inversion():
    assert photodarkening_loss_db_m(-0.5) == 0.0
    assert photodarkening_loss_db_m(1.5) == photodarkening_loss_db_m(1.0)


def test_extra_loss_integrates_over_length():
    z = np.linspace(0.0, 10.0, 200)
    n2 = np.full_like(z, 0.5)
    expected = photodarkening_loss_db_m(0.5) * 10.0
    assert photodarkening_extra_loss_db(z, n2) == pytest.approx(expected, rel=1e-3)


def test_extra_loss_zero_for_unpumped_fiber():
    z = np.linspace(0.0, 5.0, 50)
    n2 = np.zeros_like(z)
    assert photodarkening_extra_loss_db(z, n2) == 0.0
