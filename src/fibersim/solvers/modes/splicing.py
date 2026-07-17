"""Splice-loss estimation via LP01 overlap integrals.

UNITS: unlike the rest of fibersim (SI meters), this module's public API takes
micrometers/nanometers/milliradians, as spelled out by the parameter suffixes
(`radius_um*`, `wavelength_nm`, `offset_*_um`, `tilt_*_mrad`). Do NOT pass SI
meters here — a `FiberGeometry.core_radius` (meters) must be converted with
`* 1e6` first.
"""
import numpy as np
from scipy.special import jv, kn
from fibersim.solvers.modes.analytical import find_modes, find_mode

def evaluate_lp01_field(x, y, u, w, core_radius, l=0):
    """
    Evaluates the LP01 field amplitude at given x, y coordinates.
    Since LP01 has l=0, it is azimuthally symmetric.
    """
    r = np.sqrt(x**2 + y**2)
    field = np.zeros_like(r)
    
    in_core = r <= core_radius
    in_clad = ~in_core
    
    # Core (J0 Bessel function)
    if np.any(in_core):
        # Prevent division by zero if u is zero (not physical, but for robustness)
        u_val = max(u, 1e-9)
        field[in_core] = jv(0, u_val / core_radius * r[in_core]) / jv(0, u_val)
        
    # Cladding (K0 modified Bessel function)
    if np.any(in_clad):
        w_val = max(w, 1e-9)
        field[in_clad] = kn(0, w_val / core_radius * r[in_clad]) / kn(0, w_val)
        
    return field

def calculate_splicing_overlap(
    core_n1, cladding_n1, radius_um1,
    core_n2, cladding_n2, radius_um2,
    wavelength_nm,
    offset_x_um=0.0, offset_y_um=0.0,
    tilt_x_mrad=0.0, tilt_y_mrad=0.0,
    grid_size=128
):
    """
    Calculates the overlap integral and splicing loss between two fibers.
    
    Returns:
        coupling_coefficient (float): LP01 to LP01 coupling fraction
        loss_db (float): Splicing loss in dB
        field_1 (ndarray): Source 2D field intensity
        field_2 (ndarray): Destination 2D field intensity (offset and tilted)
        extent_um (float): Half width of the grid in micrometers
    """
    wavelength_um = wavelength_nm * 1e-3  # Convert nm to um
    
    # Find modes for Fiber 1 (source)
    modes1 = find_modes(radius_um1, core_n1, cladding_n1, wavelength_um)
    # Find modes for Fiber 2 (destination)
    modes2 = find_modes(radius_um2, core_n2, cladding_n2, wavelength_um)
    
    if not modes1 or not modes2:
        raise ValueError("Could not find guided modes for one or both fibers.")
        
    lp01_1 = find_mode(modes1, 0, 1)
    lp01_2 = find_mode(modes2, 0, 1)
    
    if not lp01_1 or not lp01_2:
        # Fallback: take the first mode in the list
        lp01_1 = modes1[0]
        lp01_2 = modes2[0]

    # Define shared grid
    max_radius = max(radius_um1, radius_um2) * 2.5
    extent_um = max_radius
    
    xs = np.linspace(-extent_um, extent_um, grid_size)
    ys = np.linspace(-extent_um, extent_um, grid_size)
    X, Y = np.meshgrid(xs, ys)
    
    # Evaluate Fiber 1 field (centered, real)
    E1 = evaluate_lp01_field(X, Y, lp01_1.u, lp01_1.w, radius_um1)
    
    # Evaluate Fiber 2 field (offset coordinates, complex due to tilt phase)
    X_shifted = X - offset_x_um
    Y_shifted = Y - offset_y_um
    E2_amp = evaluate_lp01_field(X_shifted, Y_shifted, lp01_2.u, lp01_2.w, radius_um2)
    
    # Tilt phase factor: exp(i * (kx * x + ky * y))
    # Wavevector magnitude in the core: k = 2 * pi * n_core / wavelength
    k = 2.0 * np.pi * core_n2 / wavelength_um
    kx = k * (tilt_x_mrad * 1e-3)
    ky = k * (tilt_y_mrad * 1e-3)
    tilt_phase = np.exp(1j * (kx * X + ky * Y))
    
    E2 = E2_amp * tilt_phase
    
    # Overlap integral: |iint E1 * E2^* dx dy|^2 / (iint |E1|^2 * iint |E2|^2)
    numerator = np.abs(np.sum(E1 * np.conj(E2)))**2
    denominator = np.sum(np.abs(E1)**2) * np.sum(np.abs(E2)**2)
    
    if denominator > 0:
        coupling_coefficient = float(numerator / denominator)
    else:
        coupling_coefficient = 0.0
        
    coupling_coefficient = min(max(coupling_coefficient, 0.0), 1.0)
    
    if coupling_coefficient > 0:
        loss_db = float(-10.0 * np.log10(coupling_coefficient))
    else:
        loss_db = float('inf')
        
    # Calculate coupling to all guided modes of Fiber 2
    total_coupling = 0.0
    for mode in modes2:
        # Evaluate this mode's amplitude with rotation/symmetry if needed,
        # but for coupling simple LP modes, we check cosine and sine terms.
        # Since E1 has l=0 (azimuthal symmetry), it will only couple to modes with l=0.
        # For non-zero l, the azimuthal overlap int_0^2pi cos(l theta) dtheta = 0.
        # So we only couple to l=0 modes. Let's do a general projection just in case.
        if mode.l == 0:
            E_mode_amp = evaluate_lp01_field(X_shifted, Y_shifted, mode.u, mode.w, radius_um2)
            E_mode = E_mode_amp * tilt_phase
            num_m = np.abs(np.sum(E1 * np.conj(E_mode)))**2
            den_m = np.sum(np.abs(E1)**2) * np.sum(np.abs(E_mode)**2)
            if den_m > 0:
                total_coupling += float(num_m / den_m)

    total_coupling = min(max(total_coupling, 0.0), 1.0)
    total_loss_db = float(-10.0 * np.log10(total_coupling)) if total_coupling > 0 else float('inf')
        
    return {
        'coupling_coefficient': coupling_coefficient,
        'loss_db': loss_db,
        'total_coupling': total_coupling,
        'total_loss_db': total_loss_db,
        'field_1': np.abs(E1)**2,
        'field_2': np.abs(E2)**2,
        'extent_um': extent_um
    }
