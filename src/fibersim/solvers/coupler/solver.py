"""
Fiber directional coupler solver using coupled-mode theory (CMT).

Model: two parallel identical (or near-identical) single-mode step-index fibers
coupled through evanescent field overlap over a coupling length L.

Equations (asymmetric coupler with phase mismatch δ):
    dA₁/dz =  i δ A₁ − i κ A₂
    dA₂/dz = −i δ A₂ − i κ A₁

Solutions for incoherent dual input (P₁₀, P₂₀):
    P₁(z) = P₁₀ [1 − F² sin²(Ωz)] + P₂₀ F² sin²(Ωz)
    P₂(z) = P₁₀ F² sin²(Ωz) + P₂₀ [1 − F² sin²(Ωz)]

where Ω = √(κ² + δ²), F² = κ²/Ω²

Coupling coefficient κ(λ) — Marcuse approximation for LP₀₁ mode:
    κ = (U²/V²) × √(2Δ) / (a × K₁(W)) × K₀(W × d_cc/a)

References:
  - Marcuse, "Theory of Dielectric Optical Waveguides", Academic Press (1991)
  - Okamoto, "Fundamentals of Optical Waveguides", Elsevier (2006) Ch. 4
"""
import numpy as np
from scipy.special import j0, j1, k0, k1
from scipy.optimize import brentq


def _lp01_params(V: float):
    """Find normalized transverse parameters U, W for LP₀₁ mode at V."""
    def _char(U):
        if U <= 0 or U >= V:
            return 1e10
        W = np.sqrt(V**2 - U**2)
        # LP₀₁ characteristic: U J₁(U)/J₀(U) = W K₁(W)/K₀(W)
        return U * j1(U) * k0(W) - W * k1(W) * j0(U)

    try:
        U_sol = brentq(_char, 1e-6, V - 1e-6, xtol=1e-10)
    except ValueError:
        U_sol = V / np.sqrt(2)
    W_sol = np.sqrt(max(V**2 - U_sol**2, 0.0))
    return float(U_sol), float(W_sol)


def _kappa(core_radius_m: float, n_core: float, n_clad: float,
           d_cc_m: float, lambda_m: float) -> float:
    """Coupling coefficient [1/m] between two identical LP₀₁-mode step-index fibers."""
    k0_val = 2.0 * np.pi / lambda_m
    NA2 = n_core**2 - n_clad**2
    if NA2 <= 0:
        return 0.0

    V = k0_val * core_radius_m * np.sqrt(NA2)
    if V < 0.05:
        return 0.0

    U, W = _lp01_params(V)
    if W < 1e-6:
        return 0.0

    Delta = NA2 / (2.0 * n_core**2)
    wd_a = W * d_cc_m / core_radius_m

    kappa_val = (U**2 / V**2) * np.sqrt(2.0 * Delta) / (core_radius_m * k1(W)) * k0(wd_a)
    return float(max(kappa_val, 0.0))


def solve_coupler(
    core_radius_um: float = 4.0,
    n_core: float = 1.4508,
    n_clad: float = 1.45,
    fiber_separation_um: float = 10.0,   # surface-to-surface gap between fibers
    coupling_length_mm: float = 10.0,
    lambda_center_nm: float = 1550.0,
    P1_in_w: float = 1.0,
    P2_in_w: float = 0.0,
    delta_rad_per_m: float = 0.0,        # phase mismatch Δβ/2 for asymmetric coupler
    num_z: int = 500,
    lambda_min_nm: float = 1450.0,
    lambda_max_nm: float = 1650.0,
    num_lambda: int = 200,
) -> dict:
    """
    Solve directional fiber coupler using coupled-mode theory.

    Returns a dict with longitudinal power evolution and spectral response.
    """
    a = core_radius_um * 1e-6
    d_cc = 2.0 * a + fiber_separation_um * 1e-6   # center-to-center distance
    L = coupling_length_mm * 1e-3
    lambda_c = lambda_center_nm * 1e-9

    # ── Coupling coefficient at center wavelength ──────────────────────────
    kappa_c = _kappa(a, n_core, n_clad, d_cc, lambda_c)

    # ── Phase mismatch and effective coupling frequency ────────────────────
    delta = delta_rad_per_m
    Omega = np.sqrt(kappa_c**2 + delta**2)
    F2 = (kappa_c / Omega)**2 if Omega > 0 else 1.0

    # Full coupling length (complete power transfer when delta=0)
    Lc_m = np.pi / (2.0 * Omega) if Omega > 0 else np.inf
    Lc_mm = Lc_m * 1e3

    # ── Longitudinal power evolution ───────────────────────────────────────
    z = np.linspace(0.0, L, num_z)
    sin2 = np.sin(Omega * z) ** 2

    P1_z = P1_in_w * (1.0 - F2 * sin2) + P2_in_w * F2 * sin2
    P2_z = P1_in_w * F2 * sin2 + P2_in_w * (1.0 - F2 * sin2)

    P1_out = float(P1_z[-1])
    P2_out = float(P2_z[-1])
    P_in = P1_in_w + P2_in_w
    splitting_ratio = P2_out / P_in if P_in > 0 else 0.0

    # Throughput/cross port isolation in dB
    throughput_db = 10.0 * np.log10(P1_out / P_in) if (P_in > 0 and P1_out > 0) else -np.inf
    cross_db = 10.0 * np.log10(P2_out / P_in) if (P_in > 0 and P2_out > 0) else -np.inf

    # ── Spectral response ──────────────────────────────────────────────────
    lambdas = np.linspace(lambda_min_nm * 1e-9, lambda_max_nm * 1e-9, num_lambda)
    kappa_lam = np.array([_kappa(a, n_core, n_clad, d_cc, lam) for lam in lambdas])

    Omega_lam = np.sqrt(kappa_lam**2 + delta**2)
    F2_lam = np.where(Omega_lam > 0, (kappa_lam / Omega_lam)**2, 1.0)
    sin2_lam = np.sin(Omega_lam * L) ** 2

    P1_lam = P1_in_w * (1.0 - F2_lam * sin2_lam) + P2_in_w * F2_lam * sin2_lam
    P2_lam = P1_in_w * F2_lam * sin2_lam + P2_in_w * (1.0 - F2_lam * sin2_lam)
    split_lam = np.where(P_in > 0, P2_lam / P_in, 0.0)

    return {
        # Longitudinal results
        'z_mm': z * 1e3,
        'P1_z': P1_z,
        'P2_z': P2_z,
        # Spectral results
        'lambda_nm': lambdas * 1e9,
        'P1_lambda': P1_lam,
        'P2_lambda': P2_lam,
        'kappa_lambda': kappa_lam,
        'splitting_ratio_lambda': split_lam,
        # Summary metrics
        'kappa_c': float(kappa_c),
        'coupling_length_mm': float(Lc_mm),
        'splitting_ratio': float(splitting_ratio),
        'throughput_db': float(throughput_db),
        'cross_db': float(cross_db),
        'P1_out': P1_out,
        'P2_out': P2_out,
    }
