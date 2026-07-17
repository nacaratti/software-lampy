"""Virtual bench instruments: optical spectrum analyzer and power meter.

Both operate on an `OpticalSignal` snapshot at the point in the circuit where
the instrument is tapped in (the engine hands them whatever channels reach
that node).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from fibersim.system.signal import OpticalSignal

_MIN_DBM = -100.0  # floor for the log scale where power is numerically zero


def _to_dbm(power_w: np.ndarray | float) -> np.ndarray | float:
    p_mw = np.asarray(power_w) * 1e3
    with np.errstate(divide="ignore"):
        dbm = 10.0 * np.log10(np.maximum(p_mw, 1e-13))
    return np.maximum(dbm, _MIN_DBM)


@dataclass
class OsaTrace:
    wavelengths_nm: np.ndarray
    power_dbm: np.ndarray
    rbw_nm: float
    peak_wavelength_nm: float
    peak_power_dbm: float
    osnr_db: float | None
    total_power_w: float


def osa_trace(
    signal: OpticalSignal,
    *,
    rbw_nm: float = 0.1,
    span_nm: float | None = None,
    center_nm: float | None = None,
    num_points: int = 601,
) -> OsaTrace:
    """Synthesizes a swept-wavelength OSA trace with a Gaussian RBW kernel.

    Each spectral line (or ASE bin) is broadened by the instrument's resolution
    bandwidth, as a real grating-based OSA would report — a truly monochromatic
    laser line still shows up with a finite RBW-limited width.
    """
    channels = signal.channels
    if not channels:
        wl = np.linspace(1000.0, 1100.0, num_points)
        return OsaTrace(wl, np.full(num_points, _MIN_DBM), rbw_nm, float(wl[0]), _MIN_DBM, None, 0.0)

    wls_nm = np.array([ch.wavelength * 1e9 for ch in channels])
    if center_nm is None or span_nm is None:
        lo, hi = float(np.min(wls_nm)), float(np.max(wls_nm))
        pad = max(5.0 * rbw_nm, 0.05 * max(hi - lo, 1.0))
        lo -= pad
        hi += pad
    else:
        lo, hi = center_nm - span_nm / 2.0, center_nm + span_nm / 2.0

    grid = np.linspace(lo, hi, num_points)
    psd = np.zeros(num_points)  # W per bin, later normalized to a per-nm density
    sigma = max(rbw_nm, (hi - lo) / num_points) / 2.3548  # Gaussian sigma from FWHM=RBW

    for ch in channels:
        wl_nm = ch.wavelength * 1e9
        kernel = np.exp(-0.5 * ((grid - wl_nm) / sigma) ** 2)
        area = np.sum(kernel) * (grid[1] - grid[0])
        if area > 0:
            psd += ch.power * kernel / area

    # Power measured in one RBW-wide window centered at each grid point — this
    # is what makes a resolved line's peak reading independent of RBW (like a
    # real OSA), rather than reporting a vanishingly thin sampling-grid slice.
    power_dbm = _to_dbm(psd * rbw_nm)
    peak_idx = int(np.argmax(power_dbm))

    signal_channels = signal.signals()
    ase_channels = signal.ase()
    osnr_db: float | None = None
    if signal_channels and ase_channels:
        peak_signal = max(ch.power for ch in signal_channels)
        # ASE floor near the signal peak (average over the ASE band, excluding a notch at the line itself)
        ase_density = signal.power_of_kind("ase") / max(
            (max(ch.wavelength for ch in ase_channels) - min(ch.wavelength for ch in ase_channels)) * 1e9, 1.0
        )
        ase_in_rbw = max(ase_density * rbw_nm, 1e-15)
        osnr_db = float(10.0 * math.log10(peak_signal / ase_in_rbw))

    return OsaTrace(
        wavelengths_nm=grid,
        power_dbm=power_dbm,
        rbw_nm=rbw_nm,
        peak_wavelength_nm=float(grid[peak_idx]),
        peak_power_dbm=float(power_dbm[peak_idx]),
        osnr_db=osnr_db,
        total_power_w=signal.total_power(),
    )


@dataclass
class PowerMeterReading:
    total_power_w: float
    total_power_dbm: float
    band_power_w: dict[str, float] = field(default_factory=dict)
    band_power_dbm: dict[str, float] = field(default_factory=dict)


def power_meter_reading(
    signal: OpticalSignal,
    bands: dict[str, tuple[float, float]] | None = None,
) -> PowerMeterReading:
    """Total + per-band power reading, like a thermal power meter with wavelength filters.

    `bands` maps a label to a (wl_min_m, wl_max_m) range; defaults to the
    pump/signal/ASE split already tracked per-channel.
    """
    total = signal.total_power()
    band_w: dict[str, float] = {}
    if bands:
        for label, (wl_min, wl_max) in bands.items():
            band_w[label] = signal.power_in_band(wl_min, wl_max)
    else:
        for kind in ("pump", "signal", "ase"):
            p = signal.power_of_kind(kind)
            if p > 0:
                band_w[kind] = p

    band_dbm = {k: float(_to_dbm(v)) for k, v in band_w.items()}
    return PowerMeterReading(
        total_power_w=total,
        total_power_dbm=float(_to_dbm(total)),
        band_power_w=band_w,
        band_power_dbm=band_dbm,
    )
