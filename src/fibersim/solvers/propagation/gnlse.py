import math
import numpy as np
from typing import List, Union, Tuple
from fibersim.core.constants import C_LIGHT

class GNLSEResults:
    """
    Holds the output of a GNLSE pulse propagation simulation.
    """
    def __init__(
        self,
        z: np.ndarray,             # shape: (z_steps,)
        t: np.ndarray,             # shape: (num_t,)
        frequencies: np.ndarray,   # shape: (num_t,)
        envelopes: np.ndarray,     # shape: (z_steps, num_t) complex time envelope
        spectrums: np.ndarray      # shape: (z_steps, num_t) complex frequency spectrum
    ):
        self.z = z
        self.t = t
        self.frequencies = frequencies
        self.envelopes = envelopes
        self.spectrums = spectrums

    @property
    def temporal_power(self) -> np.ndarray:
        """Returns the 2D temporal power profile |A(z, t)|^2."""
        return np.abs(self.envelopes)**2

    @property
    def spectral_power(self) -> np.ndarray:
        """Returns the 2D spectral power profile |A_tilde(z, f)|^2."""
        return np.abs(self.spectrums)**2


def solve_gnlse(
    time_grid: np.ndarray,              # shape: (N,) - uniform time grid (s)
    initial_envelope: np.ndarray,       # shape: (N,) - complex input pulse envelope (sqrt(W))
    length: float,                      # m
    wavelength_zero: float,             # m - center wavelength (carrier)
    gamma: float,                       # 1/(W * m) - nonlinear coefficient
    beta_list: List[float],             # [beta_2, beta_3, ...] in units of s^2/m, s^3/m, etc.
    loss_db_per_m: float = 0.0,
    self_steepening: bool = True,
    raman: bool = True,
    raman_fraction: float = 0.18,
    tau1: float = 12.2e-15,             # 12.2 fs (silica glass parameter)
    tau2: float = 32.0e-15,             # 32 fs (silica glass parameter)
    z_steps: int = 400
) -> GNLSEResults:
    """
    Solves the Generalized Non-Linear Schrödinger Equation (GNLSE) using the 
    Symmetric Split-Step Fourier Method (SSFM) with frequency-domain RK4 nonlinear step.
    
    Arguments:
        time_grid (np.ndarray): Uniform time array (seconds).
        initial_envelope (np.ndarray): Complex initial envelope A(T) (sqrt(W)).
        length (float): Optical fiber propagation length (meters).
        wavelength_zero (float): Center wavelength (meters).
        gamma (float): Fiber nonlinear coefficient (1 / (W * m)).
        beta_list (List[float]): Dispersion coefficients [beta_2, beta_3, beta_4, ...].
        loss_db_per_m (float): Loss coefficient in dB/meter.
        self_steepening (bool): If True, incorporates self-steepening (shock term).
        raman (bool): If True, incorporates delayed Raman scattering.
        raman_fraction (float): Fractional Raman contribution (typically 0.18 for silica).
        tau1 (float): Raman oscillation time scale (seconds).
        tau2 (float): Raman damping decay time scale (seconds).
        z_steps (int): Number of steps along the propagation coordinate z.
        
    Returns:
        GNLSEResults: Holds the coordinate arrays, temporal envelopes, and spectra.
    """
    c_val = C_LIGHT.to("meter / second").magnitude if hasattr(C_LIGHT, "to") else float(C_LIGHT)
    N = len(time_grid)
    dt = time_grid[1] - time_grid[0]
    
    # Angular frequency grid offset from carrier frequency omega0 (Agrawal convention: omega = -omega_numpy)
    omega = -2.0 * math.pi * np.fft.fftfreq(N, dt)
    
    # Carrier frequency omega0
    omega_0 = 2.0 * math.pi * c_val / wavelength_zero
    
    # Shock operator (self-steepening factor): 1 + omega/omega0
    if self_steepening:
        shock_operator = 1.0 + omega / omega_0
    else:
        shock_operator = np.ones(N)
        
    # Convert loss from dB/m to linear amplitude loss coefficient (alpha/2)
    # loss (dB/m) = 10 * log10(exp(alpha * z)) / z = 4.343 * alpha
    alpha = (loss_db_per_m / 10.0) * math.log(10.0)
    
    # Construct linear dispersion and loss operator: D(omega)
    # GNLSE in frequency domain: dA_tilde/dz = D(omega) * A_tilde
    # where D(omega) = -alpha/2 + i * sum( beta_n / n! * omega^n )
    D = -alpha / 2.0 + 0j
    for idx, beta_n in enumerate(beta_list):
        n = idx + 2
        # dispersion contribution: +i * (beta_n / n!) * omega^n
        D += 1j * (beta_n / math.factorial(n)) * (omega ** n)
        
    # Precompute Raman response function
    if raman:
        h_r = np.zeros(N)
        for k in range(N):
            t_val = k * dt
            # Causal response (t >= 0) is stored in the first half of the array
            if t_val < N / 2.0 * dt:
                h_r[k] = ((tau1**2 + tau2**2) / (tau1 * tau2**2)) * math.exp(-t_val / tau2) * math.sin(t_val / tau1)
            else:
                h_r[k] = 0.0
        # Precomputed FFT spectrum of the Raman response
        # Using numpy's fft since h_r starts at t=0
        H_R = np.fft.fft(h_r) * dt
    else:
        H_R = np.zeros(N, dtype=complex)
        
    # Setup z grid
    z = np.linspace(0.0, length, z_steps)
    dz = length / (z_steps - 1)
    
    # Pre-allocate output arrays
    envelopes_z = np.zeros((z_steps, N), dtype=complex)
    spectrums_z = np.zeros((z_steps, N), dtype=complex)
    
    # Initialize frequency-domain envelope V(omega) = fft(A(T))
    A = initial_envelope.copy().astype(complex)
    V = np.fft.fft(A)
    
    # Create sorting index to output frequency-domain data in ascending order
    freq_phys = -np.fft.fftfreq(N, dt)
    sort_idx = np.argsort(freq_phys)
    frequencies = freq_phys[sort_idx]
    
    envelopes_z[0, :] = A
    spectrums_z[0, :] = (V / N)[sort_idx]
    
    # Pre-calculate half-step dispersion factor
    dispersion_half_step = np.exp(D * dz / 2.0)
    
    def rhs_nonlinear(V_val: np.ndarray) -> np.ndarray:
        """
        Calculates the nonlinear derivative term in frequency domain.
        """
        A_val = np.fft.ifft(V_val)
        A_sq = np.abs(A_val)**2
        
        if raman:
            # Convolution computed via FFT
            R_T = np.real(np.fft.ifft(np.fft.fft(A_sq) * H_R))
            nonlinear_phase = (1.0 - raman_fraction) * A_sq + raman_fraction * R_T
        else:
            nonlinear_phase = A_sq
            
        # N(A) = i * gamma * shock_operator * fft( A * nonlinear_phase )
        return 1j * gamma * shock_operator * np.fft.fft(A_val * nonlinear_phase)

    for idx in range(1, z_steps):
        # 1. Half-step linear dispersion propagation
        V = V * dispersion_half_step
        
        # 2. Runge-Kutta 4th-order (RK4) step for the nonlinear term
        k1 = rhs_nonlinear(V)
        k2 = rhs_nonlinear(V + 0.5 * dz * k1)
        k3 = rhs_nonlinear(V + 0.5 * dz * k2)
        k4 = rhs_nonlinear(V + dz * k3)
        
        V = V + (dz / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        
        # 3. Half-step linear dispersion propagation
        V = V * dispersion_half_step
        
        # Store results
        envelopes_z[idx, :] = np.fft.ifft(V)
        spectrums_z[idx, :] = (V / N)[sort_idx]
        
    return GNLSEResults(z, time_grid, frequencies, envelopes_z, spectrums_z)
