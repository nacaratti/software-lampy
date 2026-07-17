"""Analytical LP-mode theory for step-index fibers (Gloge approximation).

UNITS: these functions are unit-agnostic in length — `core_radius` and
`wavelength` only need to share the SAME length unit (SI meters recommended,
matching the rest of fibersim). `beta` is returned in the reciprocal of that
unit; `n_eff`, `u`, `w` and V are dimensionless.
"""
import math
import numpy as np
from scipy.special import jv, kn
from scipy.optimize import minimize_scalar

class Mode:
    """Class used to store parameters of a mode, and to plot it.

    Attributes:
        u (float): Radial propagation constant in the core.
        w (float): Radial propagation constant in the cladding.
        l (int): Azimuthal mode number.
        m (int): Radial mode number.
        beta (float): Propagation constant of the mode (1/[length unit used]).
        n_eff (float): Effective refractive index of the mode.
        core_radius (float): Radius of the fibre core (same length unit as wavelength).
        wavelength (float): Wavelength of the light in the mode (same length unit as core_radius).
        n_core (float): Refractive index of the fibre core.
        n_cladding (float): Refractive index of the cladding.
    """

    def __init__(self, u, w, l, m, beta, n_eff, core_radius, wavelength, n_core, n_cladding):
        self.u = u
        self.w = w
        self.l = l
        self.m = m
        self.beta = beta
        self.n_eff = n_eff
        self.core_radius = core_radius
        self.wavelength = wavelength
        self.n_core = n_core
        self.n_cladding = n_cladding

    def __eq__(self, other):
        if not isinstance(other, Mode):
            return False
        return (self.u == other.u and self.w == other.w and self.l == other.l and
                self.m == other.m and self.beta == other.beta and
                self.n_eff == other.n_eff and
                self.core_radius == other.core_radius and
                self.wavelength == other.wavelength and self.n_core == other.n_core and
                self.n_cladding == other.n_cladding)

    def plot_amplitude(self, grid_size, max_plot_radius):
        """Returns 2D numpy array containing the mode field amplitude (cosine version)."""
        gridCentre = grid_size // 2
        mode_cos = np.zeros((grid_size, grid_size))

        gridPoints = np.arange(0, grid_size, 1) - gridCentre
        xMesh, yMesh = np.meshgrid(gridPoints, gridPoints)

        angle = np.arctan2(yMesh, xMesh)
        rad = np.sqrt(xMesh**2 + yMesh**2)
        rad = rad / (grid_size / 2) * max_plot_radius

        cosTerm = np.cos(self.l * angle)

        coreBessel = jv(self.l, self.u / self.core_radius * rad) / jv(self.l, self.u)
        claddingBessel = kn(self.l, self.w / self.core_radius * rad) / kn(self.l, self.w)

        in_core = (rad <= self.core_radius) * (rad <= max_plot_radius)
        in_cladding = (rad > self.core_radius) * (rad <= max_plot_radius)

        mode_cos[in_core] = coreBessel[in_core] * cosTerm[in_core]
        mode_cos[in_cladding] = claddingBessel[in_cladding] * cosTerm[in_cladding]

        cos_norm = np.sqrt(np.sum(np.abs(mode_cos) ** 2))
        if cos_norm != 0:
            mode_cos = mode_cos / cos_norm
       
        return mode_cos

    def plot_amplitude_rotated(self, grid_size, max_plot_radius):
        """Returns 2D numpy array containing the mode field amplitude (sine version)."""
        if self.l == 0:
            return self.plot_amplitude(grid_size, max_plot_radius)
       
        gridCentre = grid_size // 2
        mode_sin = np.zeros((grid_size, grid_size))

        gridPoints = np.arange(0, grid_size, 1) - gridCentre
        xMesh, yMesh = np.meshgrid(gridPoints, gridPoints)

        angle = np.arctan2(yMesh, xMesh)
        rad = np.sqrt(xMesh**2 + yMesh**2)
        rad = rad / (grid_size / 2) * max_plot_radius

        sinTerm = np.sin(self.l * angle)

        coreBessel = jv(self.l, self.u / self.core_radius * rad) / jv(self.l, self.u)
        claddingBessel = kn(self.l, self.w / self.core_radius * rad) / kn(self.l, self.w)

        in_core = (rad <= self.core_radius) * (rad <= max_plot_radius)
        in_cladding = (rad > self.core_radius) * (rad <= max_plot_radius)

        mode_sin[in_core] = coreBessel[in_core] * sinTerm[in_core]
        mode_sin[in_cladding] = claddingBessel[in_cladding] * sinTerm[in_cladding]

        sin_norm = np.sqrt(np.sum(np.abs(mode_sin)**2))
        if sin_norm != 0:
            mode_sin = mode_sin / sin_norm
            
        return mode_sin

    def plot_intensity(self, grid_size, max_plot_radius):
        """Returns 2D numpy array containing the mode intensity (cosine version)."""
        return np.abs(self.plot_amplitude(grid_size, max_plot_radius))**2
    
    def plot_intensity_rotated(self, grid_size, max_plot_radius):
        """Returns 2D numpy array containing the mode intensity (sine version)."""
        return np.abs(self.plot_amplitude_rotated(grid_size, max_plot_radius))**2


def v_number(core_radius, n_core, n_cladding, wavelength):
    """Calculates the fiber V number."""
    na = math.sqrt(n_core**2 - n_cladding**2)
    return (2 * math.pi / wavelength) * core_radius * na


def est_num_modes(core_radius, n_core, n_cladding, wavelength):
    """Estimates number of modes supported by a fiber using V number."""
    v = v_number(core_radius, n_core, n_cladding, wavelength)
    return np.round((v**2) / 2)


def find_modes(core_radius, n_core, n_cladding, wavelength):
    """Finds all LP modes for a step index fiber by solving the dispersion relation."""
    modes = []
    v = v_number(core_radius, n_core, n_cladding, wavelength)
    k = 2 * math.pi / wavelength

    fineNPoints = 1000
    fineURange = np.linspace(0, v - .1, fineNPoints)

    iL = 0
    residual = np.zeros(len(fineURange))
    signChange = np.zeros(len(fineURange))

    while True:
        # Coarse search
        for idx, u_val in enumerate(fineURange):
            residual[idx] = __calculate_LP_mismatch(
                core_radius, n_core, n_cladding, wavelength, iL, u_val
            )
            if idx > 1:
                signChange[idx] = (np.sign(residual[idx]) != np.sign(residual[idx-1])) and (residual[idx] > residual[idx-1])

        coarseSolutions = np.argwhere(signChange)

        if len(coarseSolutions) == 0:
            return modes

        # Fine search/minimization
        for idx, solution in enumerate(coarseSolutions):
            # np.argwhere returns shape (N, 1); coerce to scalar int for clean indexing
            sol_idx = int(np.atleast_1d(solution).ravel()[0])
            minRange = float(fineURange[sol_idx - 1])
            maxRange = float(fineURange[sol_idx])

            def wrapper(arg):
                return __calculate_LP_mismatch(core_radius, n_core, n_cladding, wavelength, iL, arg)

            res = minimize_scalar(wrapper, bounds=(minRange, maxRange), method='bounded')
            u_opt = res.x
            # Ensure scalar float format across Scipy versions
            if hasattr(u_opt, '__len__') or isinstance(u_opt, (np.ndarray, list)):
                u = float(u_opt[0])
            else:
                u = float(u_opt)

            beta = math.sqrt(k**2 * n_core**2 - (u / core_radius)**2)
            w = math.sqrt(v**2 - u**2)
            m = idx + 1
            l = iL
            n_eff = beta / k

            mode = Mode(u, w, l, m, beta, n_eff, core_radius, wavelength, n_core, n_cladding)
            modes.append(mode)

        iL += 1


def __calculate_LP_mismatch(core_radius, core_n, cladding_n, wavelength, order, u):
    """Calculates the mismatch in the LP mode boundary condition equation."""
    k = 2 * math.pi / wavelength
    u_f = float(np.squeeze(u))
    beta_arg = k**2 * core_n**2 - (u_f / core_radius)**2
    if beta_arg <= 0:
        return 1e6  # large mismatch — pushes optimizer away from invalid region
    beta = math.sqrt(beta_arg)
    w_arg = beta**2 - k**2 * cladding_n**2
    if w_arg <= 0:
        return 1e6
    w = core_radius * math.sqrt(w_arg)

    den = u_f * jv(order - 1, u_f)
    if den != 0:
        coreTerm = jv(order, u_f) / den
    else:
        coreTerm = 0.0

    cl_den = w * kn(order - 1, w)
    if cl_den == 0:
        return 1e6
    claddingTerm = kn(order, w) / cl_den
    return float(coreTerm + claddingTerm)


def num_rotated_modes(modes):
    """Returns number of modes when rotations are counted as separate modes."""
    return len(modes) + sum(1 for mode in modes if mode.l > 0)


def find_mode(modes, l, m):
    """Finds mode with specific l and m values in a list of Modes."""
    for mode in modes:
        if mode.l == l and mode.m == m:
            return mode
    return None


def find_mode_idx(modes, l, m):
    """Finds index of mode with specific l and m values in a list of Modes."""
    for idx, mode in enumerate(modes):
        if mode.l == l and mode.m == m:
            return idx
    return None


def plot_modes_amplitude(modes, grid_size, max_plot_radius):
    """Plots and returns cosine and sine versions of all modes in list."""
    num_m = len(modes)
    mode_cos_all = np.zeros((num_m, grid_size, grid_size))
    mode_sin_all = np.zeros((num_m, grid_size, grid_size))

    for idx, mode in enumerate(modes):
        mode_cos_all[idx] = mode.plot_amplitude(grid_size, max_plot_radius)
        mode_sin_all[idx] = mode.plot_amplitude_rotated(grid_size, max_plot_radius)

    return mode_cos_all, mode_sin_all
