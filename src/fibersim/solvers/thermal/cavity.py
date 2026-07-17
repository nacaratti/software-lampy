"""
Yb-doped fiber laser cavity solver — translation of the MATLAB reference
model from `fiber_laser_matlab_models.py`.

Models a FBG-based cladding-pumped Yb fiber laser cavity with two reflectors
(R1 at z=0, R2 at z=L). Output coupler is R2 → P_out = (1 - R2) * P_signal_forward.

Two solver methods are provided:
- 'analytical': closed-form steady-state solution (forward / backward / two-end pumping)
- 'rk4':        Runge-Kutta 4 with shooting method + Newton-Raphson on cavity BCs

The thermal solver is the 3-layer cylindrical model (core / cladding / coating).
"""

import numpy as np

# Physical constants
H_PLANCK = 6.62607015e-34  # J·s
C_LIGHT = 299792458.0       # m/s
SIGMA_BOLTZMANN = 5.670374419e-8  # W/(m²·K⁴)


# ------------------------------------------------------------------
# Closed-form analytical solvers (MATLAB translation)
# ------------------------------------------------------------------

def _analytical_constants(A_core, Ts, Tp, sigma_es, sigma_as, sigma_ap,
                          alpha_p_bg, lambda_p, lambda_s, N_total, tau):
    v_s = C_LIGHT / lambda_s
    v_p = C_LIGHT / lambda_p
    pssat = (H_PLANCK * v_s * A_core) / (Ts * tau * (sigma_es + sigma_as))
    alpha = (Tp * sigma_ap * N_total) + alpha_p_bg
    s_ratio = lambda_p / lambda_s
    return v_s, v_p, pssat, alpha, s_ratio


def _forward_analytical(z, L, A_core, Ts, Tp,
                        sigma_es, sigma_as, sigma_ep, sigma_ap,
                        alpha_p_bg, alpha_s_bg,
                        R1, R2, N_total, tau, lambda_p, lambda_s,
                        P_pump_forward):
    """Forward-pumped FBG cavity (closed-form)."""
    v_s, v_p, pssat, alpha, _ = _analytical_constants(
        A_core, Ts, Tp, sigma_es, sigma_as, sigma_ap, alpha_p_bg,
        lambda_p, lambda_s, N_total, tau,
    )

    ppma0 = 0.0
    K = ((1.0 / L) * np.log(1.0 / np.sqrt(R1 * R2)) +
         (sigma_as * Ts * N_total + alpha_s_bg) * L) / \
        ((sigma_es + sigma_as) * L)

    term1 = (np.sqrt(R2) * pssat) / \
            ((1.0 - R1) * np.sqrt(R2) + (1.0 - R2) * np.sqrt(R1))
    term2 = (v_s / v_p) * (1.0 - (alpha_p_bg / alpha)) * \
            (1.0 - np.exp(-alpha * L)) * ((P_pump_forward + ppma0) / pssat)
    term3 = (N_total * Ts * sigma_as) * L
    term4 = np.log(1.0 / np.sqrt(R1 * R2))
    psma0 = term1 * (term2 - term3 - term4)

    ppmo = P_pump_forward * np.exp(-(Tp * sigma_ap * N_total + alpha_p_bg) * z)
    ppma = np.zeros_like(z)

    B1 = (1.0 - R1) * psma0
    B2 = (v_s / v_p) * (1.0 - alpha_p_bg / alpha) * (1.0 - np.exp(alpha * z))
    B3 = ppmo
    B4 = (H_PLANCK * v_s * A_core * K * z) / tau

    B = B1 + B2 * B3 + B4
    sqrt_term = np.sqrt(B**2 + 4.0 * R1 * (psma0**2))
    psmo = (-B + sqrt_term) / 2.0
    psma = (B + sqrt_term) / 2.0
    pout = (1.0 - R2) * psmo

    return ppmo, ppma, psmo, psma, pout


def _backward_analytical(z, L, A_core, Ts, Tp,
                         sigma_es, sigma_as, sigma_ep, sigma_ap,
                         alpha_p_bg, alpha_s_bg,
                         R1, R2, N_total, tau, lambda_p, lambda_s,
                         P_pump_backward):
    """Backward-pumped FBG cavity (closed-form)."""
    v_s, v_p, pssat, alpha, _ = _analytical_constants(
        A_core, Ts, Tp, sigma_es, sigma_as, sigma_ap, alpha_p_bg,
        lambda_p, lambda_s, N_total, tau,
    )

    ppmo0 = 0.0
    K = ((1.0 / L) * np.log(1.0 / np.sqrt(R1 * R2)) +
         (sigma_as * Ts * N_total + alpha_s_bg) * L) / \
        ((sigma_es + sigma_as) * L)

    ppma = P_pump_backward * np.exp((Tp * sigma_ap * N_total + alpha_p_bg) * (z - L))
    ppmo = np.zeros_like(z)

    term1 = (np.sqrt(R2) * pssat) / \
            ((1.0 - R1) * np.sqrt(R2) + (1.0 - R2) * np.sqrt(R1))
    term2 = (v_s / v_p) * (1.0 - (alpha_p_bg / alpha)) * \
            (1.0 - np.exp(-alpha * L)) * ((ppmo0 + ppma[-1]) / pssat)
    term3 = (N_total * Ts * sigma_as + alpha_s_bg) * L
    term4 = np.log(1.0 / np.sqrt(R1 * R2))
    psma0 = term1 * (term2 - term3 - term4)

    B1 = (1.0 - R1) * psma0
    B2 = (v_s / v_p) * (1.0 - alpha_p_bg / alpha) * (1.0 - np.exp(alpha * z))
    B3 = ppma[-1] * np.exp(-alpha * L)
    B4 = (H_PLANCK * v_s * A_core * K * z) / tau

    B = B1 + B2 * B3 + B4
    sqrt_term = np.sqrt(B**2 + 4.0 * R1 * (psma0**2))
    psmo = (-B + sqrt_term) / 2.0
    psma = (B + sqrt_term) / 2.0
    pout = (1.0 - R2) * psmo

    return ppmo, ppma, psmo, psma, pout


def _two_end_analytical(z, L, A_core, Ts, Tp,
                        sigma_es, sigma_as, sigma_ep, sigma_ap,
                        alpha_p_bg, alpha_s_bg,
                        R1, R2, N_total, tau, lambda_p, lambda_s,
                        P_pump_forward, P_pump_backward):
    """Two-end (bidirectional) pumped FBG cavity (closed-form)."""
    v_s, v_p, pssat, alpha, _ = _analytical_constants(
        A_core, Ts, Tp, sigma_es, sigma_as, sigma_ap, alpha_p_bg,
        lambda_p, lambda_s, N_total, tau,
    )

    K = ((1.0 / L) * np.log(1.0 / np.sqrt(R1 * R2)) +
         (sigma_as * Ts * N_total + alpha_s_bg) * L) / \
        ((sigma_es + sigma_as) * L)

    term1 = (np.sqrt(R2) * pssat) / \
            ((1.0 - R1) * np.sqrt(R2) + (1.0 - R2) * np.sqrt(R1))
    term2 = (v_s / v_p) * (1.0 - (alpha_p_bg / alpha)) * \
            (1.0 - np.exp(-alpha * L)) * ((P_pump_forward + P_pump_backward) / pssat)
    term3 = (N_total * Ts * sigma_as + alpha_s_bg) * L
    term4 = np.log(1.0 / np.sqrt(R1 * R2))
    psma0 = term1 * (term2 - term3 - term4)

    ppmo = P_pump_forward * np.exp(-(Tp * sigma_ap * N_total + alpha_p_bg) * z)
    ppma = P_pump_backward * np.exp((Tp * sigma_ap * N_total + alpha_p_bg) * (z - L))

    B1 = psma0 * (1.0 - R1)
    B2 = (v_s / v_p) * ((P_pump_forward * np.exp(-alpha * z)
                         + P_pump_backward * np.exp(-alpha * L)) *
                        (1.0 - alpha_p_bg / alpha))
    B3 = (1.0 - np.exp(alpha * z))
    B4 = (H_PLANCK * v_s * A_core * K * z) / tau

    B = B1 + B2 * B3 + B4
    sqrt_term = np.sqrt(B**2 + 4.0 * R1 * (psma0**2))
    psmo = (-B + sqrt_term) / 2.0
    psma = (B + sqrt_term) / 2.0
    pout = (1.0 - R2) * psmo

    return ppmo, ppma, psmo, psma, pout


# ------------------------------------------------------------------
# RK4 shooting solvers (MATLAB translation)
# ------------------------------------------------------------------

def _rk4_step_kernel(z_val, p_f, p_b, hh_step, pump_term,
                     sigma_es, tau, sigma_ap_alpha_a, Tp, A_core,
                     v_p, alpha_s_bg, p0=0.0, pss=None):
    """Common stage helper — returns (k_f, k_b)."""
    term_denom = 1.0 + ((p_f + p_b) / pss)
    common = ((sigma_es * tau) / (H_PLANCK * v_p)) * \
              sigma_ap_alpha_a * pump_term * (Tp / A_core)
    k_f = hh_step * (common * ((p0 + p_f) / term_denom) - alpha_s_bg * p_f)
    k_b = hh_step * (-common * ((p0 + p_b) / term_denom) + alpha_s_bg * p_b)
    return k_f, k_b


def _rk4_forward(L, A_core, Ts, Tp,
                 sigma_es, sigma_as, sigma_ap,
                 alpha_p_bg, alpha_s_bg,
                 R1, R2, N_total, tau, lambda_p, lambda_s,
                 P_pump_forward, num_steps=86, max_iter=10000, tol=1e-10):
    v_p = C_LIGHT / lambda_p
    v_s = C_LIGHT / lambda_s
    alpha_a = N_total * sigma_ap
    pss = ((H_PLANCK * v_s) / (sigma_es * tau)) * A_core

    deltap = 0.0
    p_sigb0 = 1.0
    psig_f = np.zeros(num_steps)
    psig_b = np.zeros(num_steps)
    zz = np.zeros(num_steps)

    hh = L / (num_steps - 1)
    converged = False
    error = float('inf')

    def pump_at(z_val):
        return P_pump_forward * np.exp(-((alpha_a * Tp) + alpha_p_bg) * z_val)

    for _ in range(max_iter):
        p_sigb0 = deltap + p_sigb0
        f_vals = np.zeros(2)

        for j in range(2):
            p_sigb = p_sigb0 + j * 0.001
            p_sigf = p_sigb * R1

            for x in range(num_steps):
                z1 = x * hh

                term_exp = np.exp(-((alpha_a * Tp) + alpha_p_bg) * z1)
                pump_term_1 = P_pump_forward * term_exp
                k1, k11 = _rk4_step_kernel(z1, p_sigf, p_sigb, hh, pump_term_1,
                                            sigma_es, tau, alpha_a, Tp, A_core,
                                            v_p, alpha_s_bg, pss=pss)

                z2 = z1 + hh / 2
                term_exp = np.exp(-((alpha_a * Tp) + alpha_p_bg) * z2)
                pump_term_2 = P_pump_forward * term_exp
                k2, k22 = _rk4_step_kernel(z2, p_sigf + 0.5*k1, p_sigb + 0.5*k11,
                                            hh, pump_term_2,
                                            sigma_es, tau, alpha_a, Tp, A_core,
                                            v_p, alpha_s_bg, pss=pss)

                k3, k33 = _rk4_step_kernel(z2, p_sigf + 0.5*k2, p_sigb + 0.5*k22,
                                            hh, pump_term_2,
                                            sigma_es, tau, alpha_a, Tp, A_core,
                                            v_p, alpha_s_bg, pss=pss)

                z4 = z1 + hh
                term_exp = np.exp(-((alpha_a * Tp) + alpha_p_bg) * z4)
                pump_term_4 = P_pump_forward * term_exp
                k4, k44 = _rk4_step_kernel(z4, p_sigf + k3, p_sigb + k33,
                                            hh, pump_term_4,
                                            sigma_es, tau, alpha_a, Tp, A_core,
                                            v_p, alpha_s_bg, pss=pss)

                p_sigf = p_sigf + (k1 + 2*k2 + 2*k3 + k4) / 6.0
                p_sigb = p_sigb + (k11 + 2*k22 + 2*k33 + k44) / 6.0

                psig_f[x] = p_sigf
                psig_b[x] = p_sigb
                zz[x] = z1

            f_vals[j] = psig_b[-1] / psig_f[-1] if psig_f[-1] != 0 else 0.0

        m = (f_vals[1] - f_vals[0]) / 0.001 if (f_vals[1] - f_vals[0]) != 0 else 1.0
        error = abs(R2 - f_vals[0])
        deltap = (R2 - f_vals[0]) / m

        if error < tol:
            converged = True
            break

    ppp = P_pump_forward * np.exp(-((alpha_a * Tp) + alpha_p_bg) * zz)
    return zz, psig_f, psig_b, ppp, converged


def _rk4_backward(L, A_core, Ts, Tp,
                  sigma_es, sigma_as, sigma_ap,
                  alpha_p_bg, alpha_s_bg,
                  R1, R2, N_total, tau, lambda_p, lambda_s,
                  P_pump_backward, num_steps=86, max_iter=10000, tol=1e-10):
    v_p = C_LIGHT / lambda_p
    v_s = C_LIGHT / lambda_s
    alpha_a = N_total * sigma_ap
    pss = ((H_PLANCK * v_s) / (sigma_es * tau)) * A_core

    deltap = 0.0
    p_sigb0 = 1.0
    psig_f = np.zeros(num_steps)
    psig_b = np.zeros(num_steps)
    zz = np.zeros(num_steps)

    hh = L / (num_steps - 1)
    converged = False
    error = float('inf')

    for _ in range(max_iter):
        p_sigb0 = deltap + p_sigb0
        f_vals = np.zeros(2)

        for j in range(2):
            p_sigb = p_sigb0 + j * 0.001
            p_sigf = p_sigb * R1

            for x in range(num_steps):
                z1 = x * hh

                pump_term_1 = P_pump_backward * np.exp(-((alpha_a * Tp) + alpha_p_bg) * (L - z1))
                k1, k11 = _rk4_step_kernel(z1, p_sigf, p_sigb, hh, pump_term_1,
                                            sigma_es, tau, alpha_a, Tp, A_core,
                                            v_p, alpha_s_bg, pss=pss)

                z2 = z1 + hh / 2
                pump_term_2 = P_pump_backward * np.exp(-((alpha_a * Tp) + alpha_p_bg) * (L - z2))
                k2, k22 = _rk4_step_kernel(z2, p_sigf + 0.5*k1, p_sigb + 0.5*k11,
                                            hh, pump_term_2,
                                            sigma_es, tau, alpha_a, Tp, A_core,
                                            v_p, alpha_s_bg, pss=pss)

                k3, k33 = _rk4_step_kernel(z2, p_sigf + 0.5*k2, p_sigb + 0.5*k22,
                                            hh, pump_term_2,
                                            sigma_es, tau, alpha_a, Tp, A_core,
                                            v_p, alpha_s_bg, pss=pss)

                z4 = z1 + hh
                pump_term_4 = P_pump_backward * np.exp(-((alpha_a * Tp) + alpha_p_bg) * (L - z4))
                k4, k44 = _rk4_step_kernel(z4, p_sigf + k3, p_sigb + k33,
                                            hh, pump_term_4,
                                            sigma_es, tau, alpha_a, Tp, A_core,
                                            v_p, alpha_s_bg, pss=pss)

                p_sigf = p_sigf + (k1 + 2*k2 + 2*k3 + k4) / 6.0
                p_sigb = p_sigb + (k11 + 2*k22 + 2*k33 + k44) / 6.0

                psig_f[x] = p_sigf
                psig_b[x] = p_sigb
                zz[x] = z1

            f_vals[j] = psig_b[-1] / psig_f[-1] if psig_f[-1] != 0 else 0.0

        m = (f_vals[1] - f_vals[0]) / 0.001 if (f_vals[1] - f_vals[0]) != 0 else 1.0
        error = abs(R2 - f_vals[0])
        deltap = (R2 - f_vals[0]) / m

        if error < tol:
            converged = True
            break

    ppp = P_pump_backward * np.exp(-((alpha_a * Tp) + alpha_p_bg) * (L - zz))
    return zz, psig_f, psig_b, ppp, converged


def _rk4_two_end(L, A_core, Ts, Tp,
                 sigma_es, sigma_as, sigma_ap,
                 alpha_p_bg, alpha_s_bg,
                 R1, R2, N_total, tau, lambda_p, lambda_s,
                 P_pump_forward, P_pump_backward, num_steps=86,
                 max_iter=10000, tol=1e-10):
    v_p = C_LIGHT / lambda_p
    v_s = C_LIGHT / lambda_s
    alpha_a = N_total * sigma_ap
    pss = ((H_PLANCK * v_s) / (sigma_es * tau)) * A_core

    deltap = 0.0
    p_sigb0 = 1.0
    psig_f = np.zeros(num_steps)
    psig_b = np.zeros(num_steps)
    zz = np.zeros(num_steps)

    hh = L / (num_steps - 1)
    converged = False
    error = float('inf')

    def pump_term_at(z_val):
        ef = np.exp(-((alpha_a * Tp) + alpha_p_bg) * z_val)
        eb = np.exp(-((alpha_a * Tp) + alpha_p_bg) * (L - z_val))
        return P_pump_forward * ef + P_pump_backward * eb

    for _ in range(max_iter):
        p_sigb0 = deltap + p_sigb0
        f_vals = np.zeros(2)

        for j in range(2):
            p_sigb = p_sigb0 + j * 0.001
            p_sigf = p_sigb * R1

            for x in range(num_steps):
                z1 = x * hh

                k1, k11 = _rk4_step_kernel(z1, p_sigf, p_sigb, hh, pump_term_at(z1),
                                            sigma_es, tau, alpha_a, Tp, A_core,
                                            v_p, alpha_s_bg, pss=pss)

                z2 = z1 + hh / 2
                pt2 = pump_term_at(z2)
                k2, k22 = _rk4_step_kernel(z2, p_sigf + 0.5*k1, p_sigb + 0.5*k11,
                                            hh, pt2,
                                            sigma_es, tau, alpha_a, Tp, A_core,
                                            v_p, alpha_s_bg, pss=pss)

                k3, k33 = _rk4_step_kernel(z2, p_sigf + 0.5*k2, p_sigb + 0.5*k22,
                                            hh, pt2,
                                            sigma_es, tau, alpha_a, Tp, A_core,
                                            v_p, alpha_s_bg, pss=pss)

                z4 = z1 + hh
                k4, k44 = _rk4_step_kernel(z4, p_sigf + k3, p_sigb + k33,
                                            hh, pump_term_at(z4),
                                            sigma_es, tau, alpha_a, Tp, A_core,
                                            v_p, alpha_s_bg, pss=pss)

                p_sigf = p_sigf + (k1 + 2*k2 + 2*k3 + k4) / 6.0
                p_sigb = p_sigb + (k11 + 2*k22 + 2*k33 + k44) / 6.0

                psig_f[x] = p_sigf
                psig_b[x] = p_sigb
                zz[x] = z1

            f_vals[j] = psig_b[-1] / psig_f[-1] if psig_f[-1] != 0 else 0.0

        m = (f_vals[1] - f_vals[0]) / 0.001 if (f_vals[1] - f_vals[0]) != 0 else 1.0
        error = abs(R2 - f_vals[0])
        deltap = (R2 - f_vals[0]) / m

        if error < tol:
            converged = True
            break

    ppp_f = P_pump_forward * np.exp(-((alpha_a * Tp) + alpha_p_bg) * zz)
    ppp_b = P_pump_backward * np.exp(-((alpha_a * Tp) + alpha_p_bg) * (L - zz))
    return zz, psig_f, psig_b, ppp_f, ppp_b, converged


# ------------------------------------------------------------------
# Public interface
# ------------------------------------------------------------------

def solve_laser_rate_equations(
    fiber_length=13.0,
    core_radius=7.5e-6,   # 15 μm diameter (MATLAB default core_diam = 15e-6)
    clad_radius=100e-6,   # 200 μm clad diameter
    coating_radius=125e-6,
    N_total=6e25,
    tau=1e-3,
    lambda_pump=976e-9,
    lambda_signal=1018e-9,
    # Cross-sections — MATLAB defaults (cladding-pumped Yb)
    sigma_abs_pump=2.8e-24,
    sigma_em_pump=1.8e-27,
    sigma_abs_signal=3.5e-27,
    sigma_em_signal=6.5e-25,
    # Overlap (Ts / Tp in MATLAB)
    gamma_pump=0.0025,    # Tp — small for cladding pump
    gamma_signal=0.82,    # Ts — typical for signal in core
    # Background propagation losses
    alpha_p_bg=0.003,
    alpha_s_bg=0.005,
    # FBG cavity reflectivities
    R1=0.99,
    R2=0.04,
    # Pump powers
    P_pump_forward=10.0,
    P_pump_backward=0.0,
    P_signal_seed=1e-6,   # kept for API compatibility (unused: signal is internal cavity)
    pumping="forward",
    method="analytical",
    num_points=500,
):
    """
    FBG-cavity Yb fiber laser solver — MATLAB reference translation.

    Parameters mirror `fiber_laser_matlab_models.MatlabFiberConfig`:
    - `gamma_pump`/`gamma_signal` correspond to MATLAB `Tp`/`Ts` (overlap factors).
    - `alpha_p_bg`/`alpha_s_bg` are background propagation losses (1/m).
    - `R1`/`R2` are FBG reflectivities at z=0 and z=L. Output is (1-R2)·P_s_fwd(L).
    - `core_radius` is the radius (m). MATLAB uses diameter; A_core = π·r².
    - `method`: 'analytical' (closed-form) or 'rk4' (shooting + Newton-Raphson).
    """
    pumping = (pumping or "forward").lower()
    method = (method or "analytical").lower()

    L = float(fiber_length)
    A_core = np.pi * core_radius**2
    Ts = float(gamma_signal)
    Tp = float(gamma_pump)

    # Build z grid (analytical can use any spacing; RK4 uses its own internal step)
    z = np.linspace(0.0, L, num_points)

    if method == "analytical":
        if pumping == "forward":
            ppmo, ppma, psmo, psma, pout = _forward_analytical(
                z, L, A_core, Ts, Tp,
                sigma_em_signal, sigma_abs_signal, sigma_em_pump, sigma_abs_pump,
                alpha_p_bg, alpha_s_bg,
                R1, R2, N_total, tau, lambda_pump, lambda_signal,
                P_pump_forward,
            )
        elif pumping == "backward":
            ppmo, ppma, psmo, psma, pout = _backward_analytical(
                z, L, A_core, Ts, Tp,
                sigma_em_signal, sigma_abs_signal, sigma_em_pump, sigma_abs_pump,
                alpha_p_bg, alpha_s_bg,
                R1, R2, N_total, tau, lambda_pump, lambda_signal,
                P_pump_backward,
            )
        else:  # bidirectional / two-end
            ppmo, ppma, psmo, psma, pout = _two_end_analytical(
                z, L, A_core, Ts, Tp,
                sigma_em_signal, sigma_abs_signal, sigma_em_pump, sigma_abs_pump,
                alpha_p_bg, alpha_s_bg,
                R1, R2, N_total, tau, lambda_pump, lambda_signal,
                P_pump_forward, P_pump_backward,
            )
        used_method = "analytical"

    else:  # method == "rk4"
        # RK4 uses a fixed-step internal grid (default 86 steps, MATLAB choice)
        # Then interpolate to user-requested z grid.
        if pumping == "forward":
            zz, psig_f, psig_b, ppp, conv = _rk4_forward(
                L, A_core, Ts, Tp,
                sigma_em_signal, sigma_abs_signal, sigma_abs_pump,
                alpha_p_bg, alpha_s_bg,
                R1, R2, N_total, tau, lambda_pump, lambda_signal,
                P_pump_forward, num_steps=num_points,
            )
            ppmo = np.interp(z, zz, ppp)
            ppma = np.zeros_like(z)
            psmo = np.interp(z, zz, psig_f)
            psma = np.interp(z, zz, psig_b)
            pout = (1.0 - R2) * psmo
            used_method = "rk4" if conv else "rk4 (not converged)"
        elif pumping == "backward":
            zz, psig_f, psig_b, ppp, conv = _rk4_backward(
                L, A_core, Ts, Tp,
                sigma_em_signal, sigma_abs_signal, sigma_abs_pump,
                alpha_p_bg, alpha_s_bg,
                R1, R2, N_total, tau, lambda_pump, lambda_signal,
                P_pump_backward, num_steps=num_points,
            )
            ppmo = np.zeros_like(z)
            ppma = np.interp(z, zz, ppp)
            psmo = np.interp(z, zz, psig_f)
            psma = np.interp(z, zz, psig_b)
            pout = (1.0 - R2) * psmo
            used_method = "rk4" if conv else "rk4 (not converged)"
        else:  # bidirectional
            zz, psig_f, psig_b, ppp_f, ppp_b, conv = _rk4_two_end(
                L, A_core, Ts, Tp,
                sigma_em_signal, sigma_abs_signal, sigma_abs_pump,
                alpha_p_bg, alpha_s_bg,
                R1, R2, N_total, tau, lambda_pump, lambda_signal,
                P_pump_forward, P_pump_backward, num_steps=num_points,
            )
            ppmo = np.interp(z, zz, ppp_f)
            ppma = np.interp(z, zz, ppp_b)
            psmo = np.interp(z, zz, psig_f)
            psma = np.interp(z, zz, psig_b)
            pout = (1.0 - R2) * psmo
            used_method = "rk4" if conv else "rk4 (not converged)"

    # Derive N2 fraction from steady-state rate equation (used in thermal display)
    E_pump = H_PLANCK * C_LIGHT / lambda_pump
    E_signal = H_PLANCK * C_LIGHT / lambda_signal
    pump_total = ppmo + ppma
    W_abs_p = sigma_abs_pump * Tp * pump_total / (A_core * E_pump)
    W_em_p = sigma_em_pump * Tp * pump_total / (A_core * E_pump)
    W_abs_s = sigma_abs_signal * Ts * (psmo + psma) / (A_core * E_signal)
    W_em_s = sigma_em_signal * Ts * (psmo + psma) / (A_core * E_signal)
    denom = W_abs_p + W_em_p + W_abs_s + W_em_s + 1.0 / tau
    n2_frac = np.where(denom > 0, (W_abs_p + W_abs_s) / denom, 0.0)
    N2 = n2_frac * N_total

    # Aggregate metrics (output is at z=L for forward, z=0 for backward, both for bidir)
    output_power = float(pout[-1])
    total_pump_in = P_pump_forward + P_pump_backward
    efficiency = output_power / total_pump_in if total_pump_in > 0 else 0.0
    efficiency = max(0.0, min(efficiency, 1.0))

    # Cavity round-trip gain proxy: 10·log10(psmo(L)/psmo(0))
    if psmo[0] > 0:
        gain_db = float(10.0 * np.log10(psmo[-1] / psmo[0]))
    else:
        gain_db = 0.0

    return {
        'z': z,
        'P_pump': pump_total,
        'P_pump_forward': ppmo,
        'P_pump_backward': ppma,
        'P_signal': psmo,
        'P_signal_backward': psma,
        'P_out': pout,
        'N2': N2,
        'gain_db': gain_db,
        'efficiency': efficiency,
        'output_power': output_power,
        'method_used': used_method,
    }


# ------------------------------------------------------------------
# Thermal solver (MATLAB-style 3-layer cylindrical)
# ------------------------------------------------------------------

def calculate_thermal_cavity(
    laser_results,
    core_radius=7.5e-6,
    clad_radius=100e-6,
    coating_radius=125e-6,
    lambda_pump=976e-9,
    lambda_signal=1018e-9,
    k_core=1.38,
    k_clad=1.38,
    k_coat=0.2,
    h_conv=100.0,
    epsilon=0.9,
    T_ambient=290.0,
    num_radial=50,
):
    """
    2D temperature distribution from MATLAB reference (3-layer cylindrical).

    Uses MATLAB convention where `a = core_diam` (used as a length in q·a²
    rather than as a strict radius — this is the MATLAB formulation as-is).
    """
    z = laser_results['z']
    P_f = laser_results['P_pump_forward']
    P_b = laser_results['P_pump_backward']

    a = 2.0 * core_radius      # diameter (MATLAB convention)
    b = 2.0 * clad_radius
    c_coat = 2.0 * coating_radius

    s_ratio = lambda_pump / lambda_signal  # MATLAB uses s = landa_p/landa_s
    eta_heat = 1.0 - s_ratio

    # Volumetric heat from *absorbed* pump power (quantum-defect heating), not
    # the pump power still present at z. P_f travels in +z and is depleted as
    # it propagates (absorbed density = -dP_f/dz); P_b travels in -z and, in
    # this z-array's convention, increases with z as it's depleted travelling
    # backward (absorbed density = +dP_b/dz). Both terms are the local power
    # actually converted into heat, unlike the raw P_f+P_b (power in transit).
    absorbed_density = np.clip(-np.gradient(P_f, z) + np.gradient(P_b, z), 0.0, None)
    q = absorbed_density * eta_heat / (np.pi * a * a)

    # T0 longitudinal (axis temperature)
    T0 = T_ambient + (q * a * a) / (2.0 * h_conv * c_coat) + \
         ((q * a * a) / (2.0 * k_core)) * (np.log(b / a) + 0.5) + \
         (q * a * a) * np.log(c_coat / b) / (2.0 * k_coat)

    T_surface = T_ambient + (q * a * a) / (2.0 * h_conv * c_coat)

    # Radial profile at each z (MATLAB radial grid goes 0..c_coat)
    r = np.linspace(0.0, c_coat, num_radial)
    T_2d = np.zeros((len(r), len(z)))

    for i in range(len(z)):
        q_val = q[i]
        T0_val = T0[i]
        for j, ri in enumerate(r):
            if ri < a:
                T_2d[j, i] = T0_val - q_val * (ri**2) / 4.0 / k_core
            elif ri < b:
                T_2d[j, i] = T0_val - (q_val * (a**2) / 4.0 / k_core) - \
                             (q_val * (a**2) * np.log(ri / a) / 2.0 / k_clad)
            else:
                T_2d[j, i] = T0_val - (q_val * (a**2) / 4.0 / k_core) - \
                             (q_val * (a**2) * np.log(b / a) / 2.0 / k_clad) - \
                             (q_val * (a**2) * np.log(ri / b) / 2.0 / k_coat)

    T_max = float(np.max(T_2d))
    T_max_celsius = T_max - 273.15

    return {
        'r': r,
        'T_2d': T_2d,
        'T_center': T0,
        'T_surface': T_surface,
        'T_max': T_max,
        'T_max_celsius': T_max_celsius,
    }
