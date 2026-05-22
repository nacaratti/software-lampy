import math
import numpy as np
from typing import List, Dict, Union, Tuple, Callable, Optional
from pint import Quantity
from fibersim.core.units import ureg
from fibersim.core.fiber import ActiveFiber
from fibersim.core.constants import H_PLANCK, C_LIGHT


class JobCancelled(RuntimeError):
    """Raised internally when a progress_callback returns False to signal cancellation."""
    pass


def _propagate_forward(P: np.ndarray, g: np.ndarray, S: np.ndarray, dz: float) -> np.ndarray:
    """Integrate dP/dz = g*P + S over length dz (stable exponential step)."""
    g = np.clip(g, -200.0, 200.0)
    gdz = np.clip(g * dz, -20.0, 20.0)
    out = np.empty_like(P)
    small = np.abs(g) < 1e-12
    exp_gdz = np.exp(gdz)
    out[~small] = P[~small] * exp_gdz[~small] + (S[~small] / g[~small]) * (exp_gdz[~small] - 1.0)
    out[small] = P[small] + S[small] * dz
    return np.maximum(out, 0.0)


def _propagate_backward(P: np.ndarray, g: np.ndarray, S: np.ndarray, dz: float) -> np.ndarray:
    """Integrate dP-/dz = -(g*P + S) when marching from z=L toward z=0."""
    return _propagate_forward(P, g, S, dz)

class ASEPowerResults:
    """
    Holds the results of the ASE solver simulation.
    """
    def __init__(
        self,
        z: np.ndarray,
        pumps_f: np.ndarray,      # shape: (num_pumps, num_z)
        pumps_b: np.ndarray,      # shape: (num_pumps, num_z)
        signals_f: np.ndarray,    # shape: (num_signals, num_z)
        signals_b: np.ndarray,    # shape: (num_signals, num_z)
        ase_f: np.ndarray,        # shape: (num_ase, num_z)
        ase_b: np.ndarray,        # shape: (num_ase, num_z)
        n2_fraction: np.ndarray,  # shape: (num_z,)
        pump_wavelengths: List[float],
        signal_wavelengths: List[float],
        ase_wavelengths: List[float]
    ):
        self.z = z
        self.pumps_f = pumps_f
        self.pumps_b = pumps_b
        self.signals_f = signals_f
        self.signals_b = signals_b
        self.ase_f = ase_f
        self.ase_b = ase_b
        self.n2_fraction = n2_fraction
        self.pump_wavelengths = pump_wavelengths
        self.signal_wavelengths = signal_wavelengths
        self.ase_wavelengths = ase_wavelengths


def solve_ase(
    active_fiber: ActiveFiber,
    length: Union[float, Quantity],
    pumps: List[Dict[str, float]],       # items: {'wavelength': m, 'power_in_f': W, 'power_in_b': W, 'loss': 1/m, 'overlap': float}
    signals: List[Dict[str, float]],     # items: {'wavelength': m, 'power_in_f': W, 'power_in_b': W, 'loss': 1/m, 'overlap': float}
    ase_config: Dict[str, Union[float, int]], # {'wl_min': m, 'wl_max': m, 'num_channels': int, 'loss': 1/m, 'overlap': float, 'R1': float, 'R2': float}
    num_z_points: int = 150,
    max_iterations: int = 100,
    tolerance: float = 1e-5,
    relaxation_factor: float = 0.4,
    progress_callback: Optional[Callable[[float], Optional[bool]]] = None,
) -> ASEPowerResults:
    """
    Solves the bi-directional fiber amplifier/laser power evolution equations 
    with Amplified Spontaneous Emission (ASE) using the relaxation grid method.
    """
    L = length.to("meter").magnitude if isinstance(length, Quantity) else float(length)
    
    # Convert Pint constants to standard floats in SI units
    h_val = H_PLANCK.to("joule * second").magnitude if hasattr(H_PLANCK, "to") else float(H_PLANCK)
    c_val = C_LIGHT.to("meter / second").magnitude if hasattr(C_LIGHT, "to") else float(C_LIGHT)
    
    # 1. Setup z grid
    z = np.linspace(0.0, L, num_z_points)
    dz = z[1] - z[0]
    
    # Extract core properties
    a_core = active_fiber.geometry.core_radius
    area_core = math.pi * a_core**2
    ion = active_fiber.ion
    N_total = active_fiber.N_max # assumed uniform or peak in core
    
    # 2. Configure channels
    channels = []
    
    # Add Pumps
    for p_idx, p in enumerate(pumps):
        wl = p['wavelength']
        sig_a, sig_e = ion.get_cross_sections(wl)
        channels.append({
            'type': 'pump',
            'index': p_idx,
            'wavelength': wl,
            'power_in_f': p.get('power_in_f', 0.0),
            'power_in_b': p.get('power_in_b', 0.0),
            'loss': p.get('loss', 0.0),
            'overlap': p.get('overlap', 1.0),
            'sig_a': sig_a,
            'sig_e': sig_e,
            'R1': 0.0,
            'R2': 0.0,
            'ase_band': 0.0 # spontaneous source is zero
        })
        
    # Add Signals
    for s_idx, s in enumerate(signals):
        wl = s['wavelength']
        sig_a, sig_e = ion.get_cross_sections(wl)
        channels.append({
            'type': 'signal',
            'index': s_idx,
            'wavelength': wl,
            'power_in_f': s.get('power_in_f', 0.0),
            'power_in_b': s.get('power_in_b', 0.0),
            'loss': s.get('loss', 0.0),
            'overlap': s.get('overlap', 1.0),
            'sig_a': sig_a,
            'sig_e': sig_e,
            'R1': s.get('R1', 0.0),
            'R2': s.get('R2', 0.0),
            'ase_band': 0.0 # spontaneous source is zero
        })
        
    # Add ASE channels
    wl_min = ase_config.get('wl_min', 1000e-9)
    wl_max = ase_config.get('wl_max', 1100e-9)
    n_ase = int(ase_config.get('num_channels', 40))
    ase_wls = np.linspace(wl_min, wl_max, n_ase)
    dwl = (wl_max - wl_min) / (n_ase - 1) if n_ase > 1 else 10e-9

    for a_idx, wl in enumerate(ase_wls):
        sig_a, sig_e = ion.get_cross_sections(wl)
        channels.append({
            'type': 'ase',
            'index': a_idx,
            'wavelength': wl,
            'power_in_f': 0.0,
            'power_in_b': 0.0,
            'loss': ase_config.get('loss', 0.0),
            'overlap': ase_config.get('overlap', 1.0),
            'sig_a': sig_a,
            'sig_e': sig_e,
            'R1': ase_config.get('R1', 0.0),
            'R2': ase_config.get('R2', 0.0),
            'ase_dwl': dwl,
        })

    # Prepare local variables & arrays
    num_ch = len(channels)
    
    # Initialize power arrays; only boundary injection (interior starts at zero)
    P_f = np.zeros((num_ch, num_z_points))
    P_b = np.zeros((num_ch, num_z_points))
    for ch_idx, ch in enumerate(channels):
        P_f[ch_idx, 0] = ch['power_in_f']
        P_b[ch_idx, -1] = ch['power_in_b']

    n2 = np.zeros(num_z_points)

    h_nu = np.array([h_val * c_val / ch['wavelength'] for ch in channels])
    sig_a_arr = np.array([ch['sig_a'] for ch in channels])
    sig_e_arr = np.array([ch['sig_e'] for ch in channels])
    gamma_arr = np.array([ch['overlap'] for ch in channels])
    loss_arr = np.array([ch['loss'] for ch in channels])
    wl_arr = np.array([ch['wavelength'] for ch in channels])
    is_ase_ch = np.array([ch['type'] == 'ase' for ch in channels])
    is_pump_sig = np.array([ch['type'] in ('pump', 'signal') for ch in channels])
    ase_dwl_arr = np.array([ch.get('ase_dwl', 0.0) for ch in channels])
    # Max |g| per step (1/m) — avoids exp() overflow on long fibers / high doping
    g_max = 200.0

    # Progress throttle: report at most ~100 times across all iterations
    progress_stride = max(1, max_iterations // 100)

    def _n2_fraction_at(i: int, *, include_backward: bool) -> float:
        """Upper-state fraction from local pump + signal + ASE powers at grid index i."""
        p_loc = P_f[:, i]
        if include_backward:
            p_loc = p_loc + P_b[:, i]
        w_abs = np.sum(p_loc * sig_a_arr * gamma_arr / (h_nu * area_core))
        w_em = np.sum(p_loc * sig_e_arr * gamma_arr / (h_nu * area_core))
        denom = w_abs + w_em + 1.0 / ion.lifetime
        if denom <= 0.0:
            return 0.0
        return min(max(w_abs / denom, 0.0), 1.0)

    def _g_and_s_ase(i: int, *, include_backward: bool) -> tuple[np.ndarray, np.ndarray]:
        n2_frac = _n2_fraction_at(i, include_backward=include_backward)
        n2[i] = n2_frac
        n2_dens = n2_frac * N_total
        n1_dens = (1.0 - n2_frac) * N_total
        g = np.clip(gamma_arr * (sig_e_arr * n2_dens - sig_a_arr * n1_dens), -g_max, g_max)
        # ASE bins: limit stimulated gain to avoid runaway on coarse z-grids
        g = np.where(is_ase_ch, np.minimum(g, 25.0), g)
        # Single-mode spontaneous: 2*h*nu*Delta_nu * sigma_e * N2 * Gamma (Giles / Einstein)
        delta_nu = c_val * ase_dwl_arr / (wl_arr ** 2)
        s_ase = np.where(
            is_ase_ch,
            2.0 * h_val * (c_val / wl_arr) * delta_nu * sig_e_arr * n2_dens * gamma_arr,
            0.0,
        )
        return g, s_ase

    # Relaxation iterations
    for it in range(max_iterations):
        P_f_old = P_f.copy()
        P_b_old = P_b.copy()

        # Forward: local n2(z) from pump + signal at each step
        for ch_idx, ch in enumerate(channels):
            P_f[ch_idx, 0] = ch['power_in_f'] + ch['R1'] * P_b[ch_idx, 0]

        for i in range(num_z_points - 1):
            g, s_ase = _g_and_s_ase(i, include_backward=True)
            P_f[:, i + 1] = _propagate_forward(P_f[:, i], g - loss_arr, s_ase, dz)

        # Backward
        for ch_idx, ch in enumerate(channels):
            P_b[ch_idx, -1] = ch['power_in_b'] + ch['R2'] * P_f[ch_idx, -1]

        for i in range(num_z_points - 1, 0, -1):
            g, s_ase = _g_and_s_ase(i, include_backward=True)
            P_b[:, i - 1] = _propagate_backward(P_b[:, i], g - loss_arr, s_ase, dz)
            
        # 4. Under-relaxation (ramp up first iterations — avoids trapping at zero interior)
        eff_relax = 1.0 if it < 15 else relaxation_factor
        P_f = eff_relax * P_f + (1.0 - eff_relax) * P_f_old
        P_b = eff_relax * P_b + (1.0 - eff_relax) * P_b_old
        
        # 5. Check Convergence
        max_err = 0.0
        for ch_idx in range(num_ch):
            # Focus error check on channels with significant power
            max_power = np.max(P_f[ch_idx, :] + P_b[ch_idx, :])
            if max_power > 1e-9:
                err_f = np.max(np.abs(P_f[ch_idx, :] - P_f_old[ch_idx, :])) / max_power
                err_b = np.max(np.abs(P_b[ch_idx, :] - P_b_old[ch_idx, :])) / max_power
                max_err = max(max_err, err_f, err_b)
                
        if max_err < tolerance and it > 5:
            # Succeeded convergence
            if progress_callback is not None:
                progress_callback(1.0)
            break

        # Throttled progress + cancellation check
        if progress_callback is not None and (it % progress_stride == 0):
            cont = progress_callback((it + 1) / max_iterations)
            if cont is False:
                raise JobCancelled("ASE solver cancelled by user")

    # Extract results back by channel type
    pump_indices = [idx for idx, ch in enumerate(channels) if ch['type'] == 'pump']
    signal_indices = [idx for idx, ch in enumerate(channels) if ch['type'] == 'signal']
    ase_indices = [idx for idx, ch in enumerate(channels) if ch['type'] == 'ase']
    
    return ASEPowerResults(
        z=z,
        pumps_f=P_f[pump_indices, :],
        pumps_b=P_b[pump_indices, :],
        signals_f=P_f[signal_indices, :],
        signals_b=P_b[signal_indices, :],
        ase_f=P_f[ase_indices, :],
        ase_b=P_b[ase_indices, :],
        n2_fraction=n2,
        pump_wavelengths=[channels[idx]['wavelength'] for idx in pump_indices],
        signal_wavelengths=[channels[idx]['wavelength'] for idx in signal_indices],
        ase_wavelengths=[channels[idx]['wavelength'] for idx in ase_indices]
    )
