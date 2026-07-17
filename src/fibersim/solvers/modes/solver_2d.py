import math
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.interpolate import RegularGridInterpolator
from typing import List, Tuple, Union
from pint import Quantity
from fibersim.core.units import ureg
from fibersim.core.fiber import FiberGeometry

class FDMode2D:
    """
    Represents a transverse optical mode solved via 2D Finite Differences.
    """
    def __init__(
        self,
        l_approx: int,
        m_approx: int,
        beta: float,
        n_eff: float,
        wavelength: float,
        x_grid: np.ndarray,
        y_grid: np.ndarray,
        psi_2d: np.ndarray
    ):
        self.l_approx = l_approx
        self.m_approx = m_approx
        self.beta = beta
        self.n_eff = n_eff
        self.wavelength = wavelength
        self.x_grid = x_grid
        self.y_grid = y_grid
        self.psi_2d = psi_2d  # 2D field amplitude array

    def get_intensity_2d(self) -> np.ndarray:
        """Returns the 2D normalized intensity profile."""
        return self.psi_2d**2


def _classify_lp_mode(
    psi_2d: np.ndarray,
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    core_radius: float,
) -> Tuple[int, int]:
    """Estimate LP mode orders (l, m) from a 2D field profile via azimuthal FFT and radial node counting."""
    interp = RegularGridInterpolator(
        (x_grid, y_grid), psi_2d,
        method="linear", bounds_error=False, fill_value=0.0,
    )

    # Azimuthal Fourier decomposition at r = 0.5 * core_radius to estimate l
    r_az = 0.5 * core_radius
    n_theta = 256
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)
    pts_az = np.column_stack([r_az * np.cos(theta), r_az * np.sin(theta)])
    az_vals = interp(pts_az)
    fft_coeffs = np.abs(np.fft.rfft(az_vals))
    max_l_search = min(8, len(fft_coeffs) - 1)
    l_est = int(np.argmax(fft_coeffs[: max_l_search + 1]))

    # Radial zero-crossing count along direction of peak amplitude to estimate m
    max_abs_idx = np.unravel_index(np.argmax(np.abs(psi_2d)), psi_2d.shape)
    x_peak = float(x_grid[max_abs_idx[0]])
    y_peak = float(y_grid[max_abs_idx[1]])
    angle = math.atan2(y_peak, x_peak)
    r_rad = np.linspace(0.0, 1.1 * core_radius, 300)
    pts_rad = np.column_stack([r_rad * np.cos(angle), r_rad * np.sin(angle)])
    rad_vals = interp(pts_rad)
    core_vals = rad_vals[r_rad <= core_radius]
    noise_thresh = 0.05 * float(np.max(np.abs(core_vals))) if core_vals.size else 0.0
    core_sig = core_vals[np.abs(core_vals) > noise_thresh]
    if core_sig.size < 2:
        m_est = 1
    else:
        zero_crossings = int(np.sum(np.diff(np.sign(core_sig)) != 0))
        m_est = zero_crossings + 1

    return l_est, m_est


def solve_modes_2d(
    fiber: FiberGeometry,
    wavelength: Union[float, Quantity],
    grid_size: int = 80,
    grid_width: Union[float, Quantity, None] = None,
    num_modes: int = 6
) -> List[FDMode2D]:
    """
    Solves the 2D Helmholtz equation on a Cartesian grid to find guided transverse modes.
    
    Arguments:
        fiber (FiberGeometry): Waveguide geometry.
        wavelength (Union[float, Quantity]): Optical wavelength (m).
        grid_size (int): Number of grid points along x and y (grid will be grid_size x grid_size).
        grid_width (Union[float, Quantity, None]): Total grid width (m). Defaults to 3 * core_radius.
        num_modes (int): Number of eigenvalues/modes to search for near n_core.
        
    Returns:
        List[FDMode2D]: Sorted list of guided modes (highest n_eff first).
    """
    wl = wavelength.to("meter").magnitude if isinstance(wavelength, Quantity) else float(wavelength)
    
    if grid_width is not None:
        w_grid = grid_width.to("meter").magnitude if isinstance(grid_width, Quantity) else float(grid_width)
    else:
        w_grid = 3.0 * fiber.core_radius

    # Create grid axes
    Nx = grid_size
    Ny = grid_size
    x = np.linspace(-w_grid, w_grid, Nx)
    y = np.linspace(-w_grid, w_grid, Ny)
    dx = x[1] - x[0]
    dy = y[1] - y[0]

    # Precompute refractive index profile on the 2D grid
    X, Y = np.meshgrid(x, y, indexing='ij')
    R = np.sqrt(X**2 + Y**2)
    n_2d = fiber.refractive_index_profile(R, wl)

    k = 2.0 * math.pi / wl
    n_co = fiber.refractive_index_profile(0.0, wl)
    n_cl = fiber.refractive_index_profile(w_grid, wl)

    # 1D second derivative sparse matrices (Dirichlet boundaries: psi=0 at edges)
    # Dxx = 1/dx^2 * [1, -2, 1]
    diags_x = np.ones((3, Nx))
    diags_x[0, :] = 1.0 / dx**2
    diags_x[1, :] = -2.0 / dx**2
    diags_x[2, :] = 1.0 / dx**2
    Dxx = sp.spdiags(diags_x, [-1, 0, 1], Nx, Nx, format="csc")

    diags_y = np.ones((3, Ny))
    diags_y[0, :] = 1.0 / dy**2
    diags_y[1, :] = -2.0 / dy**2
    diags_y[2, :] = 1.0 / dy**2
    Dyy = sp.spdiags(diags_y, [-1, 0, 1], Ny, Ny, format="csc")

    # 2D Laplacian operator via Kronecker sums
    Ix = sp.eye(Nx, format="csc")
    Iy = sp.eye(Ny, format="csc")
    L = sp.kron(Dxx, Iy) + sp.kron(Ix, Dyy)

    # Diagonal potential matrix: k^2 * n_2d(x,y)^2
    n_flat = n_2d.flatten()
    V = sp.diags((k * n_flat)**2, 0, format="csc")

    # Full 2D Helmholtz matrix: H = L + V
    H = L + V

    # Target eigenvalue search center (near n_core^2)
    target_sigma = (k * n_co)**2

    # Solve the symmetric sparse matrix eigenvalue problem
    # eigsh finds the closest eigenvalues to target_sigma
    try:
        eigenvalues, eigenvectors = spla.eigsh(
            H,
            k=num_modes,
            sigma=target_sigma,
            which='LM',
            maxiter=1000
        )
    except spla.ArpackNoConvergence as e:
        # Fallback to fewer modes if ARPACK fails to converge
        eigenvalues, eigenvectors = e.eigenvalues, e.eigenvectors
        if len(eigenvalues) == 0:
            return []

    # Process and filter guided modes
    guided_modes = []
    for idx in range(len(eigenvalues)):
        beta_sq = eigenvalues[idx]
        if beta_sq <= 0:
            continue
            
        beta = math.sqrt(beta_sq)
        n_eff = beta / k
        
        # Guided mode criterion: n_cladding < n_eff < n_core
        if n_cl - 1e-4 < n_eff < n_co + 1e-4:
            vec = eigenvectors[:, idx]
            psi_2d = vec.reshape((Nx, Ny))
            
            # Normalize 2D field profile: Double Integral (psi^2 dx dy) = 1
            norm = np.sqrt(np.sum(psi_2d**2 * dx * dy))
            if norm > 1e-12:
                psi_2d = psi_2d / norm
                
            # Align sign so peak amplitude is positive
            max_idx = np.unravel_index(np.argmax(np.abs(psi_2d)), psi_2d.shape)
            if psi_2d[max_idx] < 0:
                psi_2d = -psi_2d
                
            guided_modes.append((n_eff, beta, psi_2d))

    # Sort guided modes by n_eff in descending order
    guided_modes.sort(key=lambda val: val[0], reverse=True)

    modes_list = []
    for _m_idx, (n_eff, beta, psi_2d) in enumerate(guided_modes):
        l_approx, m_approx = _classify_lp_mode(psi_2d, x, y, fiber.core_radius)
        mode = FDMode2D(
            l_approx=l_approx,
            m_approx=m_approx,
            beta=beta,
            n_eff=n_eff,
            wavelength=wl,
            x_grid=x,
            y_grid=y,
            psi_2d=psi_2d
        )
        modes_list.append(mode)

    return modes_list
