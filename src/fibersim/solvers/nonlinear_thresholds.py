"""Nonlinear power-scaling limit estimators: stimulated Raman/Brillouin
scattering thresholds for high-power fiber laser design.

These are the standard textbook (Smith 1972; Agrawal, "Nonlinear Fiber
Optics") threshold criteria used for a quick design check — "how close am I
to the point where this nonlinearity starts stealing power/purity from my
signal" — not a full coupled-mode propagation model. Actual channel-to-channel
Raman power transfer along z is a separate, substantially larger undertaking
(coupling every pair of ASE/signal/pump bins in the propagation ODE) that is
not implemented here; see the System Builder warnings for how these
thresholds are surfaced to the user.
"""
from __future__ import annotations

import math

# Peak Raman gain coefficient for silica at 1550 nm, per Agrawal (~1e-13 m/W
# for standard single-mode fiber). Scales roughly as 1/wavelength since the
# Raman cross-section grows with photon energy.
_RAMAN_GAIN_AT_1550NM = 1.0e-13  # m/W
_RAMAN_REFERENCE_WAVELENGTH_M = 1550e-9

# Peak Brillouin gain coefficient for silica, ~ wavelength-independent over
# the near-IR range used here (Agrawal).
_BRILLOUIN_GAIN_COEFFICIENT = 5.0e-11  # m/W
# Intrinsic Brillouin gain bandwidth (linewidth) for silica at room temperature.
_BRILLOUIN_LINEWIDTH_HZ = 20e6  # ~20 MHz


def raman_gain_coefficient(wavelength_m: float) -> float:
    """Approximate silica Raman gain coefficient g_R at the given pump
    wavelength (m/W), scaling the 1550 nm reference value as 1/λ."""
    return _RAMAN_GAIN_AT_1550NM * (_RAMAN_REFERENCE_WAVELENGTH_M / wavelength_m)


def brillouin_gain_coefficient() -> float:
    """Approximate silica Brillouin gain coefficient g_B (m/W)."""
    return _BRILLOUIN_GAIN_COEFFICIENT


def effective_length(length_m: float, loss_per_m: float = 0.0) -> float:
    """L_eff = (1 - exp(-αL)) / α — accounts for fiber loss reducing the
    effective interaction length for a nonlinear process; reduces to L for
    a lossless fiber."""
    if loss_per_m <= 0.0:
        return length_m
    return (1.0 - math.exp(-loss_per_m * length_m)) / loss_per_m


def srs_threshold_power(
    wavelength_m: float,
    effective_area_m2: float,
    length_m: float,
    loss_per_m: float = 0.0,
) -> float:
    """Smith (1972) SRS threshold: the pump power at which the first-Stokes
    line reaches the same power as the pump at the fiber output.

    P_th ≈ 16 · A_eff / (g_R · L_eff)
    """
    g_r = raman_gain_coefficient(wavelength_m)
    l_eff = effective_length(length_m, loss_per_m)
    if g_r <= 0.0 or l_eff <= 0.0:
        return math.inf
    return 16.0 * effective_area_m2 / (g_r * l_eff)


def sbs_threshold_power(
    effective_area_m2: float,
    length_m: float,
    loss_per_m: float = 0.0,
    signal_linewidth_hz: float = 0.0,
) -> float:
    """Smith (1972) SBS threshold, extended with the standard linewidth
    correction: broadening the signal beyond the intrinsic Brillouin gain
    bandwidth raises the threshold by roughly (1 + Δν_signal/Δν_B).

    P_th ≈ 21 · A_eff / (g_B · L_eff) · (1 + Δν_signal / Δν_B)
    """
    g_b = brillouin_gain_coefficient()
    l_eff = effective_length(length_m, loss_per_m)
    if g_b <= 0.0 or l_eff <= 0.0:
        return math.inf
    base = 21.0 * effective_area_m2 / (g_b * l_eff)
    linewidth_factor = 1.0 + max(signal_linewidth_hz, 0.0) / _BRILLOUIN_LINEWIDTH_HZ
    return base * linewidth_factor
