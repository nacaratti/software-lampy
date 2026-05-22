import math
import numpy as np
from typing import Union, Tuple, Dict, Callable, Optional
from pint import Quantity
from fibersim.core.units import ureg
from fibersim.core.fiber import FiberGeometry
from fibersim.solvers.power.ase import JobCancelled

class BPMResults:
    """
    Holds the results of a 3D Beam Propagation Method simulation.
    """
    def __init__(
        self,
        z: np.ndarray,
        x: np.ndarray,
        y: np.ndarray,
        fields: np.ndarray,       # shape: (num_z, Nx, Ny) complex
        powers: np.ndarray        # shape: (num_z,) total power along z
    ):
        self.z = z
        self.x = x
        self.y = y
        self.fields = fields
        self.powers = powers

    @property
    def intensities(self) -> np.ndarray:
        """Returns the 3D intensity profile along z."""
        return np.abs(self.fields)**2


def solve_bpm(
    fiber: FiberGeometry,
    wavelength: Union[float, Quantity],
    initial_field: np.ndarray,        # shape: (Nx, Ny)
    length: Union[float, Quantity],
    z_steps: int = 200,
    grid_width: Union[float, Quantity, None] = None,
    n_ref: Union[float, None] = None,
    absorber_width_fraction: float = 0.15,
    absorber_strength: float = 0.05,
    z_profile_modifier: Union[Callable[[np.ndarray, np.ndarray, float], np.ndarray], None] = None,
    progress_callback: Optional[Callable[[float], Optional[bool]]] = None,
) -> BPMResults:
    """
    Propagates an optical field through a fiber waveguide using the paraxial 3D Split-Step Fourier BPM.
    
    Arguments:
        fiber (FiberGeometry): Waveguide geometry.
        wavelength (Union[float, Quantity]): Wavelength (m).
        initial_field (np.ndarray): 2D complex array of initial transverse field amplitude.
        length (Union[float, Quantity]): Propagation distance (m).
        z_steps (int): Number of steps along the propagation axis z.
        grid_width (Union[float, Quantity, None]): Total grid half-width (m). Defaults to 3 * core_radius.
        n_ref (Union[float, None]): Reference index of refraction. Defaults to cladding index.
        absorber_width_fraction (float): Fraction of grid edge width used for absorber.
        absorber_strength (float): Peak power absorption scaling at grid boundary.
        z_profile_modifier (Callable): Optional function `f(X, Y, z)` returning refractive index profile at z.
        
    Returns:
        BPMResults: Holds coordinates, complex field distributions, and power tracking.
    """
    wl = wavelength.to("meter").magnitude if isinstance(wavelength, Quantity) else float(wavelength)
    L = length.to("meter").magnitude if isinstance(length, Quantity) else float(length)
    
    Nx, Ny = initial_field.shape
    if grid_width is not None:
        w_grid = grid_width.to("meter").magnitude if isinstance(grid_width, Quantity) else float(grid_width)
    else:
        w_grid = 3.0 * fiber.core_radius
        
    # Spatial grid setup
    x = np.linspace(-w_grid, w_grid, Nx)
    y = np.linspace(-w_grid, w_grid, Ny)
    dx = x[1] - x[0]
    dy = y[1] - y[0]
    
    # 2D coordinate mesh
    X, Y = np.meshgrid(x, y, indexing='ij')
    R = np.sqrt(X**2 + Y**2)
    
    # Wavelength constants
    k0 = 2.0 * math.pi / wl
    n_cl = fiber.refractive_index_profile(w_grid, wl)
    n_reference = float(n_ref) if n_ref is not None else n_cl
    beta = k0 * n_reference
    
    # Setup spectral domain coordinates (Fourier frequencies)
    kx = 2.0 * math.pi * np.fft.fftfreq(Nx, dx)
    ky = 2.0 * math.pi * np.fft.fftfreq(Ny, dy)
    Kx, Ky = np.meshgrid(kx, ky, indexing='ij')
    K2 = Kx**2 + Ky**2
    
    # Setup z grid
    z = np.linspace(0.0, L, z_steps)
    dz = L / (z_steps - 1)
    
    # Pre-calculate diffraction operator for half-step dz/2
    # exp( -i * (kx^2 + ky^2) / (4 * beta) * dz )
    diffraction_op = np.exp(-1j * K2 * dz / (4.0 * beta))
    
    # Setup boundary absorber profile (super-Gaussian filter at grid edges)
    # absorber(r) = exp( -strength * (r / boundary_radius)^16 )
    boundary_r = w_grid * (1.0 - absorber_width_fraction)
    absorber = np.exp(-absorber_strength * np.maximum(R - boundary_r, 0.0)**4 / (w_grid * absorber_width_fraction)**4)
    
    # Allocate output arrays
    fields_z = np.zeros((z_steps, Nx, Ny), dtype=complex)
    powers_z = np.zeros(z_steps)
    
    # Initialize propagation field
    psi = initial_field.copy().astype(complex)
    fields_z[0, :, :] = psi
    powers_z[0] = np.sum(np.abs(psi)**2 * dx * dy)

    # Progress is reported at most ~100 times across all z-steps
    progress_stride = max(1, z_steps // 100)

    for idx in range(1, z_steps):
        z_val = z[idx-1]
        
        # 1. Half-step diffraction in Fourier space
        psi_fft = np.fft.fft2(psi)
        psi_fft = psi_fft * diffraction_op
        psi = np.fft.ifft2(psi_fft)
        
        # 2. Full-step refraction in spatial space
        if z_profile_modifier is not None:
            n_profile = z_profile_modifier(X, Y, z_val + dz / 2.0)
        else:
            # For standard geometry, it's z-independent
            n_profile = fiber.refractive_index_profile(R, wl)
            
        # Refraction phase shift: exp( i * k0^2 * (n^2 - n_ref^2) / (2 * beta) * dz )
        refraction_phase = k0**2 * (n_profile**2 - n_reference**2) / (2.0 * beta) * dz
        psi = psi * np.exp(1j * refraction_phase)
        
        # 3. Half-step diffraction in Fourier space
        psi_fft = np.fft.fft2(psi)
        psi_fft = psi_fft * diffraction_op
        psi = np.fft.ifft2(psi_fft)
        
        # 4. Apply boundary absorber to filter edge reflections
        psi = psi * absorber
        
        # Store results
        fields_z[idx, :, :] = psi
        powers_z[idx] = np.sum(np.abs(psi)**2 * dx * dy)

        if progress_callback is not None and (idx % progress_stride == 0 or idx == z_steps - 1):
            cont = progress_callback(idx / (z_steps - 1))
            if cont is False:
                raise JobCancelled("BPM solver cancelled by user")

    return BPMResults(z, x, y, fields_z, powers_z)
