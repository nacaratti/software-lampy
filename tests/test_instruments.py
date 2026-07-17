"""Virtual bench instrument tests: OSA trace and power meter."""
import numpy as np
import pytest

from fibersim.system.instruments import osa_trace, power_meter_reading
from fibersim.system.signal import OpticalSignal, SpectralChannel


def _amp_signal():
    return OpticalSignal([
        SpectralChannel(976e-9, 0.5, "pump"),
        SpectralChannel(1064e-9, 2.0, "signal"),
        SpectralChannel(1050e-9, 1e-4, "ase", width=2e-9),
        SpectralChannel(1080e-9, 1e-4, "ase", width=2e-9),
    ])


def test_osa_peak_matches_strongest_line():
    trace = osa_trace(_amp_signal(), rbw_nm=0.1, num_points=2000)
    assert trace.peak_wavelength_nm == pytest.approx(1064.0, abs=0.2)
    assert trace.peak_power_dbm > 0  # 2W signal -> +33 dBm


def test_osa_reports_multiple_lines_above_floor():
    trace = osa_trace(_amp_signal(), rbw_nm=0.05, num_points=4000)
    # Both the pump (976nm) and signal (1064nm) peaks should be resolvable
    idx_pump = int(np.argmin(np.abs(trace.wavelengths_nm - 976.0)))
    idx_signal = int(np.argmin(np.abs(trace.wavelengths_nm - 1064.0)))
    assert trace.power_dbm[idx_pump] > -20
    assert trace.power_dbm[idx_signal] > 20


def test_osa_peak_reading_is_rbw_independent_for_a_resolved_line():
    """A well-isolated line's peak reading shouldn't depend on the chosen RBW
    (real OSAs report the same peak power for a resolved line regardless of
    resolution bandwidth — only the noise floor and adjacent-feature
    resolvability change)."""
    narrow = osa_trace(_amp_signal(), rbw_nm=0.02, num_points=4000)
    wide = osa_trace(_amp_signal(), rbw_nm=1.0, num_points=4000)
    assert wide.peak_power_dbm == pytest.approx(narrow.peak_power_dbm, abs=2.5)


def test_osa_empty_signal_returns_floor():
    trace = osa_trace(OpticalSignal.empty())
    assert trace.total_power_w == 0.0
    assert np.all(trace.power_dbm <= -99)


def test_osa_osnr_positive_for_amplifier_signal():
    trace = osa_trace(_amp_signal())
    assert trace.osnr_db is not None
    assert trace.osnr_db > 20  # strong signal vs weak ASE


def test_power_meter_default_bands():
    reading = power_meter_reading(_amp_signal())
    assert reading.total_power_w == pytest.approx(0.5 + 2.0 + 2e-4)
    assert reading.band_power_w["pump"] == pytest.approx(0.5)
    assert reading.band_power_w["signal"] == pytest.approx(2.0)
    assert reading.band_power_w["ase"] == pytest.approx(2e-4)
    assert reading.total_power_dbm == pytest.approx(10 * np.log10(reading.total_power_w * 1e3))


def test_power_meter_custom_bands():
    reading = power_meter_reading(
        _amp_signal(), bands={"c_band": (1000e-9, 1100e-9), "pump_band": (900e-9, 1000e-9)}
    )
    assert reading.band_power_w["c_band"] == pytest.approx(2.0 + 2e-4)
    assert reading.band_power_w["pump_band"] == pytest.approx(0.5)


def test_power_meter_empty_signal():
    reading = power_meter_reading(OpticalSignal.empty())
    assert reading.total_power_w == 0.0
    assert reading.band_power_w == {}
