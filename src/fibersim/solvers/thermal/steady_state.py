import math
import numpy as np
from typing import Union, Tuple, Dict
from pint import Quantity
from fibersim.core.units import ureg

def solve_thermal_3layer(
    z: np.ndarray,
    heat_per_length: np.ndarray,
    core_radius: Union[float, Quantity],
    cladding_radius: Union[float, Quantity],
    coating_radius: Union[float, Quantity],
    k_core: float = 1.38,
    k_clad: float = 1.38,
    k_coat: float = 0.2,
    h_conv: float = 100.0,
    T_ambient: float = 293.15
) -> Dict[str, Union[np.ndarray, float]]:
    """
    Solves the 3-layer heat transfer equations for an optical fiber (core, cladding, coating).
    
    Arguments:
        z (np.ndarray): 1D array of longitudinal coordinate points (m).
        heat_per_length (np.ndarray): 1D array of heat generation per unit length Q_L(z) in W/m.
        core_radius (Union[float, Quantity]): Radius of the fiber core (m).
        cladding_radius (Union[float, Quantity]): Radius of the cladding (m).
        coating_radius (Union[float, Quantity]): Radius of the coating (m).
        k_core (float): Thermal conductivity of the core (W/m·K). Default: 1.38 (silica).
        k_clad (float): Thermal conductivity of the cladding (W/m·K). Default: 1.38 (silica).
        k_coat (float): Thermal conductivity of the coating polymer (W/m·K). Default: 0.2.
        h_conv (float): Convective heat transfer coefficient at outer coating boundary (W/m²·K). Default: 100.
        T_ambient (float): Ambient/coolant temperature in Kelvin. Default: 293.15 (20°C).
        
    Returns:
        Dict: Contains 'z', 'T0' (center temp in K), 'T_surface' (surface temp in K),
              'T_max_celsius' (max temp in Celsius), and a helper function to retrieve radial temperature profile at any z index.
    """
    # Convert radii to float meters
    a = core_radius.to("meter").magnitude if isinstance(core_radius, Quantity) else float(core_radius)
    b = cladding_radius.to("meter").magnitude if isinstance(cladding_radius, Quantity) else float(cladding_radius)
    c = coating_radius.to("meter").magnitude if isinstance(coating_radius, Quantity) else float(coating_radius)
    
    Q_L = np.asarray(heat_per_length)
    
    # Core center temperature T0(z)
    # T0(z) = T_ambient + Q_L/(2*pi*h_conv*c) + Q_L/(2*pi*k_core) * (ln(b/a) + 0.5) + Q_L * ln(c/b)/(2*pi*k_coat)
    # Note: since the core conductivity k_core is used for core heat generation (uniform in core), the term is 0.5/k_core.
    term_conv = Q_L / (2.0 * math.pi * h_conv * c)
    term_core_clad = (Q_L / (2.0 * math.pi * k_core)) * (np.log(b / a) + 0.5)
    term_coat = (Q_L * np.log(c / b)) / (2.0 * math.pi * k_coat)
    
    T0 = T_ambient + term_conv + term_core_clad + term_coat
    T_surface = T_ambient + term_conv
    
    T_max_celsius = np.max(T0) - 273.15

    def get_radial_profile(z_idx: int, num_r_points: int = 250) -> Tuple[np.ndarray, np.ndarray]:
        """Calculates radial temperature profile T(r) at a specific z position index."""
        r = np.linspace(0, c, num_r_points)
        T_r = np.zeros_like(r)
        
        Q_val = Q_L[z_idx]
        T0_val = T0[z_idx]
        q_val = Q_val / (math.pi * a**2) if a > 0 else 0.0
        
        for i, ri in enumerate(r):
            if ri <= a:
                # Core
                T_r[i] = T0_val - q_val * (ri**2) / (4.0 * k_core)
            elif ri <= b:
                # Cladding
                T_r[i] = T0_val - (Q_val / (4.0 * math.pi * k_core)) - (Q_val * np.log(ri / a) / (2.0 * math.pi * k_clad))
            else:
                # Coating
                T_r[i] = (T0_val - (Q_val / (4.0 * math.pi * k_core)) 
                          - (Q_val * np.log(b / a) / (2.0 * math.pi * k_clad))
                          - (Q_val * np.log(ri / b) / (2.0 * math.pi * k_coat)))
                
        return r, T_r

    return {
        "z": z,
        "T0": T0,
        "T_surface": T_surface,
        "T_max_celsius": T_max_celsius,
        "get_radial_profile": get_radial_profile
    }
