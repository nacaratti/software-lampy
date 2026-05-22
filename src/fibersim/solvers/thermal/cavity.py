import numpy as np

# Physical constants
H_PLANCK = 6.62607015e-34  # J·s
C_LIGHT = 299792458  # m/s
SIGMA_BOLTZMANN = 5.670374419e-8  # W/(m²·K⁴)

def solve_laser_rate_equations(
    fiber_length=5.0,
    core_radius=3e-6,
    clad_radius=62.5e-6,
    coating_radius=125e-6,
    N_total=4e25,
    tau=1e-3,
    lambda_pump=976e-9,
    lambda_signal=1018e-9,
    sigma_abs_pump=2.5e-25,
    sigma_em_pump=2.7e-25,
    sigma_abs_signal=0.4e-25,
    sigma_em_signal=4.5e-25,
    gamma_pump=0.8,
    gamma_signal=0.9,
    P_pump_forward=10.0,
    P_pump_backward=0.0,
    P_signal_seed=1e-6,
    pumping="forward",
    num_points=500
):
    """
    Solves steady-state rate equations for Yb-doped active fiber.
    Supports forward, backward, and bidirectional pumping.
    """
    z = np.linspace(0.0, fiber_length, num_points)
    dz = z[1] - z[0] if num_points > 1 else 0.01

    A_core = np.pi * core_radius**2
    E_pump = H_PLANCK * C_LIGHT / lambda_pump
    E_signal = H_PLANCK * C_LIGHT / lambda_signal

    Gamma_p = gamma_pump / A_core
    Gamma_s = gamma_signal / A_core

    # Initialize arrays
    P_pump_f = np.zeros_like(z)
    P_pump_b = np.zeros_like(z)
    P_signal = np.zeros_like(z)
    N2 = np.zeros_like(z)

    # Set up relaxation method iterations
    max_iter = 100
    tol = 1e-5
    
    # Initial guesses
    if pumping == "forward":
        P_pump_f[0] = P_pump_forward
        P_signal[0] = P_signal_seed
        # March forward directly
        for i in range(len(z) - 1):
            W_abs_p = sigma_abs_pump * Gamma_p * P_pump_f[i] / E_pump
            W_em_p = sigma_em_pump * Gamma_p * P_pump_f[i] / E_pump
            W_abs_s = sigma_abs_signal * Gamma_s * P_signal[i] / E_signal
            W_em_s = sigma_em_signal * Gamma_s * P_signal[i] / E_signal

            denom = (W_abs_p + W_em_p + W_abs_s + W_em_s + 1.0 / tau)
            n2_frac = (W_abs_p + W_abs_s) / denom if denom > 0 else 0.0
            N2[i] = n2_frac * N_total
            N1 = N_total - N2[i]

            dP_pump_dz = Gamma_p * (sigma_em_pump * N2[i] - sigma_abs_pump * N1) * P_pump_f[i]
            dP_signal_dz = Gamma_s * (sigma_em_signal * N2[i] - sigma_abs_signal * N1) * P_signal[i]

            P_pump_f[i+1] = max(P_pump_f[i] + dP_pump_dz * dz, 1e-12)
            P_signal[i+1] = max(P_signal[i] + dP_signal_dz * dz, 1e-12)

        # Calculate final point N2
        W_abs_p = sigma_abs_pump * Gamma_p * P_pump_f[-1] / E_pump
        W_em_p = sigma_em_pump * Gamma_p * P_pump_f[-1] / E_pump
        W_abs_s = sigma_abs_signal * Gamma_s * P_signal[-1] / E_signal
        W_em_s = sigma_em_signal * Gamma_s * P_signal[-1] / E_signal
        denom = (W_abs_p + W_em_p + W_abs_s + W_em_s + 1.0 / tau)
        N2[-1] = ((W_abs_p + W_abs_s) / denom if denom > 0 else 0.0) * N_total

    elif pumping == "backward":
        P_pump_b[-1] = P_pump_backward
        P_signal[0] = P_signal_seed
        # Iterate to converge backward pump and forward signal
        for it in range(max_iter):
            P_pump_b_old = P_pump_b.copy()
            P_signal_old = P_signal.copy()

            # 1. Backward pump propagation (from end to start)
            P_pump_b[-1] = P_pump_backward
            for i in range(len(z) - 1, 0, -1):
                W_abs_p = sigma_abs_pump * Gamma_p * P_pump_b[i] / E_pump
                W_em_p = sigma_em_pump * Gamma_p * P_pump_b[i] / E_pump
                W_abs_s = sigma_abs_signal * Gamma_s * P_signal[i] / E_signal
                W_em_s = sigma_em_signal * Gamma_s * P_signal[i] / E_signal
                
                denom = (W_abs_p + W_em_p + W_abs_s + W_em_s + 1.0 / tau)
                N2[i] = ((W_abs_p + W_abs_s) / denom if denom > 0 else 0.0) * N_total
                N1 = N_total - N2[i]

                # Propagate pump backward (going from i to i-1, delta_z is effectively -dz)
                dP_pump_dz = Gamma_p * (sigma_em_pump * N2[i] - sigma_abs_pump * N1) * P_pump_b[i]
                P_pump_b[i-1] = max(P_pump_b[i] - dP_pump_dz * dz, 1e-12)

            # 2. Forward signal propagation
            P_signal[0] = P_signal_seed
            for i in range(len(z) - 1):
                W_abs_p = sigma_abs_pump * Gamma_p * P_pump_b[i] / E_pump
                W_em_p = sigma_em_pump * Gamma_p * P_pump_b[i] / E_pump
                W_abs_s = sigma_abs_signal * Gamma_s * P_signal[i] / E_signal
                W_em_s = sigma_em_signal * Gamma_s * P_signal[i] / E_signal
                
                denom = (W_abs_p + W_em_p + W_abs_s + W_em_s + 1.0 / tau)
                N2[i] = ((W_abs_p + W_abs_s) / denom if denom > 0 else 0.0) * N_total
                N1 = N_total - N2[i]

                dP_signal_dz = Gamma_s * (sigma_em_signal * N2[i] - sigma_abs_signal * N1) * P_signal[i]
                P_signal[i+1] = max(P_signal[i] + dP_signal_dz * dz, 1e-12)

            # Converged?
            err_b = np.max(np.abs(P_pump_b - P_pump_b_old)) / (P_pump_backward + 1e-12)
            err_s = np.max(np.abs(P_signal - P_signal_old)) / (np.max(P_signal) + 1e-12)
            if err_b < tol and err_s < tol:
                break

    else: # bidirectional
        P_pump_f[0] = P_pump_forward
        P_pump_b[-1] = P_pump_backward
        P_signal[0] = P_signal_seed
        
        for it in range(max_iter):
            P_pump_f_old = P_pump_f.copy()
            P_pump_b_old = P_pump_b.copy()
            P_signal_old = P_signal.copy()

            # Forward pump propagation
            P_pump_f[0] = P_pump_forward
            for i in range(len(z) - 1):
                P_p_tot = P_pump_f[i] + P_pump_b[i]
                W_abs_p = sigma_abs_pump * Gamma_p * P_p_tot / E_pump
                W_em_p = sigma_em_pump * Gamma_p * P_p_tot / E_pump
                W_abs_s = sigma_abs_signal * Gamma_s * P_signal[i] / E_signal
                W_em_s = sigma_em_signal * Gamma_s * P_signal[i] / E_signal

                denom = (W_abs_p + W_em_p + W_abs_s + W_em_s + 1.0 / tau)
                N2[i] = ((W_abs_p + W_abs_s) / denom if denom > 0 else 0.0) * N_total
                N1 = N_total - N2[i]

                dP_pump_dz = Gamma_p * (sigma_em_pump * N2[i] - sigma_abs_pump * N1) * P_pump_f[i]
                P_pump_f[i+1] = max(P_pump_f[i] + dP_pump_dz * dz, 1e-12)

            # Backward pump propagation
            P_pump_b[-1] = P_pump_backward
            for i in range(len(z) - 1, 0, -1):
                dP_pump_dz = Gamma_p * (sigma_em_pump * N2[i] - (N_total - N2[i])) * P_pump_b[i]
                P_pump_b[i-1] = max(P_pump_b[i] - dP_pump_dz * dz, 1e-12)

            # Forward signal propagation
            P_signal[0] = P_signal_seed
            for i in range(len(z) - 1):
                P_p_tot = P_pump_f[i] + P_pump_b[i]
                W_abs_p = sigma_abs_pump * Gamma_p * P_p_tot / E_pump
                W_em_p = sigma_em_pump * Gamma_p * P_p_tot / E_pump
                W_abs_s = sigma_abs_signal * Gamma_s * P_signal[i] / E_signal
                W_em_s = sigma_em_signal * Gamma_s * P_signal[i] / E_signal

                denom = (W_abs_p + W_em_p + W_abs_s + W_em_s + 1.0 / tau)
                N2[i] = ((W_abs_p + W_abs_s) / denom if denom > 0 else 0.0) * N_total
                N1 = N_total - N2[i]

                dP_signal_dz = Gamma_s * (sigma_em_signal * N2[i] - sigma_abs_signal * N1) * P_signal[i]
                P_signal[i+1] = max(P_signal[i] + dP_signal_dz * dz, 1e-12)

            # Check convergence
            err_f = np.max(np.abs(P_pump_f - P_pump_f_old)) / (P_pump_forward + 1e-12)
            err_b = np.max(np.abs(P_pump_b - P_pump_b_old)) / (P_pump_backward + 1e-12)
            err_s = np.max(np.abs(P_signal - P_signal_old)) / (np.max(P_signal) + 1e-12)
            if err_f < tol and err_b < tol and err_s < tol:
                break

    # Calculate metrics
    P_pump_tot = P_pump_f + P_pump_b
    output_power = float(P_signal[-1])
    gain_db = float(10.0 * np.log10(P_signal[-1] / P_signal_seed)) if P_signal_seed > 0 else 0.0
    
    total_pump_in = 0.0
    if pumping == "forward" or pumping == "bidirectional":
        total_pump_in += P_pump_forward
    if pumping == "backward" or pumping == "bidirectional":
        total_pump_in += P_pump_backward
        
    efficiency = float((P_signal[-1] - P_signal_seed) / total_pump_in) if total_pump_in > 0 else 0.0
    efficiency = max(0.0, efficiency)

    return {
        'z': z,
        'P_pump': P_pump_tot,
        'P_pump_forward': P_pump_f,
        'P_pump_backward': P_pump_b,
        'P_signal': P_signal,
        'N2': N2,
        'gain_db': gain_db,
        'efficiency': efficiency,
        'output_power': output_power
    }


def calculate_thermal_cavity(
    laser_results,
    core_radius=3e-6,
    clad_radius=62.5e-6,
    coating_radius=125e-6,
    lambda_pump=976e-9,
    lambda_signal=1018e-9,
    k_core=1.38,
    k_clad=1.38,
    k_coat=0.2,
    h_conv=10.0,
    T_ambient=298.15,
    num_radial=50
):
    """
    Calculates the 2D temperature distribution T(r, z) based on local pump absorption.
    Uses the 3-layer cylindrical heat conduction equations.
    """
    z = laser_results['z']
    P_pump = laser_results['P_pump']
    N2 = laser_results['N2']

    # Local heat generation per unit length Q_L(z) in W/m.
    # dP_pump/dz gives pump power absorbed.
    # Note: Q_L(z) = eta_heat * (-dP_pump/dz)
    eta_heat = 1.0 - (lambda_pump / lambda_signal)
    
    # We estimate local absorbed power along z.
    # P_absorbed_per_length = -d(P_pump)/dz
    # Let's compute this using np.gradient.
    dP_pump_dz = -np.gradient(P_pump, z)
    # Heat generation Q_L
    Q_L = eta_heat * dP_pump_dz
    # Ensure no negative heat generation
    Q_L = np.clip(Q_L, 0.0, None)

    # Solve cylindrical heat equation for center temperature T0(z) and surface temperature Ts(z)
    # Radii in meters
    a = core_radius
    b = clad_radius
    c = coating_radius

    # center T0: T0(z) = T_ambient + Q_L/(2*pi*h_conv*c) + Q_L/(2*pi*k_core)*(ln(b/a) + 0.5) + Q_L*ln(c/b)/(2*pi*k_coat)
    # Actually, cladding conductivity is k_clad, core is k_core. Let's write the correct multi-layer expression:
    # T0(z) = T_ambient + Q_L / (2*pi*h_conv*c) + Q_L / (2*pi*k_coat) * ln(c/b) + Q_L / (2*pi*k_clad) * ln(b/a) + Q_L / (4*pi*k_core)
    term_conv = Q_L / (2.0 * np.pi * h_conv * c)
    term_coat = (Q_L * np.log(c / b)) / (2.0 * np.pi * k_coat)
    term_clad = (Q_L * np.log(b / a)) / (2.0 * np.pi * k_clad)
    term_core = Q_L / (4.0 * np.pi * k_core)

    T0 = T_ambient + term_conv + term_coat + term_clad + term_core
    T_surface = T_ambient + term_conv

    # 2D Grid: r from 0 to coating_radius
    r = np.linspace(0.0, coating_radius, num_radial)
    T_2d = np.zeros((len(r), len(z)))

    for i, Q_val in enumerate(Q_L):
        T0_val = T0[i]
        q_vol = Q_val / (np.pi * a**2) if a > 0 else 0.0

        for j, ri in enumerate(r):
            if ri <= a:
                # Core
                T_2d[j, i] = T0_val - q_vol * (ri**2) / (4.0 * k_core)
            elif ri <= b:
                # Cladding
                T_2d[j, i] = T0_val - (Q_val / (4.0 * np.pi * k_core)) - (Q_val * np.log(ri / a) / (2.0 * np.pi * k_clad))
            else:
                # Coating
                T_2d[j, i] = (T0_val - (Q_val / (4.0 * np.pi * k_core))
                              - (Q_val * np.log(b / a) / (2.0 * np.pi * k_clad))
                              - (Q_val * np.log(ri / b) / (2.0 * np.pi * k_coat)))

    T_max = float(np.max(T_2d))
    T_max_celsius = T_max - 273.15

    return {
        'r': r,
        'T_2d': T_2d,
        'T_center': T0,
        'T_surface': T_surface,
        'T_max': T_max,
        'T_max_celsius': T_max_celsius
    }
