"""Virtual CCD beam profiler: M^2 beam-quality analysis (ISO 11146) for the
field exiting a fiber facet.

v1 model: the near field at the facet is synthesized from the fiber's guided
LP modes (LP01, plus a heuristic LP11 admixture when the fiber is multimode —
a real device would split power across many HOMs depending on launch
conditions and bend history, which is not modeled here).

Since the synthesized near field carries no imposed phase curvature or tilt,
the fiber facet (z=0) is exactly the beam waist by construction. This lets us
compute M^2 the rigorous ISO 11146 way — from the second moments of the near
field (spatial) and its angular spectrum (far-field, via FFT) — with no
numerical z-propagation needed for the reported numbers, and therefore no
grid-growth/aliasing sensitivity. The camera "images" stack is still produced
by physically propagating the field (angular-spectrum method) so the UI can
show a realistic caustic sweep; only that visualization is subject to the
usual finite-grid clipping far from the waist.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from fibersim.core.fiber import FiberGeometry
from fibersim.solvers.modes.analytical import v_number
from fibersim.solvers.modes.fd import solve_modes_fd


@dataclass
class BeamProfilerResult:
    z_m: np.ndarray             # (num_z,) camera positions relative to the facet
    x_m: np.ndarray             # (Nx,) transverse grid
    y_m: np.ndarray             # (Ny,)
    images: np.ndarray          # (num_z, Nx, Ny) intensity, each plane peak-normalized to 1 (camera-like)
    wx_m: np.ndarray            # (num_z,) D4sigma/2 beam radius vs z (analytic hyperbola), x
    wy_m: np.ndarray
    w0x_m: float
    w0y_m: float
    z0x_m: float
    z0y_m: float
    m2x: float
    m2y: float
    divergence_x_mrad: float
    divergence_y_mrad: float
    bpp_mm_mrad: float
    wavelength_m: float
    v_number: float
    is_single_mode: bool
    waist_index: int            # index into z_m closest to the fitted waist


def _hom_power_fraction(v: float) -> float:
    """Heuristic higher-order-mode power fraction from the V-number.

    Single-mode (V <= 2.405) -> 0. Above cutoff, grows with excess V and
    saturates — a stand-in for real launch-condition-dependent HOM content
    until the plan's Fase 4 modal-decomposition work replaces it.
    """
    if v <= 2.405:
        return 0.0
    return float(min(0.45, (v - 2.405) / 4.0))


def _synthesize_near_field(
    fiber: FiberGeometry, wavelength_m: float, grid_n: int, half_width: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, bool]:
    """Builds the complex near-field E(x, y) at the fiber facet (z=0)."""
    n_co = fiber.refractive_index_profile(0.0, wavelength_m)
    n_cl = fiber.refractive_index_profile(fiber.mode_solving_cladding_radius(), wavelength_m)
    v = v_number(fiber.core_radius, n_co, n_cl, wavelength_m)
    single_mode = v <= 2.405

    x = np.linspace(-half_width, half_width, grid_n)
    y = np.linspace(-half_width, half_width, grid_n)
    X, Y = np.meshgrid(x, y, indexing="ij")
    R = np.sqrt(X**2 + Y**2)
    theta = np.arctan2(Y, X)

    lp01_modes = solve_modes_fd(fiber, wavelength_m, l=0, grid_points=600, r_max=half_width)
    if not lp01_modes:
        raise ValueError("No guided LP01 mode found for this fiber/wavelength — cannot profile the beam.")
    psi01 = lp01_modes[0].get_field_amplitude(R)

    hom_frac = _hom_power_fraction(v)
    field = psi01 * math.sqrt(max(1.0 - hom_frac, 0.0))

    if hom_frac > 0.0:
        lp11_modes = solve_modes_fd(fiber, wavelength_m, l=1, grid_points=600, r_max=half_width)
        if lp11_modes:
            psi11 = lp11_modes[0].get_field_amplitude(R) * np.cos(theta)
            # Normalize LP11 to unit power on this grid before mixing in its share.
            norm11 = math.sqrt(float(np.sum(psi11**2))) or 1.0
            field = field + math.sqrt(hom_frac) * (psi11 / norm11) * math.sqrt(float(np.sum(psi01**2)))

    return x, y, field.astype(complex), v, single_mode


def _second_moments_2d(I: np.ndarray, x: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float]:
    """ISO 11146 D4sigma radii (2*std) and centroids for a 2D intensity map."""
    X, Y = np.meshgrid(x, y, indexing="ij")
    total = float(np.sum(I))
    if total <= 0:
        return 0.0, 0.0, 0.0, 0.0
    xc = float(np.sum(X * I) / total)
    yc = float(np.sum(Y * I) / total)
    var_x = float(np.sum((X - xc) ** 2 * I) / total)
    var_y = float(np.sum((Y - yc) ** 2 * I) / total)
    return 2.0 * math.sqrt(max(var_x, 0.0)), 2.0 * math.sqrt(max(var_y, 0.0)), xc, yc


def _angular_second_moments(field0: np.ndarray, x: np.ndarray, y: np.ndarray,
                            wavelength_m: float) -> tuple[float, float]:
    """Far-field D4sigma divergence half-angles (rad) from the field's angular spectrum.

    theta = 2*std(k)/k0, computed directly from the near field's Fourier
    transform — exact for any near field with no z-propagation required.
    """
    dx = x[1] - x[0]
    dy = y[1] - y[0]
    Nx, Ny = len(x), len(y)
    kx = 2.0 * math.pi * np.fft.fftfreq(Nx, dx)
    ky = 2.0 * math.pi * np.fft.fftfreq(Ny, dy)
    k0 = 2.0 * math.pi / wavelength_m

    field_fft = np.fft.fft2(field0)
    I_ff = np.abs(field_fft) ** 2
    theta_x_2d, theta_y_2d, _, _ = _second_moments_2d(I_ff, kx, ky)
    return theta_x_2d / k0, theta_y_2d / k0


def _propagate_free_space(field0: np.ndarray, x: np.ndarray, y: np.ndarray,
                           wavelength_m: float, z_planes: np.ndarray) -> np.ndarray:
    """Scalar angular-spectrum propagation in free space (n=1) to each z in z_planes.

    Used only to render camera images for the UI; the reported M^2/w0/theta
    numbers come from `_second_moments_2d`/`_angular_second_moments` instead,
    so this function's finite-grid clipping at large |z| does not affect them.
    """
    dx = x[1] - x[0]
    dy = y[1] - y[0]
    Nx, Ny = len(x), len(y)
    kx = 2.0 * math.pi * np.fft.fftfreq(Nx, dx)
    ky = 2.0 * math.pi * np.fft.fftfreq(Ny, dy)
    Kx, Ky = np.meshgrid(kx, ky, indexing="ij")
    K2 = Kx**2 + Ky**2
    k0 = 2.0 * math.pi / wavelength_m
    kz = np.sqrt(np.clip(k0**2 - K2, 0.0, None))  # evanescent components don't propagate

    field_fft = np.fft.fft2(field0)
    out = np.empty((len(z_planes), Nx, Ny), dtype=complex)
    for i, z in enumerate(z_planes):
        out[i] = np.fft.ifft2(field_fft * np.exp(1j * kz * z))
    return out


def solve_lp01_lp11_fields(
    fiber: FiberGeometry, wavelength_m: float, grid_n: int, half_width: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
    """Solves the LP01 (and LP11, if guided) near-field once, each normalized
    to the same total power on this grid, so callers can cheaply blend them
    at any mixing fraction afterward without re-solving modes per fraction
    (used by the Power Ramp explorer to sweep many power steps against one
    mode solve). Returns (x, y, psi01, psi11) — psi11 is None if the fiber
    doesn't guide a distinct LP11 at this wavelength."""
    x = np.linspace(-half_width, half_width, grid_n)
    y = np.linspace(-half_width, half_width, grid_n)
    X, Y = np.meshgrid(x, y, indexing="ij")
    R = np.sqrt(X**2 + Y**2)
    theta = np.arctan2(Y, X)

    lp01_modes = solve_modes_fd(fiber, wavelength_m, l=0, grid_points=600, r_max=half_width)
    if not lp01_modes:
        raise ValueError("No guided LP01 mode found for this fiber/wavelength.")
    psi01 = lp01_modes[0].get_field_amplitude(R)

    psi11 = None
    lp11_modes = solve_modes_fd(fiber, wavelength_m, l=1, grid_points=600, r_max=half_width)
    if lp11_modes:
        psi11_raw = lp11_modes[0].get_field_amplitude(R) * np.cos(theta)
        norm11 = math.sqrt(float(np.sum(psi11_raw**2))) or 1.0
        norm01 = math.sqrt(float(np.sum(psi01**2)))
        psi11 = (psi11_raw / norm11) * norm01

    return x, y, psi01, psi11


def mix_fields_and_measure_m2(
    x: np.ndarray, y: np.ndarray, psi01: np.ndarray, psi11: np.ndarray | None,
    hom_fraction: float, wavelength_m: float,
) -> tuple[float, float, np.ndarray]:
    """Blends a pre-solved LP01/LP11 pair at a given LP11 power fraction and
    measures the rigorous ISO 11146 M^2 of the resulting composite near
    field (same near+far-field second-moment method as `analyze_beam`, just
    skipping the z-propagation image sweep — cheap enough to call once per
    power step in a sweep). Returns (m2x, m2y, composite_field)."""
    f = float(np.clip(hom_fraction, 0.0, 1.0))
    field = psi01 * math.sqrt(max(1.0 - f, 0.0))
    if psi11 is not None and f > 0.0:
        field = field + psi11 * math.sqrt(f)
    field = field.astype(complex)

    w0x, w0y, _, _ = _second_moments_2d(np.abs(field) ** 2, x, y)
    theta_x, theta_y = _angular_second_moments(field, x, y, wavelength_m)
    m2x = max(math.pi * w0x * theta_x / wavelength_m, 1.0)
    m2y = max(math.pi * w0y * theta_y / wavelength_m, 1.0)
    return m2x, m2y, field


def analyze_beam(
    fiber: FiberGeometry,
    wavelength_m: float,
    *,
    grid_n: int = 128,
    num_z: int = 21,
    z_span_factor: float = 6.0,
) -> BeamProfilerResult:
    """Runs the full virtual-CCD M^2 analysis for a fiber's output facet.

    z_span_factor sets the camera sweep range as a multiple of the Rayleigh
    length, used only for the visualization; M^2/w0/divergence are computed
    directly from second moments and are independent of this choice.
    """
    half_width = 4.0 * fiber.core_radius
    x, y, field0, v, single_mode = _synthesize_near_field(fiber, wavelength_m, grid_n, half_width)

    w0x, w0y, _, _ = _second_moments_2d(np.abs(field0) ** 2, x, y)
    theta_x, theta_y = _angular_second_moments(field0, x, y, wavelength_m)

    m2x = max(math.pi * w0x * theta_x / wavelength_m, 1.0)
    m2y = max(math.pi * w0y * theta_y / wavelength_m, 1.0)
    # z0 = 0 by construction (no phase curvature/tilt imposed on the synthesized near field).
    z0x = z0y = 0.0

    z_r = math.pi * 0.5 * (w0x + w0y) ** 2 / wavelength_m
    z_max = z_span_factor * max(z_r, 1e-9)
    z_planes = np.linspace(-z_max, z_max, num_z)

    wx_m = np.sqrt(w0x**2 + (theta_x * z_planes) ** 2)
    wy_m = np.sqrt(w0y**2 + (theta_y * z_planes) ** 2)

    fields = _propagate_free_space(field0, x, y, wavelength_m, z_planes)
    images_raw = np.abs(fields) ** 2
    peaks = images_raw.reshape(len(z_planes), -1).max(axis=1)
    images_norm = images_raw / np.where(peaks[:, None, None] > 0, peaks[:, None, None], 1.0)

    waist_index = int(np.argmin(np.abs(z_planes)))

    return BeamProfilerResult(
        z_m=z_planes,
        x_m=x,
        y_m=y,
        images=images_norm.astype(np.float32),
        wx_m=wx_m,
        wy_m=wy_m,
        w0x_m=w0x,
        w0y_m=w0y,
        z0x_m=z0x,
        z0y_m=z0y,
        m2x=m2x,
        m2y=m2y,
        divergence_x_mrad=theta_x * 1e3,
        divergence_y_mrad=theta_y * 1e3,
        bpp_mm_mrad=0.5 * (w0x + w0y) * 1e3 * 0.5 * (theta_x + theta_y) * 1e3,
        wavelength_m=wavelength_m,
        v_number=v,
        is_single_mode=single_mode,
        waist_index=waist_index,
    )
