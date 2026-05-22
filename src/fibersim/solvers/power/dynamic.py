import math
import numpy as np
from typing import List, Dict, Union, Callable, Tuple, Optional
from pint import Quantity
from fibersim.core.units import ureg
from fibersim.core.fiber import ActiveFiber
from fibersim.core.constants import H_PLANCK, C_LIGHT
from fibersim.solvers.power.ase import JobCancelled

class DynamicPowerResults:
    """
    Holds the output of a spatial-temporal dynamic fiber laser/amplifier simulation.
    """
    def __init__(
        self,
        t: np.ndarray,            # shape: (num_t,)
        z: np.ndarray,            # shape: (num_z,)
        pumps_f: np.ndarray,      # shape: (num_pumps, num_t, num_z)
        pumps_b: np.ndarray,      # shape: (num_pumps, num_t, num_z)
        signals_f: np.ndarray,    # shape: (num_signals, num_t, num_z)
        signals_b: np.ndarray,    # shape: (num_signals, num_t, num_z)
        n2_fraction: np.ndarray   # shape: (num_t, num_z)
    ):
        self.t = t
        self.z = z
        self.pumps_f = pumps_f
        self.pumps_b = pumps_b
        self.signals_f = signals_f
        self.signals_b = signals_b
        self.n2_fraction = n2_fraction


def solve_dynamic(
    active_fiber: ActiveFiber,
    length: Union[float, Quantity],
    pumps: List[Dict[str, Union[float, Callable[[float], float]]]],
    signals: List[Dict[str, Union[float, Callable[[float], float]]]],
    time_grid: np.ndarray,
    num_z_points: int = 100,
    initial_n2: Union[np.ndarray, float, None] = None,
    progress_callback: Optional[Callable[[float], Optional[bool]]] = None,
) -> DynamicPowerResults:
    """
    Solves the transient coupled spatial-temporal rate equations for active fibers.
    Supports time-dependent pump/signal modulation functions.
    """
    L = length.to("meter").magnitude if isinstance(length, Quantity) else float(length)
    num_t = len(time_grid)
    dt = time_grid[1] - time_grid[0] if num_t > 1 else 1e-6
    
    # Setup z grid
    z = np.linspace(0.0, L, num_z_points)
    dz = L / (num_z_points - 1)
    
    # Physical and spectroscopic properties
    h_val = H_PLANCK.to("joule * second").magnitude if hasattr(H_PLANCK, "to") else float(H_PLANCK)
    c_val = C_LIGHT.to("meter / second").magnitude if hasattr(C_LIGHT, "to") else float(C_LIGHT)
    a_core = active_fiber.geometry.core_radius
    area_core = math.pi * a_core**2
    ion = active_fiber.ion
    N_total = active_fiber.N_max
    tau = ion.lifetime
    
    # Build list of channels
    channels = []
    
    # Process pump channels
    for p_idx, p in enumerate(pumps):
        wl = p['wavelength']
        sig_a, sig_e = ion.get_cross_sections(wl)
        
        # Convert inputs to callable functions
        p_in_f = p.get('power_in_f', 0.0)
        p_in_b = p.get('power_in_b', 0.0)
        func_f = p_in_f if callable(p_in_f) else (lambda t, val=p_in_f: val)
        func_b = p_in_b if callable(p_in_b) else (lambda t, val=p_in_b: val)
        
        channels.append({
            'type': 'pump',
            'index': p_idx,
            'wavelength': wl,
            'func_in_f': func_f,
            'func_in_b': func_b,
            'loss': p.get('loss', 0.0),
            'overlap': p.get('overlap', 1.0),
            'sig_a': sig_a,
            'sig_e': sig_e,
            'R1': 0.0,
            'R2': 0.0
        })
        
    # Process signal channels
    for s_idx, s in enumerate(signals):
        wl = s['wavelength']
        sig_a, sig_e = ion.get_cross_sections(wl)
        
        s_in_f = s.get('power_in_f', 0.0)
        s_in_b = s.get('power_in_b', 0.0)
        func_f = s_in_f if callable(s_in_f) else (lambda t, val=s_in_f: val)
        func_b = s_in_b if callable(s_in_b) else (lambda t, val=s_in_b: val)
        
        channels.append({
            'type': 'signal',
            'index': s_idx,
            'wavelength': wl,
            'func_in_f': func_f,
            'func_in_b': func_b,
            'loss': s.get('loss', 0.0),
            'overlap': s.get('overlap', 1.0),
            'sig_a': sig_a,
            'sig_e': sig_e,
            'R1': s.get('R1', 0.0),
            'R2': s.get('R2', 0.0)
        })

    num_ch = len(channels)
    
    # Pre-allocate output results arrays
    pump_indices = [idx for idx, ch in enumerate(channels) if ch['type'] == 'pump']
    sig_indices = [idx for idx, ch in enumerate(channels) if ch['type'] == 'signal']
    
    pumps_f_res = np.zeros((len(pump_indices), num_t, num_z_points))
    pumps_b_res = np.zeros((len(pump_indices), num_t, num_z_points))
    signals_f_res = np.zeros((len(sig_indices), num_t, num_z_points))
    signals_b_res = np.zeros((len(sig_indices), num_t, num_z_points))
    n2_res = np.zeros((num_t, num_z_points))
    
    # Initialize population inversion fraction n2(z)
    if initial_n2 is None:
        n2 = np.zeros(num_z_points)
    elif isinstance(initial_n2, float):
        n2 = np.full(num_z_points, initial_n2)
    else:
        n2 = initial_n2.copy()
        
    # Spectroscopic factors arrays
    h_nu = np.array([h_val * c_val / ch['wavelength'] for ch in channels])
    sig_a_arr = np.array([ch['sig_a'] for ch in channels])
    sig_e_arr = np.array([ch['sig_e'] for ch in channels])
    gamma_arr = np.array([ch['overlap'] for ch in channels])
    loss_arr = np.array([ch['loss'] for ch in channels])
    R1_arr = np.array([ch['R1'] for ch in channels])
    R2_arr = np.array([ch['R2'] for ch in channels])
    
    def propagate_fields(n2_profile: np.ndarray, t_val: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Solves the spatial power distribution analytically for a given population inversion.
        """
        P_f_local = np.zeros((num_ch, num_z_points))
        P_b_local = np.zeros((num_ch, num_z_points))
        
        # Calculate local gain G_k(z) = gamma_k * N_total * [ (sig_a + sig_e)*n2 - sig_a ] - loss_k
        G = np.zeros((num_ch, num_z_points))
        for i in range(num_z_points):
            G[:, i] = gamma_arr * N_total * ((sig_a_arr + sig_e_arr) * n2_profile[i] - sig_a_arr) - loss_arr
            
        # Cumulative gain integrals
        # integral_0^z G(s) ds
        cum_G_f = np.zeros((num_ch, num_z_points))
        for i in range(1, num_z_points):
            cum_G_f[:, i] = cum_G_f[:, i-1] + G[:, i-1] * dz
            
        # integral_z^L G(s) ds
        cum_G_b = np.zeros((num_ch, num_z_points))
        for i in range(num_z_points - 2, -1, -1):
            cum_G_b[:, i] = cum_G_b[:, i+1] + G[:, i+1] * dz
            
        # Total single-pass gain transmission: T = exp(integral_0^L G ds)
        T = np.exp(cum_G_f[:, -1])
        
        # Input boundary levels at this specific time step
        P_in_f_val = np.array([ch['func_in_f'](t_val) for ch in channels])
        P_in_b_val = np.array([ch['func_in_b'](t_val) for ch in channels])
        
        # Solve boundary equations:
        # P_b(L) = (P_in_b(L) + R2 * T * P_in_f(0)) / (1 - R1 * R2 * T^2)
        denom = 1.0 - R1_arr * R2_arr * T**2
        # Avoid division by zero
        denom = np.where(np.abs(denom) < 1e-9, 1e-9, denom)
        
        P_b_L = (P_in_b_val + R2_arr * T * P_in_f_val) / denom
        P_f_0 = P_in_f_val + R1_arr * T * P_b_L
        
        # Propagate power across spatial positions
        for i in range(num_z_points):
            P_f_local[:, i] = P_f_0 * np.exp(cum_G_f[:, i])
            P_b_local[:, i] = P_b_L * np.exp(cum_G_b[:, i])
            
        return P_f_local, P_b_local

    def get_population_derivative(P_f_local: np.ndarray, P_b_local: np.ndarray, n2_profile: np.ndarray) -> np.ndarray:
        """
        Calculates d(n2)/dt at all positions z.
        """
        P_tot = P_f_local + P_b_local
        # absorption transition rate W_abs
        W_abs = np.zeros(num_z_points)
        W_stim = np.zeros(num_z_points)
        
        for i in range(num_z_points):
            W_abs[i] = np.sum(P_tot[:, i] * sig_a_arr * gamma_arr / (h_nu * area_core))
            W_stim[i] = np.sum(P_tot[:, i] * (sig_a_arr + sig_e_arr) * gamma_arr / (h_nu * area_core))
            
        # dn2/dt = W_abs * (1 - n2) - (1/tau + W_stim) * n2
        dn2_dt = W_abs * (1.0 - n2_profile) - (1.0 / tau + W_stim) * n2_profile
        return dn2_dt

    # Progress stride: report at most ~100 times across all time-steps
    progress_stride = max(1, num_t // 100)

    # Time integration loop
    for t_idx in range(num_t):
        t_val = time_grid[t_idx]
        
        # 1. Propagate fields using current population inversion n2
        P_f, P_b = propagate_fields(n2, t_val)
        
        # Record results at this time step
        pumps_f_res[:, t_idx, :] = P_f[pump_indices, :]
        pumps_b_res[:, t_idx, :] = P_b[pump_indices, :]
        signals_f_res[:, t_idx, :] = P_f[sig_indices, :]
        signals_b_res[:, t_idx, :] = P_b[sig_indices, :]
        n2_res[t_idx, :] = n2
        
        # 2. Unconditionally stable Exponential Integrator time step
        if t_idx < num_t - 1:
            P_tot = P_f + P_b
            W_abs = np.zeros(num_z_points)
            W_stim = np.zeros(num_z_points)
            for i in range(num_z_points):
                W_abs[i] = np.sum(P_tot[:, i] * sig_a_arr * gamma_arr / (h_nu * area_core))
                W_stim[i] = np.sum(P_tot[:, i] * (sig_a_arr + sig_e_arr) * gamma_arr / (h_nu * area_core))
                
            A = W_abs
            B = W_abs + 1.0 / tau + W_stim
            
            # Update n2 analytically: n2 = n2 * exp(-B * dt) + (A / B) * (1 - exp(-B * dt))
            B_safe = np.where(B < 1e-12, 1e-12, B)
            exp_factor = np.exp(-B * dt)
            n2 = n2 * exp_factor + (A / B_safe) * (1.0 - exp_factor)
            n2 = np.clip(n2, 0.0, 1.0)

        if progress_callback is not None and (t_idx % progress_stride == 0 or t_idx == num_t - 1):
            cont = progress_callback((t_idx + 1) / num_t)
            if cont is False:
                raise JobCancelled("Dynamic solver cancelled by user")

    return DynamicPowerResults(
        t=time_grid,
        z=z,
        pumps_f=pumps_f_res,
        pumps_b=pumps_b_res,
        signals_f=signals_f_res,
        signals_b=signals_b_res,
        n2_fraction=n2_res
    )
