"""Propagation solver tests: BPM power conservation and GNLSE physics checks."""
import math

import numpy as np
import pytest

from fibersim.core.fiber import StepIndexFiber
from fibersim.solvers.power.ase import JobCancelled
from fibersim.solvers.propagation.bpm import solve_bpm
from fibersim.solvers.propagation.gnlse import solve_gnlse


# ---------------------------------------------------------------------------
# BPM
# ---------------------------------------------------------------------------

def _gaussian_field(n_grid, half_width, waist):
    x = np.linspace(-half_width, half_width, n_grid)
    X, Y = np.meshgrid(x, x, indexing="ij")
    return np.exp(-(X**2 + Y**2) / waist**2).astype(complex)


def test_bpm_fundamental_mode_power_conservation():
    """The LP01 eigenmode must propagate with negligible power loss."""
    from fibersim.solvers.modes.fd import solve_modes_fd

    fiber = StepIndexFiber(5e-6, 62.5e-6, 1.45, 1.444)
    wl = 1.03e-6
    lp01 = solve_modes_fd(fiber, wl, l=0, grid_points=800)[0]

    half_width = 15e-6
    x = np.linspace(-half_width, half_width, 64)
    X, Y = np.meshgrid(x, x, indexing="ij")
    field = lp01.get_field_amplitude(np.sqrt(X**2 + Y**2)).astype(complex)

    # NOTE: z_steps matters — the split-step error at the sharp core interface
    # radiates power on coarse dz (64-grid/80-steps loses ~13%; 400 steps ~0.6%).
    res = solve_bpm(fiber, wl, field, length=1e-3, z_steps=400)
    ratio = res.powers[-1] / res.powers[0]
    assert 0.98 < ratio <= 1.001, f"power ratio {ratio:.4f}"
    assert np.isfinite(res.fields).all()


def test_bpm_mismatched_gaussian_radiates_more_than_mode():
    """A deliberately mismatched launch must lose more power than the eigenmode."""
    fiber = StepIndexFiber(5e-6, 62.5e-6, 1.45, 1.444)
    field = _gaussian_field(64, 15e-6, 2e-6)  # too narrow -> excites radiation
    res = solve_bpm(fiber, 1.03e-6, field, length=1e-3, z_steps=400)
    ratio = res.powers[-1] / res.powers[0]
    assert ratio < 0.95
    assert ratio > 0.3


def test_bpm_cancellation():
    fiber = StepIndexFiber(5e-6, 62.5e-6, 1.45, 1.444)
    field = _gaussian_field(32, 15e-6, 4e-6)
    with pytest.raises(JobCancelled):
        solve_bpm(fiber, 1.03e-6, field, length=1e-3, z_steps=60,
                  progress_callback=lambda _v: False)


# ---------------------------------------------------------------------------
# GNLSE
# ---------------------------------------------------------------------------

BETA2 = -2.17e-26   # s^2/m (-21.7 ps^2/km, standard SMF anomalous dispersion)
GAMMA_NL = 1.3e-3   # 1/(W m)
T0 = 100e-15        # s


def _time_grid(n=1024, window=3e-12):
    return np.linspace(-window / 2, window / 2, n, endpoint=False)


def _fwhm(t, power):
    half = power.max() / 2.0
    above = np.where(power >= half)[0]
    return t[above[-1]] - t[above[0]]


def test_gnlse_linear_gaussian_dispersion_broadening():
    """With gamma=0 the SSFM is exact: a Gaussian broadens by sqrt(1+(z/L_D)^2)."""
    t = _time_grid()
    pulse = np.exp(-t**2 / (2 * T0**2)).astype(complex)
    L_D = T0**2 / abs(BETA2)
    res = solve_gnlse(
        time_grid=t,
        initial_envelope=pulse,
        length=L_D,
        wavelength_zero=1550e-9,
        gamma=0.0,
        beta_list=[BETA2],
        self_steepening=False,
        raman=False,
        z_steps=100,
    )
    fwhm_in = _fwhm(t, np.abs(res.envelopes[0]) ** 2)
    fwhm_out = _fwhm(t, np.abs(res.envelopes[-1]) ** 2)
    assert fwhm_out / fwhm_in == pytest.approx(np.sqrt(2.0), rel=0.02)


def test_gnlse_fundamental_soliton_preserved():
    """An N=1 soliton (no Raman/shock) keeps its peak power over one soliton period."""
    t = _time_grid()
    p0 = abs(BETA2) / (GAMMA_NL * T0**2)
    pulse = np.sqrt(p0) / np.cosh(t / T0)
    z0 = (np.pi / 2.0) * T0**2 / abs(BETA2)
    res = solve_gnlse(
        time_grid=t,
        initial_envelope=pulse.astype(complex),
        length=z0,
        wavelength_zero=1550e-9,
        gamma=GAMMA_NL,
        beta_list=[BETA2],
        self_steepening=False,
        raman=False,
        z_steps=300,
    )
    peak_out = np.max(np.abs(res.envelopes[-1]) ** 2)
    assert peak_out == pytest.approx(p0, rel=0.03)
    # Pulse energy conserved (lossless propagation)
    e_in = np.sum(np.abs(res.envelopes[0]) ** 2)
    e_out = np.sum(np.abs(res.envelopes[-1]) ** 2)
    assert e_out == pytest.approx(e_in, rel=1e-6)


def test_gnlse_spm_broadens_spectrum():
    """Pure SPM (no dispersion) must broaden the spectrum while conserving energy."""
    t = _time_grid()
    pulse = (np.sqrt(100.0) * np.exp(-t**2 / (2 * T0**2))).astype(complex)
    res = solve_gnlse(
        time_grid=t,
        initial_envelope=pulse,
        length=10.0,
        wavelength_zero=1550e-9,
        gamma=GAMMA_NL,
        beta_list=[0.0],
        self_steepening=False,
        raman=False,
        z_steps=200,
    )

    def spectral_rms(spectrum):
        p = np.abs(spectrum) ** 2
        f = res.frequencies
        mean = np.sum(f * p) / np.sum(p)
        return np.sqrt(np.sum((f - mean) ** 2 * p) / np.sum(p))

    assert spectral_rms(res.spectrums[-1]) > 1.5 * spectral_rms(res.spectrums[0])


# ---------------------------------------------------------------------------
# GNLSE + saturable gain (Fase 4b.6)
# ---------------------------------------------------------------------------

def test_gnlse_gain_amplifies_pulse_energy():
    """A positive small-signal gain with no saturation should amplify the
    pulse energy by exp(g0*L) over a lossless, dispersionless, gainful pass."""
    t = _time_grid()
    pulse = np.exp(-t**2 / (2 * T0**2)).astype(complex)
    g0 = 2.0  # 1/m
    length = 3.0
    res = solve_gnlse(
        time_grid=t, initial_envelope=pulse, length=length, wavelength_zero=1550e-9,
        gamma=0.0, beta_list=[0.0], self_steepening=False, raman=False, z_steps=200,
        small_signal_gain_per_m=g0,
    )
    e_in = np.sum(np.abs(res.envelopes[0]) ** 2)
    e_out = np.sum(np.abs(res.envelopes[-1]) ** 2)
    assert e_out / e_in == pytest.approx(math.exp(g0 * length), rel=0.02)
    assert res.saturated_gain_per_m == pytest.approx(g0)


def test_gnlse_gain_defaults_to_unchanged_passive_solver():
    """small_signal_gain_per_m=0.0 (the default) must reproduce the exact
    passive-fiber behavior — no gain-related fields populated."""
    t = _time_grid()
    pulse = np.exp(-t**2 / (2 * T0**2)).astype(complex)
    res = solve_gnlse(
        time_grid=t, initial_envelope=pulse, length=1.0, wavelength_zero=1550e-9,
        gamma=0.0, beta_list=[0.0], self_steepening=False, raman=False, z_steps=50,
    )
    assert res.saturated_gain_per_m is None
    assert res.pulse_energy_in_j is None
    assert res.pulse_energy_out_j is None


def test_gnlse_gain_saturates_with_energy():
    """A high-energy pulse relative to E_sat should see less net amplification
    than a low-energy one, given the same small-signal gain — the defining
    signature of gain saturation."""
    t = _time_grid()
    g0 = 5.0
    length = 2.0
    e_sat = 1e-10  # J (arbitrary units consistent with |A|^2 in W)

    low_energy_pulse = (0.01 * np.exp(-t**2 / (2 * T0**2))).astype(complex)
    high_energy_pulse = (5.0 * np.exp(-t**2 / (2 * T0**2))).astype(complex)

    def _gain_ratio(pulse):
        res = solve_gnlse(
            time_grid=t, initial_envelope=pulse, length=length, wavelength_zero=1550e-9,
            gamma=0.0, beta_list=[0.0], self_steepening=False, raman=False, z_steps=200,
            small_signal_gain_per_m=g0, saturation_energy_j=e_sat,
        )
        e_in = np.sum(np.abs(res.envelopes[0]) ** 2)
        e_out = np.sum(np.abs(res.envelopes[-1]) ** 2)
        return e_out / e_in, res.saturated_gain_per_m

    low_ratio, low_gain = _gain_ratio(low_energy_pulse)
    high_ratio, high_gain = _gain_ratio(high_energy_pulse)
    assert high_gain < low_gain
    assert high_ratio < low_ratio


def test_gnlse_gain_bandwidth_limits_far_off_carrier_gain():
    """A finite gain bandwidth should amplify a narrowband pulse near the
    carrier more than a broadband one with significant spectral content far
    from the carrier (the Lorentzian gain filter rolls off)."""
    t = _time_grid(n=2048, window=6e-12)
    g0 = 4.0
    length = 2.0
    bandwidth_hz = 1e12  # 1 THz gain bandwidth

    narrow_pulse = np.exp(-t**2 / (2 * (500e-15) ** 2)).astype(complex)
    broad_pulse = np.exp(-t**2 / (2 * (20e-15) ** 2)).astype(complex)  # much broader spectrum

    def _energy_gain(pulse):
        res = solve_gnlse(
            time_grid=t, initial_envelope=pulse, length=length, wavelength_zero=1550e-9,
            gamma=0.0, beta_list=[0.0], self_steepening=False, raman=False, z_steps=200,
            small_signal_gain_per_m=g0, gain_bandwidth_hz=bandwidth_hz,
        )
        e_in = np.sum(np.abs(res.envelopes[0]) ** 2)
        e_out = np.sum(np.abs(res.envelopes[-1]) ** 2)
        return e_out / e_in

    assert _energy_gain(narrow_pulse) > _energy_gain(broad_pulse)
