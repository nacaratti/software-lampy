"""Adapters that call fibersim solvers and convert results to API responses."""
from __future__ import annotations
import math
import numpy as np
from typing import Callable, Optional

from fibersim.solvers.modes.analytical import (
    find_modes,
    v_number,
)
from fibersim.solvers.modes.fd import solve_modes_fd
from fibersim.solvers.modes.solver_2d import solve_modes_2d
from fibersim.solvers.power.ase import solve_ase
from fibersim.solvers.propagation.bpm import solve_bpm

from backend.app.schemas.modes import (
    ModeAnalyticalRequest,
    ModeFDRequest,
    Mode2DRequest,
    ModesResponse,
    ModeResult,
)
from backend.app.schemas.fiber import StepIndexConfig
from backend.app.schemas.power import PowerASERequest, PowerASEResponse
from backend.app.schemas.bpm import BPMRequest, BPMResponse
from backend.app.services.fiber_builder import (
    build_fiber,
    build_active_fiber,
)
from backend.app.services.encoders import encode_array


# ---------- Mode solvers (synchronous, fast) ----------

def run_modes_analytical(req: ModeAnalyticalRequest) -> ModesResponse:
    if not isinstance(req.fiber, StepIndexConfig):
        raise ValueError(
            "Analytical LP solver only supports step-index fibers. "
            "Use radial FD or full 2D for graded or double-clad geometries."
        )
    fiber = build_fiber(req.fiber)
    wl_m = req.wavelength_nm * 1e-9
    n_co = fiber.refractive_index_profile(0.0, wl_m)
    n_cl = fiber.refractive_index_profile(fiber.mode_solving_cladding_radius(), wl_m)
    vn = v_number(fiber.core_radius, n_co, n_cl, wl_m)
    modes = find_modes(fiber.core_radius, n_co, n_cl, wl_m)
    max_r = req.max_plot_radius_factor * fiber.core_radius

    mode_results: list[ModeResult] = []
    half = req.grid_size // 2
    xs = (np.arange(req.grid_size) - half) / half * max_r
    ys = (np.arange(req.grid_size) - half) / half * max_r
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    R = np.sqrt(X ** 2 + Y ** 2)
    in_core = R <= fiber.core_radius
    pixel_area_um2 = (2.0 * max_r * 1e6 / req.grid_size) ** 2

    for mode in modes:
        amp = mode.plot_amplitude(req.grid_size, max_r)
        intensity = (amp ** 2).astype(np.float32)
        sum_int = np.sum(intensity)
        sum_int2 = np.sum(intensity ** 2)
        a_eff = (sum_int ** 2) / sum_int2 * pixel_area_um2 if sum_int2 > 0 else 0.0
        p_core = float(np.sum(intensity[in_core]) / sum_int * 100.0) if sum_int > 0 else 0.0

        mode_results.append(ModeResult(
            l=mode.l,
            m=mode.m,
            n_eff=float(mode.n_eff),
            beta=float(mode.beta),
            u=float(mode.u),
            w=float(mode.w),
            a_eff_um2=float(a_eff),
            power_core_pct=float(p_core),
            intensity_2d=encode_array(intensity),
            extent_um=max_r * 1e6,
        ))

    return ModesResponse(
        method="analytical",
        wavelength_nm=req.wavelength_nm,
        n_core=float(n_co),
        n_cladding=float(n_cl),
        v_number=float(vn),
        num_modes=len(mode_results),
        modes=mode_results,
    )


def _project_radial_to_2d(r_grid: np.ndarray, psi: np.ndarray, l: int,
                          grid_size: int, max_r: float) -> np.ndarray:
    """Build a 2D intensity image from a radial profile psi(r) and azimuthal order l."""
    half = grid_size // 2
    xs = (np.arange(grid_size) - half) / half * max_r
    ys = (np.arange(grid_size) - half) / half * max_r
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    R = np.sqrt(X ** 2 + Y ** 2)
    theta = np.arctan2(Y, X)
    radial = np.interp(R, r_grid, psi, left=0.0, right=0.0)
    amp = radial * np.cos(l * theta)
    return (amp ** 2).astype(np.float32)


def run_modes_fd(req: ModeFDRequest) -> ModesResponse:
    fiber = build_fiber(req.fiber)
    wl_m = req.wavelength_nm * 1e-9
    n_co = fiber.refractive_index_profile(0.0, wl_m)
    n_cl = fiber.refractive_index_profile(fiber.mode_solving_cladding_radius(), wl_m)
    vn = v_number(fiber.core_radius, n_co, n_cl, wl_m)
    fd_modes = solve_modes_fd(fiber, wl_m, l=req.l, grid_points=req.grid_points)

    max_r = req.max_plot_radius_factor * fiber.core_radius
    mode_results: list[ModeResult] = []
    half = req.plot_grid_size // 2
    xs = (np.arange(req.plot_grid_size) - half) / half * max_r
    ys = (np.arange(req.plot_grid_size) - half) / half * max_r
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    R = np.sqrt(X ** 2 + Y ** 2)
    in_core = R <= fiber.core_radius
    pixel_area_um2 = (2.0 * max_r * 1e6 / req.plot_grid_size) ** 2

    for mode in fd_modes:
        intensity = _project_radial_to_2d(
            mode.r_grid, mode.psi, req.l, req.plot_grid_size, max_r
        )
        sum_int = np.sum(intensity)
        sum_int2 = np.sum(intensity ** 2)
        a_eff = (sum_int ** 2) / sum_int2 * pixel_area_um2 if sum_int2 > 0 else 0.0
        p_core = float(np.sum(intensity[in_core]) / sum_int * 100.0) if sum_int > 0 else 0.0

        mode_results.append(ModeResult(
            l=mode.l,
            m=mode.m,
            n_eff=float(mode.n_eff),
            beta=float(mode.beta),
            u=float(mode.u) if mode.u is not None else None,
            w=float(mode.w) if mode.w is not None else None,
            a_eff_um2=float(a_eff),
            power_core_pct=float(p_core),
            intensity_2d=encode_array(intensity),
            extent_um=max_r * 1e6,
        ))

    return ModesResponse(
        method="fd",
        wavelength_nm=req.wavelength_nm,
        n_core=float(n_co),
        n_cladding=float(n_cl),
        v_number=float(vn),
        num_modes=len(mode_results),
        modes=mode_results,
    )


def run_modes_2d(req: Mode2DRequest) -> ModesResponse:
    fiber = build_fiber(req.fiber)
    wl_m = req.wavelength_nm * 1e-9
    n_co = fiber.refractive_index_profile(0.0, wl_m)
    n_cl = fiber.refractive_index_profile(fiber.mode_solving_cladding_radius(), wl_m)
    grid_w = req.grid_width_factor * fiber.core_radius
    modes_2d = solve_modes_2d(
        fiber, wl_m,
        grid_size=req.grid_size,
        grid_width=grid_w,
        num_modes=req.num_modes,
    )

    half = req.grid_size // 2
    xs = (np.arange(req.grid_size) - half) / half * grid_w
    ys = (np.arange(req.grid_size) - half) / half * grid_w
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    R = np.sqrt(X ** 2 + Y ** 2)
    in_core = R <= fiber.core_radius
    pixel_area_um2 = (2.0 * grid_w * 1e6 / req.grid_size) ** 2

    mode_results: list[ModeResult] = []
    for mode in modes_2d:
        intensity = (mode.psi_2d ** 2).astype(np.float32)
        sum_int = np.sum(intensity)
        sum_int2 = np.sum(intensity ** 2)
        a_eff = (sum_int ** 2) / sum_int2 * pixel_area_um2 if sum_int2 > 0 else 0.0
        p_core = float(np.sum(intensity[in_core]) / sum_int * 100.0) if sum_int > 0 else 0.0

        mode_results.append(ModeResult(
            l=mode.l_approx,
            m=mode.m_approx,
            n_eff=float(mode.n_eff),
            beta=float(mode.beta),
            u=None,
            w=None,
            a_eff_um2=float(a_eff),
            power_core_pct=float(p_core),
            intensity_2d=encode_array(intensity),
            extent_um=grid_w * 1e6,
        ))

    return ModesResponse(
        method="2d",
        wavelength_nm=req.wavelength_nm,
        n_core=float(n_co),
        n_cladding=float(n_cl),
        v_number=None,
        num_modes=len(mode_results),
        modes=mode_results,
    )


# ---------- ASE power (long-running) ----------

def _db_per_m_to_inv_m(loss_db_per_m: float) -> float:
    return (loss_db_per_m / 10.0) * math.log(10.0)


def run_ase(
    req: PowerASERequest,
    progress_callback: Optional[Callable[[float], Optional[bool]]] = None,
) -> PowerASEResponse:
    active_fiber = build_active_fiber(req.active_fiber)
    pumps = [
        {
            "wavelength": p.wavelength_nm * 1e-9,
            "power_in_f": p.power_forward_w,
            "power_in_b": p.power_backward_w,
            "overlap": p.overlap,
            "loss": _db_per_m_to_inv_m(p.loss_db_per_m),
        }
        for p in req.pumps
    ]
    signals = [
        {
            "wavelength": s.wavelength_nm * 1e-9,
            "power_in_f": s.power_forward_w,
            "power_in_b": s.power_backward_w,
            "overlap": s.overlap,
            "loss": _db_per_m_to_inv_m(s.loss_db_per_m),
            "R1": s.reflectivity_input,
            "R2": s.reflectivity_output,
        }
        for s in req.signals
    ]
    ase_cfg = {
        "wl_min": req.ase.wavelength_min_nm * 1e-9,
        "wl_max": req.ase.wavelength_max_nm * 1e-9,
        "num_channels": req.ase.num_channels if req.ase.enabled else 0,
        "overlap": req.ase.overlap,
        "loss": _db_per_m_to_inv_m(req.ase.loss_db_per_m),
        "R1": 0.0,
        "R2": 0.0,
    }

    result = solve_ase(
        active_fiber=active_fiber,
        length=req.length_m,
        pumps=pumps,
        signals=signals,
        ase_config=ase_cfg,
        num_z_points=req.num_z_points,
        max_iterations=req.max_iterations,
        tolerance=req.tolerance,
        relaxation_factor=req.relaxation_factor,
        progress_callback=progress_callback,
    )

    # Summary metrics
    summary = {}
    if len(result.signals_f) > 0:
        # Sum external transmitted signal powers: P_f(L) * (1 - R2) + P_b(0) * (1 - R1)
        sig_out = 0.0
        for j, s in enumerate(req.signals):
            sig_out += float(
                result.signals_f[j, -1] * (1.0 - s.reflectivity_output) +
                result.signals_b[j, 0] * (1.0 - s.reflectivity_input)
            )
        sig_in = float(sum(s.power_forward_w + s.power_backward_w for s in req.signals))
        pump_in = float(sum(p.power_forward_w + p.power_backward_w for p in req.pumps))
        summary["signal_output_w"] = sig_out
        summary["signal_input_w"] = sig_in
        if sig_in > 0:
            summary["gain_db"] = 10.0 * math.log10(sig_out / sig_in) if sig_out > 0 else float("-inf")
        if pump_in > 0:
            summary["efficiency"] = max(0.0, sig_out - sig_in) / pump_in
    if len(result.ase_f) > 0:
        summary["ase_output_w"] = float(
            result.ase_f[:, -1].sum() + result.ase_b[:, 0].sum()
        )

    return PowerASEResponse(
        z_m=result.z.tolist(),
        pump_wavelengths_nm=[w * 1e9 for w in result.pump_wavelengths],
        signal_wavelengths_nm=[w * 1e9 for w in result.signal_wavelengths],
        ase_wavelengths_nm=[w * 1e9 for w in result.ase_wavelengths],
        pumps_forward=encode_array(result.pumps_f),
        pumps_backward=encode_array(result.pumps_b),
        signals_forward=encode_array(result.signals_f),
        signals_backward=encode_array(result.signals_b),
        ase_forward=encode_array(result.ase_f),
        ase_backward=encode_array(result.ase_b),
        n2_fraction=encode_array(result.n2_fraction),
        summary=summary,
    )


# ---------- BPM (long-running) ----------

def _build_initial_field(grid_size: int, grid_width_m: float, cfg, wavelength_m: float, fiber) -> np.ndarray:
    xs = np.linspace(-grid_width_m, grid_width_m, grid_size)
    ys = np.linspace(-grid_width_m, grid_width_m, grid_size)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    
    if cfg.kind == "fundamental_mode":
        # Solve for the fundamental mode LP01 using radial FD solver
        fd_modes = solve_modes_fd(fiber, wavelength_m, l=0)
        if len(fd_modes) > 0:
            lp01 = fd_modes[0]
            # Offset center coordinates
            x0 = cfg.x_offset_um * 1e-6
            y0 = cfg.y_offset_um * 1e-6
            R = np.sqrt((X - x0) ** 2 + (Y - y0) ** 2)
            # Interpolate the radial profile
            radial = np.interp(R, lp01.r_grid, lp01.psi, left=0.0, right=0.0)
            field = radial.astype(complex)
        else:
            # Fallback to Gaussian
            waist = cfg.waist_um * 1e-6
            x0 = cfg.x_offset_um * 1e-6
            y0 = cfg.y_offset_um * 1e-6
            r2 = (X - x0) ** 2 + (Y - y0) ** 2
            field = np.exp(-r2 / waist ** 2).astype(complex)
    else:
        # Gaussian field
        waist = cfg.waist_um * 1e-6
        x0 = cfg.x_offset_um * 1e-6
        y0 = cfg.y_offset_um * 1e-6
        r2 = (X - x0) ** 2 + (Y - y0) ** 2
        field = np.exp(-r2 / waist ** 2).astype(complex)

    # Tilt: linear phase ramp exp(i * (kx*x + ky*y))
    kx = 2.0 * math.pi / wavelength_m * (cfg.tilt_x_mrad * 1e-3)
    ky = 2.0 * math.pi / wavelength_m * (cfg.tilt_y_mrad * 1e-3)
    field = field * np.exp(1j * (kx * X + ky * Y))
    
    # Normalize power to 1
    norm = np.sqrt(np.sum(np.abs(field) ** 2))
    if norm > 0:
        field = field / norm
    return field


def run_bpm(
    req: BPMRequest,
    progress_callback: Optional[Callable[[float], Optional[bool]]] = None,
) -> BPMResponse:
    fiber = build_fiber(req.fiber)
    wl_m = req.wavelength_nm * 1e-9
    length_m = req.length_mm * 1e-3
    grid_w = req.grid_width_factor * fiber.core_radius

    initial = _build_initial_field(req.grid_size, grid_w, req.initial_field, wl_m, fiber)

    result = solve_bpm(
        fiber=fiber,
        wavelength=wl_m,
        initial_field=initial,
        length=length_m,
        z_steps=req.z_steps,
        grid_width=grid_w,
        progress_callback=progress_callback,
    )

    # Downsample z-slices to keep payload small
    n_keep = min(req.save_z_slices, req.z_steps)
    idxs = np.linspace(0, req.z_steps - 1, n_keep).astype(int)
    intensity = (np.abs(result.fields[idxs]) ** 2).astype(np.float32)

    return BPMResponse(
        z_mm=(result.z * 1e3).tolist(),
        x_um=(result.x * 1e6).tolist(),
        y_um=(result.y * 1e6).tolist(),
        intensity_slices=encode_array(intensity),
        power_vs_z=result.powers.tolist(),
        z_step_indices=idxs.tolist(),
    )
