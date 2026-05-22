import math
import numpy as np
from typing import List, Dict, Union
from pydantic import BaseModel, Field
from fibersim.core.constants import H_PLANCK, C_LIGHT

class OpticalChannel(BaseModel):
    """Represents an optical channel (pump, signal, or ASE bin) in the fiber."""
    name: str
    wavelength: float = Field(..., description="Wavelength in meters")
    power_in: float = Field(0.0, description="Input power in Watts")
    direction: str = Field("forward", description="'forward' or 'backward'")
    sigma_abs: float = Field(..., description="Absorption cross-section in m^2")
    sigma_em: float = Field(..., description="Emission cross-section in m^2")
    overlap: float = Field(..., description="Mode overlap factor (Gamma) with the active core")
    loss: float = Field(0.0, description="Background loss coefficient in 1/m")
    is_ase: bool = Field(False, description="Flag indicating if this is an ASE channel")
    bandwidth: float = Field(0.0, description="Wavelength bandwidth in meters (only for ASE channels)")


def solve_steady_state(
    length: float,
    N_total: float,
    tau: float,
    core_radius: float,
    channels: List[OpticalChannel],
    num_points: int = 200,
    max_iter: int = 150,
    tol: float = 1e-6
) -> Dict[str, Union[np.ndarray, Dict]]:
    """
    Solves steady-state coupled rate equations for Yb-doped active fibers using relaxation.
    
    Arguments:
        length (float): Fiber length in meters.
        N_total (float): Yb ion concentration in ions/m^3.
        tau (float): Upper state lifetime in seconds.
        core_radius (float): Core radius in meters.
        channels (List[OpticalChannel]): List of pump, signal, and ASE channels.
        num_points (int): Number of longitudinal discretization points.
        max_iter (int): Maximum number of relaxation iterations.
        tol (float): Relative convergence tolerance.
        
    Returns:
        Dict: Dictionary containing 'z', power profiles for each channel, upper state population N2(z),
              gain_db, and power conversion efficiency.
    """
    h = H_PLANCK.to("joule * second").magnitude
    c = C_LIGHT.to("meter / second").magnitude
    core_area = math.pi * core_radius**2

    z = np.linspace(0, length, num_points)
    dz = length / (num_points - 1)

    # Initialize power arrays for all channels [num_channels, num_points]
    num_ch = len(channels)
    P = np.zeros((num_ch, num_points))

    # Set boundary conditions
    for idx, ch in enumerate(channels):
        if ch.direction == "forward":
            P[idx, 0] = ch.power_in
        else:
            P[idx, -1] = ch.power_in

    N2 = np.zeros(num_points)
    
    # Pre-calculate photon energies and spontaneous emission source terms
    photon_energies = np.zeros(num_ch)
    ase_sources = np.zeros(num_ch)
    
    for idx, ch in enumerate(channels):
        nu = c / ch.wavelength
        photon_energies[idx] = h * nu
        if ch.is_ase:
            # Spontaneous emission source term: 2 * h * c^2 * delta_lambda / lambda^5 (W/m) per unit N2
            # For 2 polarizations, we add factor of 2.
            ase_sources[idx] = 2 * h * (c**2) * ch.bandwidth / (ch.wavelength**5)
            
    # Relaxation iterations
    for iteration in range(max_iter):
        P_old = P.copy()

        # 1. Update populations N2(z) and N1(z) at each point
        for i in range(num_points):
            # Sum up W_abs and W_em rates over all channels
            W_abs_sum = 0.0
            W_em_sum = 0.0
            
            for idx, ch in enumerate(channels):
                p_val = P[idx, i]
                # Transition rate W = (sigma * Gamma * P) / (h * nu * A_core)
                rate_factor = ch.overlap / (photon_energies[idx] * core_area)
                W_abs_sum += ch.sigma_abs * rate_factor * p_val
                W_em_sum += ch.sigma_em * rate_factor * p_val

            # Steady state upper level population fraction n2
            n2_frac = W_abs_sum / (W_abs_sum + W_em_sum + 1.0 / tau) if (W_abs_sum + W_em_sum + 1.0 / tau) > 0 else 0.0
            N2[i] = n2_frac * N_total

        N1 = N_total - N2

        # 2. Propagate channels
        # Forward propagation
        for idx, ch in enumerate(channels):
            if ch.direction == "forward":
                # Start at boundary
                P[idx, 0] = ch.power_in
                for i in range(num_points - 1):
                    # Gain coefficient
                    gain_coeff = (ch.sigma_em * N2[i] - ch.sigma_abs * N1[i]) * ch.overlap - ch.loss
                    
                    # ASE term if applicable
                    ase_term = 0.0
                    if ch.is_ase:
                        # Spontaneous emission is proportional to N2
                        ase_term = ase_sources[idx] * ch.sigma_em * N2[i] * ch.overlap
                        
                    dP_dz = gain_coeff * P[idx, i] + ase_term
                    P[idx, i+1] = max(P[idx, i] + dP_dz * dz, 0.0)

        # Backward propagation
        for idx, ch in enumerate(channels):
            if ch.direction == "backward":
                # Start at boundary
                P[idx, -1] = ch.power_in
                for i in range(num_points - 1, 0, -1):
                    # Gain coefficient
                    gain_coeff = (ch.sigma_em * N2[i] - ch.sigma_abs * N1[i]) * ch.overlap - ch.loss
                    
                    # ASE term if applicable
                    ase_term = 0.0
                    if ch.is_ase:
                        ase_term = ase_sources[idx] * ch.sigma_em * N2[i] * ch.overlap
                        
                    dP_dz = gain_coeff * P[idx, i] + ase_term
                    # P(z - dz) = P(z) - dP/dz * dz
                    P[idx, i-1] = max(P[idx, i] - dP_dz * dz, 0.0)

        # 3. Check for convergence
        max_diff = np.max(np.abs(P - P_old))
        max_val = np.max(np.abs(P))
        rel_diff = max_diff / max_val if max_val > 0 else 0.0
        
        if rel_diff < tol:
            break

    # Build results
    results_powers = {}
    for idx, ch in enumerate(channels):
        results_powers[ch.name] = P[idx]

    # Performance metrics
    output_powers = {}
    gain_db = {}
    total_pump_in = 0.0
    total_signal_out = 0.0
    
    for idx, ch in enumerate(channels):
        if "pump" in ch.name.lower():
            total_pump_in += ch.power_in
            
        out_p = P[idx, -1] if ch.direction == "forward" else P[idx, 0]
        output_powers[ch.name] = out_p
        
        if "signal" in ch.name.lower():
            total_signal_out += out_p
            if ch.power_in > 0:
                gain_db[ch.name] = 10.0 * math.log10(out_p / ch.power_in)
            else:
                gain_db[ch.name] = 0.0

    efficiency = total_signal_out / total_pump_in if total_pump_in > 0 else 0.0

    return {
        "z": z,
        "powers": results_powers,
        "N2": N2,
        "N1": N1,
        "output_powers": output_powers,
        "gain_db": gain_db,
        "efficiency": efficiency
    }
