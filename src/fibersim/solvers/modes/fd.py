import math
import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from typing import List, Tuple, Union
from pint import Quantity
from fibersim.core.units import ureg
from fibersim.core.fiber import FiberGeometry
from fibersim.solvers.modes.analytical import Mode

class FDMode(Mode):
    """
    Represents a mode solved via Finite Differences, extending the analytical Mode.
    Adds the radial grid and radial field profile.
    """
    def __init__(
        self,
        u: float,
        w: float,
        l: int,
        m: int,
        beta: float,
        n_eff: float,
        core_radius: float,
        wavelength: float,
        n_core: float,
        n_cladding: float,
        r_grid: np.ndarray,
        psi: np.ndarray
    ):
        super().__init__(u, w, l, m, beta, n_eff, core_radius, wavelength, n_core, n_cladding)
        self.r_grid = r_grid
        self.psi = psi

    def get_field_amplitude(self, r: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """Interpolates the radial field profile at arbitrary radial coordinates r."""
        return np.interp(np.abs(r), self.r_grid, self.psi, left=0.0, right=0.0)


def solve_modes_fd(
    fiber: FiberGeometry,
    wavelength: Union[float, Quantity],
    l: int,
    grid_points: int = 800,
    r_max: Union[float, Quantity, None] = None
) -> List[FDMode]:
    """
    Solves for the LP modes of order 'l' using the Radial Finite Differences method.
    
    Arguments:
        fiber (FiberGeometry): Waveguide geometry.
        wavelength (Union[float, Quantity]): Wavelength (assumes meters if float).
        l (int): Azimuthal mode order.
        grid_points (int): Number of radial grid points.
        r_max (Union[float, Quantity, None]): Grid radius limit. Defaults to 4 * core_radius.
        
    Returns:
        List[FDMode]: Sorted list of guided modes for the given l (highest n_eff first).
    """
    wl = wavelength.to("meter").magnitude if isinstance(wavelength, Quantity) else float(wavelength)
    
    if r_max is not None:
        rm = r_max.to("meter").magnitude if isinstance(r_max, Quantity) else float(r_max)
    else:
        rm = 4.0 * fiber.core_radius

    dr = rm / (grid_points - 1)
    k = 2.0 * math.pi / wl

    # 1. Refractive index profile definitions
    n_co = fiber.refractive_index_profile(0.0, wl)
    n_cl = fiber.refractive_index_profile(rm, wl)

    if l == 0:
        M = grid_points - 1
        r = np.arange(M) * dr
        n_r = fiber.refractive_index_profile(r, wl)
        
        diags = np.zeros(M)
        upper = np.zeros(M - 1)
        lower = np.zeros(M - 1)
        
        # Row 0: boundary condition at r=0 for l=0 is psi' = 0
        # psi'' + 1/r * psi' -> 2 * psi'' as r->0. 
        # Using centered difference ghost point: A[0,0] = -4/dr^2 + k^2*n^2, A[0,1] = 4/dr^2
        diags[0] = -4.0 / dr**2 + (k * n_r[0])**2
        upper[0] = 4.0 / dr**2
        
        # Rows 1 to M-1
        for i in range(1, M):
            ri = r[i]
            diags[i] = -2.0 / dr**2 + (k * n_r[i])**2
            if i < M - 1:
                upper[i] = 1.0 / dr**2 + 1.0 / (2.0 * ri * dr)
            lower[i - 1] = 1.0 / dr**2 - 1.0 / (2.0 * ri * dr)
            
        A = np.diag(diags) + np.diag(upper, 1) + np.diag(lower, -1)
    else:
        M = grid_points - 2
        # For l > 0, psi(0) = 0. Grid runs from r[1] to r[grid_points-2].
        r_all = np.arange(grid_points) * dr
        r = r_all[1:-1]
        n_r = fiber.refractive_index_profile(r, wl)
        
        diags = np.zeros(M)
        upper = np.zeros(M - 1)
        lower = np.zeros(M - 1)
        
        for idx in range(M):
            ri = r[idx]
            diags[idx] = -2.0 / dr**2 + (k * n_r[idx])**2 - (l / ri)**2
            if idx < M - 1:
                upper[idx] = 1.0 / dr**2 + 1.0 / (2.0 * ri * dr)
            if idx > 0:
                lower[idx - 1] = 1.0 / dr**2 - 1.0 / (2.0 * ri * dr)
                
        A = np.diag(diags) + np.diag(upper, 1) + np.diag(lower, -1)

    # 2. Solve eigenvalue problem: A * psi = beta^2 * psi
    # Sparse shift-invert near the core to extract only top-k guided eigenvalues.
    # Much faster than dense eig() for grid_points >> 100.
    A_sp = sp.csr_matrix(A)
    target_sigma = (k * n_co) ** 2
    k_eigs = min(M - 2, 10)
    try:
        eigenvalues, eigenvectors = spla.eigs(
            A_sp, k=k_eigs, sigma=target_sigma, which="LM", maxiter=2000
        )
    except (spla.ArpackNoConvergence, spla.ArpackError):
        # Dense fallback when ARPACK fails for tricky profiles.
        eigenvalues, eigenvectors = la.eig(A)

    # 3. Filter for guided modes
    guided_modes = []

    for idx in range(len(eigenvalues)):
        beta_sq = np.real(eigenvalues[idx])
        imag_part = np.imag(eigenvalues[idx])

        # Check if eigenvalue corresponds to a physical guided mode
        if abs(imag_part) < 1e-7 and beta_sq > 0:
            beta = math.sqrt(beta_sq)
            n_eff = beta / k
            
            # Guide mode index condition
            if n_cl < n_eff < n_co:
                vec = np.real(eigenvectors[:, idx])
                
                # Reconstruct full radial field including boundaries
                r_full = np.arange(grid_points) * dr
                psi_full = np.zeros(grid_points)
                
                if l == 0:
                    psi_full[:-1] = vec
                    psi_full[-1] = 0.0
                else:
                    psi_full[0] = 0.0
                    psi_full[1:-1] = vec
                    psi_full[-1] = 0.0
                
                # Normalize field: Int( psi^2 * 2*pi*r * dr ) = 1
                integrand = (psi_full**2) * 2.0 * np.pi * r_full * dr
                norm = np.sqrt(np.sum(integrand))
                
                if norm > 1e-12:
                    psi_full = psi_full / norm
                    
                    # Ensure positive amplitude at center or peak for plotting
                    max_idx = np.argmax(np.abs(psi_full))
                    if psi_full[max_idx] < 0:
                        psi_full = -psi_full
                        
                    # Calculate standard step-index constants u, w for analytical reference
                    # u^2 = (k^2 * n_co^2 - beta^2) * a^2
                    # w^2 = (beta^2 - k^2 * n_cl^2) * a^2
                    u_val = math.sqrt(max((k * n_co)**2 - beta**2, 0.0)) * fiber.core_radius
                    w_val = math.sqrt(max(beta**2 - (k * n_cl)**2, 0.0)) * fiber.core_radius
                    
                    guided_modes.append((n_eff, beta, u_val, w_val, psi_full))

    # Sort guided modes by n_eff descending
    guided_modes.sort(key=lambda x: x[0], reverse=True)
    
    modes = []
    for m_idx, (n_eff, beta, u, w, psi) in enumerate(guided_modes):
        r_full = np.arange(grid_points) * dr
        mode = FDMode(
            u=u,
            w=w,
            l=l,
            m=m_idx + 1,
            beta=beta,
            n_eff=n_eff,
            core_radius=fiber.core_radius,
            wavelength=wl,
            n_core=n_co,
            n_cladding=n_cl,
            r_grid=r_full,
            psi=psi
        )
        modes.append(mode)
        
    return modes
