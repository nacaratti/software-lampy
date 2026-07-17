"""
Tapered fiber solver — local mode (adiabatic) analysis.

Models a biconical taper (down-taper → flat waist → up-taper).
The cladding tapers proportionally with the core.

Mode field diameters — three definitions (matching RP Fiber Power):
  w₂     – second-moment (Petermann I):   w₂² = ∫r³|ψ|²dr / ∫r|ψ|²dr
  w_eff  – effective area (Petermann II): w_eff = √(A_eff/π)
  w_HWHM – half-width at half maximum of |ψ|²

Adiabaticity criterion (Love & Henry, Electron. Lett. 1986):
  η(z) = Ω(z) / Ω_c(z)
  Ω(z)   = |dr_core/dz|             local taper half-angle [dimensionless]
  Ω_c(z) = r_core × |β₁−β₂| / 2π  critical angle
  η ≪ 1 → adiabatic;  η ≫ 1 → non-adiabatic

Transmission (Born approximation):
  T = exp(−∫ α dz),  α = (π/2) η² / z_b × w_rad
  w_rad → 1 only when V_clad < V_RAD (cladding near cutoff → irreversible loss).
  For symmetric biconical tapers with large cladding V_clad ≫ 1 everywhere
  → cladding always guides → power recoverable on up-taper → T ≈ 1.

References:
  Love & Henry, Electron. Lett. 22 (1986) 79–81
  Birks & Li, J. Lightwave Technol. 10 (1992) 432–438
  Marcuse, BSTJ 56 (1977) 703–718
"""
import math
import numpy as np
from scipy.special import j0, j1, k0, k1, jv, kv
from scipy.optimize import brentq

try:
    _trapz = np.trapezoid
except AttributeError:
    _trapz = np.trapz

# ── Mode parameter solvers ─────────────────────────────────────────────────

def _lp01_params(V: float):
    def _char(U):
        if U <= 0 or U >= V:
            return 1e10
        W = math.sqrt(V * V - U * U)
        return U * j1(U) * k0(W) - W * k1(W) * j0(U)
    try:
        U_sol = brentq(_char, 1e-6, V - 1e-6, xtol=1e-10)
    except ValueError:
        U_sol = V / math.sqrt(2)
    W_sol = math.sqrt(max(V * V - U_sol * U_sol, 0.0))
    return float(U_sol), float(W_sol)


def _lp11_params(V: float):
    """Returns (U, W) for LP₁₁ or None if V ≤ 2.405 (cut-off)."""
    if V <= 2.405:
        return None
    def _char(U):
        if U <= 0 or U >= V:
            return 1e10
        W = math.sqrt(V * V - U * U)
        return U * jv(2, U) * k1(W) - W * kv(2, W) * j1(U)
    try:
        U_sol = brentq(_char, 1e-6, V - 1e-6, xtol=1e-10)
    except ValueError:
        return None
    W_sol = math.sqrt(max(V * V - U_sol * U_sol, 0.0))
    return float(U_sol), float(W_sol)


# ── Beam radii (numerical quadrature on the LP₀₁ field) ───────────────────

def _beam_radii(U: float, W: float, a: float):
    """
    Three MFD definitions for LP₀₁ with core radius a.
    Returns (w2, w_eff, w_hwhm, A_eff), all in meters.
    """
    N_r = 2000
    # Extend grid to capture evanescent tail; more important for small W
    r_max = max(60.0 * a, 2e-4)
    r = np.linspace(0.0, r_max, N_r)
    dr = r[1] - r[0]

    # Safe ratio for field continuity at r=a
    k0W = k0(W)
    ratio = j0(U) / k0W if k0W > 1e-30 else 0.0

    # Clip large K₀ values to avoid NaN (happens when W→0 and r/a→∞)
    clad_arg = W * r / a
    # Only compute K₀ where clad_arg is in a safe range (< 700 avoids underflow)
    clad_field = np.where(
        r <= a,
        j0(U * r / a),
        np.where(clad_arg < 700.0, ratio * k0(np.clip(clad_arg, 1e-30, 700.0)), 0.0)
    )
    I = clad_field * clad_field

    denom = float(_trapz(r * I, r))
    if denom <= 0:
        return a, a, a, math.pi * a * a

    w2 = math.sqrt(float(_trapz(r * r * r * I, r)) / denom)

    num_eff = float(_trapz(r * I, r)) ** 2
    den_eff = float(_trapz(r * I * I, r))
    A_eff = (2.0 * math.pi * num_eff / den_eff) if den_eff > 0 else math.pi * a * a
    w_eff = math.sqrt(A_eff / math.pi)

    I_half = 0.5 * I[0]
    crossings = np.where(np.diff(np.sign(I - I_half)))[0]
    if len(crossings) > 0:
        idx = int(crossings[0])
        dI = I[idx + 1] - I[idx]
        w_hwhm = r[idx] + (I_half - I[idx]) / dI * dr if abs(dI) > 0 else r[idx]
    else:
        w_hwhm = w2

    return float(w2), float(w_eff), float(w_hwhm), float(A_eff)


# ── Taper profile ──────────────────────────────────────────────────────────

def _taper_profile(z: np.ndarray, r0: float, rho: float,
                   L_down: float, L_waist: float, shape: str) -> np.ndarray:
    """Biconical taper: down → waist → up.  rho = r_waist/r0 ∈ (0,1]."""
    r = np.empty_like(z)
    for i, zi in enumerate(z):
        if zi <= 0.0 or L_down == 0.0:
            r[i] = r0
        elif zi < L_down:
            s = zi / L_down
            if shape == 'cosine':
                t = rho + (1.0 - rho) * 0.5 * (1.0 + math.cos(math.pi * s))
            elif shape == 'linear':
                t = 1.0 - (1.0 - rho) * s
            else:   # exponential
                t = math.exp(math.log(max(rho, 1e-9)) * s)
            r[i] = r0 * t
        elif zi <= L_down + L_waist:
            r[i] = r0 * rho
        elif zi < 2.0 * L_down + L_waist:
            s = (zi - L_down - L_waist) / L_down
            if shape == 'cosine':
                t = rho + (1.0 - rho) * 0.5 * (1.0 - math.cos(math.pi * s))
            elif shape == 'linear':
                t = rho + (1.0 - rho) * s
            else:
                t = math.exp(math.log(max(rho, 1e-9)) * (1.0 - s))
            r[i] = r0 * t
        else:
            r[i] = r0
    return r


# ── Main solver ────────────────────────────────────────────────────────────

def solve_taper(
    core_radius_um: float = 4.0,
    clad_radius_um: float = 62.5,
    n_core: float = 1.4681,       # SMF-28 like (NA ≈ 0.12, V ≈ 2.0 at 1550 nm)
    n_clad: float = 1.4629,
    taper_ratio: float = 0.1,     # r_waist / r₀
    L_taper_mm: float = 30.0,     # length of each taper arm (down or up)
    L_waist_mm: float = 5.0,      # flat waist length
    taper_shape: str = 'cosine',  # 'cosine' | 'linear' | 'exponential'
    lambda_nm: float = 1550.0,
    num_z: int = 800,
) -> dict:
    if not (0 < taper_ratio <= 1):
        raise ValueError("taper_ratio must be in (0, 1]")
    if n_core <= n_clad:
        raise ValueError("n_core must be > n_clad")

    r0      = core_radius_um * 1e-6
    rclad0  = clad_radius_um * 1e-6
    lam     = lambda_nm * 1e-9
    k0v     = 2.0 * math.pi / lam

    NA_core = math.sqrt(n_core ** 2 - n_clad ** 2)    # core/cladding
    NA_clad = math.sqrt(max(n_clad ** 2 - 1.0, 0.0))  # cladding/air

    L_down  = L_taper_mm * 1e-3
    L_waist = L_waist_mm * 1e-3
    L_total = 2.0 * L_down + L_waist

    z       = np.linspace(0.0, L_total, num_z)
    r_core  = _taper_profile(z, r0, taper_ratio, L_down, L_waist, taper_shape)
    r_clad  = r_core * (rclad0 / r0)

    V_core  = k0v * r_core * NA_core
    V_clad  = k0v * r_clad * NA_clad if NA_clad > 0 else np.zeros_like(r_clad)

    dr_dz   = np.gradient(r_core, z)
    omega   = np.abs(dr_dz)   # local taper half-angle = |dr_core/dz|

    V_CLIP  = 0.05   # below this: treat as unguided in core
    BIG_MFD = 400e-6

    n_pts   = len(z)
    beta1    = np.zeros(n_pts)
    beta2    = np.zeros(n_pts)
    mfd_w2   = np.zeros(n_pts)
    mfd_eff  = np.zeros(n_pts)
    mfd_hwhm = np.zeros(n_pts)
    A_eff_z  = np.zeros(n_pts)
    is_lp11  = np.zeros(n_pts, dtype=bool)
    in_clad  = np.zeros(n_pts, dtype=bool)

    for i in range(n_pts):
        Vc   = float(V_core[i])
        Vcl  = float(V_clad[i])
        rc   = float(r_core[i])
        rcl  = float(r_clad[i])

        # ── MFD: use core LP₀₁ while core is still meaningful;
        #         switch to cladding LP₀₁ only when core is essentially gone
        if Vc >= V_CLIP:
            U01, W01 = _lp01_params(Vc)
            beta1[i] = math.sqrt(max((k0v * n_core) ** 2 - (U01 / rc) ** 2, 0.0))
            w2, weff, whwhm, Aeff = _beam_radii(U01, W01, rc)
            mfd_w2[i] = w2; mfd_eff[i] = weff; mfd_hwhm[i] = whwhm; A_eff_z[i] = Aeff
            in_clad[i] = False

        elif Vcl >= V_CLIP:
            # Core gone; use cladding waveguide
            U01, W01 = _lp01_params(max(Vcl, V_CLIP))
            beta1[i] = math.sqrt(max((k0v * n_clad) ** 2 - (U01 / rcl) ** 2, 0.0))
            w2, weff, whwhm, Aeff = _beam_radii(U01, W01, rcl)
            mfd_w2[i] = w2; mfd_eff[i] = weff; mfd_hwhm[i] = whwhm; A_eff_z[i] = Aeff
            in_clad[i] = True

        else:
            # Essentially unguided
            beta1[i] = k0v * n_clad
            mfd_w2[i] = mfd_eff[i] = mfd_hwhm[i] = BIG_MFD
            A_eff_z[i] = math.pi * BIG_MFD ** 2
            in_clad[i] = True

        # ── β₂: next relevant mode ──────────────────────────────────────
        V_for_lp11 = Vc if not in_clad[i] else Vcl
        n_in_wg    = n_core if not in_clad[i] else n_clad
        r_for_lp11 = rc if not in_clad[i] else rcl

        lp11 = _lp11_params(V_for_lp11)
        if lp11 is not None:
            U11, _ = lp11
            b11 = math.sqrt(max((k0v * n_in_wg) ** 2 - (U11 / r_for_lp11) ** 2, 0.0))
            beta2[i] = b11
            is_lp11[i] = True
        else:
            # No LP₁₁; next mode is cladding / radiation
            beta2[i] = k0v * (n_clad if not in_clad[i] else 1.0)

    # MFD in μm (diameter = 2 × radius)
    mfd_w2_um    = mfd_w2   * 2e6
    mfd_weff_um  = mfd_eff  * 2e6
    mfd_hwhm_um  = mfd_hwhm * 2e6

    # ── Adiabaticity ───────────────────────────────────────────────────────
    d_beta  = np.abs(beta1 - beta2)
    z_beat  = np.where(d_beta > 0.1, 2.0 * math.pi / d_beta, 1e3)
    omega_c = r_core * d_beta / (2.0 * math.pi)
    eta     = np.where(omega_c > 1e-20, omega / omega_c, 0.0)

    # ── Transmission estimate ──────────────────────────────────────────────
    # Loss is irreversible only when the cladding near cutoff (V_clad → 0).
    V_RAD = 2.5
    rad_weight = np.clip(1.0 - V_clad / V_RAD, 0.0, 1.0)
    alpha_loss = (math.pi / 2.0) * eta ** 2 / np.maximum(z_beat, 1e-6) * rad_weight

    T_est = max(float(np.exp(-_trapz(alpha_loss, z))), 0.0)
    T_db  = 10.0 * math.log10(max(T_est, 1e-12))

    # ── Summary scalars ────────────────────────────────────────────────────
    mid = int(np.argmin(r_core))
    return {
        # z-dependent arrays
        'z_mm':              z * 1e3,
        'r_core_um':         r_core * 1e6,
        'r_clad_um':         r_clad * 1e6,
        'V_core':            V_core,
        'V_clad':            V_clad,
        'mfd_w2_um':         mfd_w2_um,
        'mfd_weff_um':       mfd_weff_um,
        'mfd_hwhm_um':       mfd_hwhm_um,
        'A_eff_um2':         A_eff_z * 1e12,
        'taper_angle_mrad':  omega * 1e3,
        'omega_c_mrad':      omega_c * 1e3,
        'eta':               eta,
        'z_beat_mm':         z_beat * 1e3,
        'is_lp11':           is_lp11,
        'in_cladding_mode':  in_clad,
        # Scalars
        'V_input':           float(V_core[0]),
        'V_waist':           float(V_core[mid]),
        'V_clad_input':      float(V_clad[0]),
        'V_clad_waist':      float(V_clad[mid]),
        'mfd_input_um':      float(mfd_w2_um[0]),
        'mfd_waist_um':      float(mfd_w2_um[mid]),
        'max_eta':           float(np.max(eta)),
        'is_adiabatic':      bool(np.max(eta) < 0.1),
        'transmission':      T_est,
        'transmission_db':   T_db,
        'L_total_mm':        float(L_total * 1e3),
        'lp11_filtered':     bool(any(is_lp11) and not is_lp11[mid]),
    }
