"""Yb photodarkening: empirical induced-loss estimator.

Photodarkening is the formation of color centers in Yb-doped aluminosilicate
fiber under sustained high inversion, causing an excess signal-wavelength
loss that grows with accumulated excited-state population and saturates
over operating time. Measurements across several groups (Jetschke et al.,
"Role of Ce in Yb/Al laser fibers", Opt. Express 2008; Engholm & Norin,
Opt. Express 2008; Yoo et al.) consistently report the induced loss scaling
with roughly the *square* of the local N2 population fraction — consistent
with a cooperative two-ion upconversion mechanism for defect formation —
and saturating (in time) at a level of order 1-10 dB/m for standard,
non-photodarkening-resistant high-NA Yb fiber at full inversion.

This module deliberately estimates only the fully time-saturated loss level
as a function of local inversion, as a design-time diagnostic — not a
kinetic model coupled back into propagation. The actual growth-rate-to-
saturation depends on fabrication-specific trap densities this generic
simulator has no principled way to source, so (mirroring the SRS/SBS
threshold-diagnostic scoping decision in Fase 4a) this gives "how much this
design could eventually cost you", not a validated time-domain simulation.
"""
from __future__ import annotations

import numpy as np

_DEFAULT_PD_COEFFICIENT_DB_M = 3.0
_DEFAULT_PD_EXPONENT = 2.0


def photodarkening_loss_db_m(
    n2_fraction,
    *,
    coefficient_db_m: float = _DEFAULT_PD_COEFFICIENT_DB_M,
    exponent: float = _DEFAULT_PD_EXPONENT,
) -> np.ndarray:
    """Steady-state (fully time-saturated) photodarkening-induced loss
    density at local Yb inversion `n2_fraction` (N2/N_total, in [0, 1]).
    Returns dB/m, same shape as the input.
    """
    n2 = np.clip(np.asarray(n2_fraction, dtype=float), 0.0, 1.0)
    return coefficient_db_m * n2 ** exponent


def photodarkening_extra_loss_db(
    z_m,
    n2_fraction,
    *,
    coefficient_db_m: float = _DEFAULT_PD_COEFFICIENT_DB_M,
    exponent: float = _DEFAULT_PD_EXPONENT,
) -> float:
    """Integrates the induced-loss density along the fiber to give the total
    extra saturated-state loss (dB) a signal would see end-to-end."""
    loss_density = photodarkening_loss_db_m(n2_fraction, coefficient_db_m=coefficient_db_m, exponent=exponent)
    return float(np.trapezoid(loss_density, np.asarray(z_m, dtype=float)))
