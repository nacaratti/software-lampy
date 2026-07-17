"""System simulation engine: walks the circuit graph mapping nodes to solvers.

Evaluation is a memoized recursion over the DAG: the signal on an edge is the
output of its source node, which recursively requests its own inputs. Laser
cavities (FBG pairs enclosing a gain fiber) are solved as a unit with
wavelength-dependent boundary reflectivities fed to `solve_ase`.

Units: SI internally (m, W); node parameters use the Device Library vocabulary
(µm/nm/ms/dB) and are converted on entry.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from fibersim.core.fiber import ActiveFiber, DoubleCladFiber, FiberGeometry, StepIndexFiber
from fibersim.core.ions import ActiveIon
from fibersim.solvers.power.ase import solve_ase
from fibersim.system.beam import BeamProfilerResult, analyze_beam
from fibersim.system.overlap import effective_mode_area, mode_dopant_overlap, pump_overlap
from fibersim.solvers.nonlinear_thresholds import sbs_threshold_power, srs_threshold_power
from fibersim.solvers.photodarkening import photodarkening_extra_loss_db, photodarkening_loss_db_m
from fibersim.system.tmi_threshold import estimate_tmi_risk
from fibersim.system.graph import (
    CavitySegment,
    GraphValidationError,
    INSTRUMENT_KINDS,
    SystemGraph,
    SystemNode,
)
from fibersim.system.instruments import (
    OsaTrace,
    PowerMeterReading,
    osa_trace,
    power_meter_reading,
)
from fibersim.system.signal import OpticalSignal, SpectralChannel

ProgressCallback = Callable[[float], Optional[bool]]

# ASE/laser band per ion (m)
ION_BANDS = {
    "yb": (1010e-9, 1110e-9),
    "er": (1500e-9, 1600e-9),
    "tm": (1850e-9, 2050e-9),
}
ION_FACTORIES = {
    "yb": ActiveIon.create_yb3,
    "er": ActiveIon.create_er3,
    "tm": ActiveIon.create_tm3,
}
DB_TO_LIN = math.log(10.0) / 10.0  # dB/m -> 1/m

# Conservative narrow-linewidth assumption for the SBS threshold estimate,
# since per-channel linewidth isn't tracked through the signal-propagation
# model yet — 1 MHz is representative of many single-frequency fiber laser
# seeds and gives the lower (more cautious) threshold bound.
_DEFAULT_SIGNAL_LINEWIDTH_HZ = 1.0e6
# Warn once a channel's power crosses this fraction of the estimated threshold.
_NONLINEAR_WARNING_FRACTION = 0.5

# Tm3+ cross-relaxation ("2-for-1") quantum yield for ~790 nm pumping: each
# absorbed pump photon's surplus energy (roughly twice the ~1900 nm laser
# photon energy) non-radiatively excites a second neighboring ground-state
# ion via ³H4+³H6 -> ³F4+³F4 energy transfer. Reported yields for
# well-designed Tm-silica span roughly 1.5-1.9; 1.6 is a representative
# middle value (see e.g. Jackson, "Cross relaxation and energy transfer
# upconversion processes relevant to the functioning of 2 um Tm-doped
# silica fibre lasers", Opt. Commun. 2004).
_TM_CROSS_RELAXATION_QUANTUM_YIELD = 1.6
# Pump wavelengths below this are treated as the 790 nm ground-state
# (³H6->³H4) pump band where cross-relaxation applies; longer-wavelength
# in-band (³F4) pumping excites the upper laser level directly (yield 1.0).
_TM_CROSS_RELAXATION_PUMP_CUTOFF_M = 900e-9


@dataclass
class SystemResult:
    """Everything produced by one system run, JSON-serializable via to_dict()."""
    edges: dict[str, dict] = field(default_factory=dict)       # edge_id -> spectrum dict
    nodes: dict[str, dict] = field(default_factory=dict)       # node_id -> solver outputs
    outputs: dict[str, dict] = field(default_factory=dict)     # output/instrument summaries
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "edges": self.edges,
            "nodes": self.nodes,
            "outputs": self.outputs,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# FBG reflection spectrum from Device Library parameters
# ---------------------------------------------------------------------------

def _fbg_reflectivity_fn(node: SystemNode) -> Callable[[np.ndarray], np.ndarray]:
    """Uniform-CMT reflection spectrum R(lambda) from (central wl, peak R, length).

    kappa is derived from the requested peak reflectivity: kappa*L = atanh(sqrt(R)),
    so the spectral shape is the physically consistent CMT response of a grating
    that actually reaches that peak.
    """
    lam_c = float(node.param("central_wavelength_nm", 1064.0)) * 1e-9
    r_peak = min(max(float(node.param("reflectivity", 0.99)), 0.0), 0.999999)
    length = float(node.param("length_mm", 10.0)) * 1e-3
    n_eff = float(node.param("n_eff", 1.45))

    kappa = math.atanh(math.sqrt(r_peak)) / length if r_peak > 0 else 0.0

    def reflectivity(wl: np.ndarray) -> np.ndarray:
        wl = np.asarray(wl, dtype=float)
        delta_beta = 2.0 * math.pi * n_eff * (1.0 / wl - 1.0 / lam_c)
        gamma_sq = kappa**2 - delta_beta**2
        r = np.zeros_like(wl)
        stop = gamma_sq > 0
        if np.any(stop):
            g = np.sqrt(gamma_sq[stop])
            th = np.tanh(g * length)
            r[stop] = (kappa**2 * th**2) / (g**2 + delta_beta[stop] ** 2 * th**2)
        passband = ~stop
        if np.any(passband) and kappa > 0:
            gp = np.sqrt(-gamma_sq[passband])
            s, c = np.sin(gp * length), np.cos(gp * length)
            den = gp**2 * c**2 + delta_beta[passband] ** 2 * s**2
            r[passband] = np.where(den > 0, (kappa**2) * s**2 / den, 0.0)
        return np.clip(r, 0.0, 1.0)

    return reflectivity


# ---------------------------------------------------------------------------
# Active fiber construction & solving
# ---------------------------------------------------------------------------

# Typical low-index fluoropolymer outer-cladding index for double-clad
# fibers; the schema doesn't expose this separately since it barely affects
# anything we compute (Γ_pump uses only the core/inner-cladding area ratio).
_OUTER_CLADDING_INDEX_DEFAULT = 1.375


def _build_active_fiber(node: SystemNode) -> tuple[ActiveFiber, str]:
    ion_kind = str(node.param("ion", "yb")).lower()
    if ion_kind not in ION_FACTORIES:
        raise GraphValidationError([f"'{node.label or node.id}': unknown ion '{ion_kind}'."])
    core_r = float(node.param("core_radius_um", 2.5)) * 1e-6
    clad_r = float(node.param("clad_radius_um", 62.5)) * 1e-6
    n_core = float(node.param("n_core", 1.46))
    n_clad = float(node.param("n_clad", 1.454))
    n_total = float(node.param("N_total", 3e25))
    inner_clad_um = node.param("inner_cladding_radius_um", None)

    if inner_clad_um is not None:
        # Double-clad / cladding-pumped: clad_radius_um is the OUTER cladding.
        geometry: FiberGeometry = DoubleCladFiber(
            core_r, float(inner_clad_um) * 1e-6, clad_r,
            n_core, n_clad, _OUTER_CLADDING_INDEX_DEFAULT,
        )
    else:
        geometry = StepIndexFiber(core_r, clad_r, n_core, n_clad)

    fiber = ActiveFiber(geometry, ION_FACTORIES[ion_kind](), n_total)
    fiber.ion.lifetime = float(node.param("tau_ms", 0.84)) * 1e-3
    return fiber, ion_kind


def _fiber_geometry_from_params(kind: str, params: dict) -> FiberGeometry:
    """Builds a bare StepIndexFiber geometry from Device-Library-style params.

    Used by the beam profiler, which only needs the waveguide (not the gain
    medium) to solve the guided modes at the facet.
    """
    core_r = float(params.get("core_radius_um", 2.5)) * 1e-6
    clad_r = float(params.get("clad_radius_um", 62.5)) * 1e-6
    n_core = float(params.get("n_core", 1.46))
    n_clad = float(params.get("n_clad", 1.454))
    return StepIndexFiber(core_r, clad_r, n_core, n_clad)


def _dominant_wavelength(signal: OpticalSignal) -> float:
    """Picks the wavelength the beam profiler should analyze: the strongest
    signal line if any, else the strongest pump line, else any channel."""
    for kind_channels in (signal.signals(), signal.pumps(), signal.channels):
        if kind_channels:
            return max(kind_channels, key=lambda ch: ch.power).wavelength
    raise ValueError("no optical power reaches this point — nothing to profile")


def _osa_trace_to_dict(trace: OsaTrace) -> dict:
    return {
        "wavelengths_nm": trace.wavelengths_nm.tolist(),
        "power_dbm": trace.power_dbm.tolist(),
        "rbw_nm": trace.rbw_nm,
        "peak_wavelength_nm": trace.peak_wavelength_nm,
        "peak_power_dbm": trace.peak_power_dbm,
        "osnr_db": trace.osnr_db,
        "total_power_w": trace.total_power_w,
    }


def _beam_result_to_dict(result: BeamProfilerResult) -> dict:
    return {
        "z_m": result.z_m,
        "x_m": result.x_m,
        "y_m": result.y_m,
        "images": result.images,
        "wx_m": result.wx_m,
        "wy_m": result.wy_m,
        "w0x_m": result.w0x_m,
        "w0y_m": result.w0y_m,
        "z0x_m": result.z0x_m,
        "z0y_m": result.z0y_m,
        "m2x": result.m2x,
        "m2y": result.m2y,
        "divergence_x_mrad": result.divergence_x_mrad,
        "divergence_y_mrad": result.divergence_y_mrad,
        "bpp_mm_mrad": result.bpp_mm_mrad,
        "wavelength_m": result.wavelength_m,
        "v_number": result.v_number,
        "is_single_mode": result.is_single_mode,
        "waist_index": result.waist_index,
    }


def _auto_num_z(fiber: ActiveFiber, node: SystemNode, length: float) -> int:
    """Grid sizing from the stiffest absorption/gain coefficient.

    The relaxation scheme in solve_ase is first-order per step; keeping
    max|g|*dz <= ~0.2 avoids the energy-conservation drift observed on
    under-resolved grids (see tests/test_ase.py note). Γ is now computed
    per-channel from the real mode overlap (always <= 1), so using Γ=1 here
    is a conservative upper bound on the required resolution — it can only
    over-resolve, never under-resolve, without needing to solve modes first.
    """
    sig_peak = float(np.max(fiber.ion.sigma_abs + fiber.ion.sigma_em))
    g_peak = sig_peak * fiber.N_max
    n = int(length * g_peak / 0.2) + 50
    return int(min(max(n, 150), 1500))


def _bin_ase_onto_grid(ase_channels: list[SpectralChannel], grid: np.ndarray) -> np.ndarray:
    """Re-bins incoming ASE bins onto this stage's ASE wavelength grid."""
    powers = np.zeros(len(grid))
    if not ase_channels or len(grid) == 0:
        return powers
    if len(grid) == 1:
        powers[0] = sum(ch.power for ch in ase_channels)
        return powers
    edges = np.concatenate((
        [grid[0] - (grid[1] - grid[0]) / 2],
        (grid[:-1] + grid[1:]) / 2,
        [grid[-1] + (grid[-1] - grid[-2]) / 2],
    ))
    for ch in ase_channels:
        idx = int(np.clip(np.searchsorted(edges, ch.wavelength) - 1, 0, len(grid) - 1))
        powers[idx] += ch.power
    return powers


def _check_nonlinear_thresholds(
    fiber: ActiveFiber, label: str, length: float, bg_loss: float,
    signal_wavelengths: list[float], signals_f: np.ndarray, warnings: list[str],
) -> dict:
    """Estimates SRS/SBS thresholds at the strongest signal line and warns if
    the actual power comes within `_NONLINEAR_WARNING_FRACTION` of them. Not a
    channel-coupled propagation model (see nonlinear_thresholds.py docstring)
    — a fast design-time check of how close this fiber is to those limits.
    """
    result: dict = {}
    if len(signal_wavelengths) == 0 or signals_f.size == 0:
        return result

    peak_per_channel = np.max(signals_f, axis=1)
    idx = int(np.argmax(peak_per_channel))
    wl = signal_wavelengths[idx]
    p_max = float(peak_per_channel[idx])
    if p_max <= 0:
        return result

    a_eff = effective_mode_area(fiber, wl)
    if a_eff is None:
        return result

    p_srs = srs_threshold_power(wl, a_eff, length, bg_loss)
    p_sbs = sbs_threshold_power(a_eff, length, bg_loss, signal_linewidth_hz=_DEFAULT_SIGNAL_LINEWIDTH_HZ)
    result = {
        "effective_area_um2": a_eff * 1e12,
        "srs_threshold_w": p_srs,
        "sbs_threshold_w": p_sbs,
        "peak_signal_power_w": p_max,
    }
    if p_max > _NONLINEAR_WARNING_FRACTION * p_srs:
        warnings.append(
            f"'{label}': signal power ({p_max:.2f} W) is within "
            f"{_NONLINEAR_WARNING_FRACTION:.0%} of the estimated SRS threshold "
            f"({p_srs:.2f} W) — expect measurable Raman conversion at this power-length product."
        )
    if p_max > _NONLINEAR_WARNING_FRACTION * p_sbs:
        warnings.append(
            f"'{label}': signal power ({p_max:.2f} W) is within "
            f"{_NONLINEAR_WARNING_FRACTION:.0%} of the estimated SBS threshold "
            f"({p_sbs:.2f} W, assuming a {_DEFAULT_SIGNAL_LINEWIDTH_HZ / 1e6:.0f} MHz linewidth) — "
            f"narrow-linewidth signals typically hit SBS well before SRS."
        )
    return result


_PHOTODARKENING_WARNING_DB = 1.0


def _check_photodarkening(label: str, z: np.ndarray, n2_fraction: np.ndarray, warnings: list[str]) -> dict:
    """Estimated Yb photodarkening-induced loss at full time-saturation (see
    solvers/photodarkening.py) — a design-time diagnostic, not a real-time
    kinetic model. Warns when the saturated extra loss would be significant.
    """
    loss_db_m = photodarkening_loss_db_m(n2_fraction)
    extra_loss_db = photodarkening_extra_loss_db(z, n2_fraction)
    result = {
        "photodarkening_peak_db_m": float(np.max(loss_db_m)),
        "photodarkening_extra_loss_db_saturated": extra_loss_db,
    }
    if extra_loss_db > _PHOTODARKENING_WARNING_DB:
        warnings.append(
            f"'{label}': at full photodarkening saturation, estimated extra "
            f"signal loss is {extra_loss_db:.2f} dB over the fiber length — "
            f"consider a photodarkening-resistant (Ce-codoped) fiber for "
            f"long-duration high-inversion operation."
        )
    return result


_TMI_SILICA_K_CORE_W_M_K = 1.38  # matches solvers/thermal/cavity.py's default core conductivity
_TMI_ROOM_TEMP_K = 294.15
_TMI_WARNING_FRACTION = 0.5


def _check_tmi_risk(
    fiber: ActiveFiber, label: str, z: np.ndarray,
    pump_forward_w: np.ndarray, pump_backward_w: np.ndarray,
    pump_wavelengths: list[float], signal_wavelengths: list[float],
    warnings: list[str],
) -> dict:
    """Rough TMI risk estimate for high-power Yb fiber amplifiers/lasers (see
    system/tmi_threshold.py for the underlying model and its limits). Builds
    a peak on-axis core temperature rise from a simple uniform-heat-
    generation conduction estimate — not the full 3-layer thermal solver,
    which isn't wired into this engine (solvers/thermal/cavity.py runs as
    its own standalone page) — then compares the resulting thermal index
    perturbation to the fiber's intrinsic LP01-LP11 effective-index gap.
    Returns {} for fibers that don't guide a distinct LP11 (deeply
    single-mode fibers aren't TMI-prone in the usual sense).
    """
    if not pump_wavelengths or not signal_wavelengths:
        return {}
    pump_total = np.asarray(pump_forward_w) + np.asarray(pump_backward_w)
    absorbed_density = np.clip(-np.gradient(pump_total, z), 0.0, None)
    peak_absorbed = float(np.max(absorbed_density))
    if peak_absorbed <= 0.0:
        return {}

    eta_heat = 1.0 - min(pump_wavelengths) / max(signal_wavelengths)
    a_core = fiber.geometry.core_radius
    q_peak = eta_heat * peak_absorbed / (math.pi * a_core ** 2)
    delta_t_peak = q_peak * a_core ** 2 / (4.0 * _TMI_SILICA_K_CORE_W_M_K)
    t_core_peak = _TMI_ROOM_TEMP_K + delta_t_peak

    def _t_of_r(r: np.ndarray) -> np.ndarray:
        r = np.asarray(r, dtype=float)
        return np.where(np.abs(r) <= a_core, t_core_peak, _TMI_ROOM_TEMP_K)

    result = estimate_tmi_risk(fiber.geometry, signal_wavelengths[0], _t_of_r)
    if result is None:
        return {}
    if result["tmi_risk_fraction"] > _TMI_WARNING_FRACTION:
        warnings.append(
            f"'{label}': estimated TMI risk fraction is {result['tmi_risk_fraction']:.2f} "
            f"(thermal index perturbation approaching the LP01-LP11 gap) — this design has "
            f"the qualitative ingredients for transverse mode instability at high power."
        )
    return {
        "tmi_risk_fraction": result["tmi_risk_fraction"],
        "tmi_core_temperature_k": t_core_peak,
    }


@dataclass
class _ActiveSolveSpec:
    """Inputs for one solve_ase call on a gain fiber."""
    node: SystemNode
    input_signal: OpticalSignal
    backward_pumps: list[SpectralChannel]
    r1_signal: float = 0.0
    r2_signal: float = 0.0
    r1_ase: np.ndarray | float = 0.0
    r2_ase: np.ndarray | float = 0.0
    laser_line: float | None = None  # cavity signal wavelength (m)
    num_ase_channels: int = 40


def _solve_active(spec: _ActiveSolveSpec, warnings: list[str],
                  progress: Optional[ProgressCallback]) -> tuple[OpticalSignal, dict]:
    node = spec.node
    label = node.label or node.id
    fiber, ion_kind = _build_active_fiber(node)
    length = float(node.param("length_m", 0.0))
    if length <= 0.0:
        length = 2.0
        warnings.append(f"'{label}': no length_m set; using 2.0 m.")

    bg_loss = float(node.param("background_loss_db_m", 0.005)) * DB_TO_LIN
    manual_gamma_pump = node.param("gamma_pump", None)
    manual_gamma_signal = node.param("gamma_signal", None)

    # Γ is computed once per unique wavelength from the real mode/dopant
    # overlap (or the cladding-pump area ratio for double-clad fibers) —
    # memoized since solving modes is the expensive part of this function.
    overlap_cache: dict[tuple[float, bool], float] = {}

    def _overlap(wl: float, manual: Optional[float], *, is_pump: bool) -> float:
        if manual is not None:
            return float(manual)
        key = (round(wl, 15), is_pump)
        if key not in overlap_cache:
            overlap_cache[key] = pump_overlap(fiber, wl) if is_pump else mode_dopant_overlap(fiber, wl)
        gamma = overlap_cache[key]
        if gamma < 1e-6:
            warnings.append(
                f"'{label}': computed Γ≈0 at {wl * 1e9:.1f} nm — this wavelength doesn't "
                f"couple to the guided mode (check geometry/indices)."
            )
        return gamma

    wl_min, wl_max = ION_BANDS[ion_kind]
    n_ase = spec.num_ase_channels
    ase_grid = np.linspace(wl_min, wl_max, n_ase)

    def _pump_quantum_yield(wl: float) -> float:
        if ion_kind == "tm" and wl < _TM_CROSS_RELAXATION_PUMP_CUTOFF_M:
            return _TM_CROSS_RELAXATION_QUANTUM_YIELD
        return 1.0

    pumps = []
    for ch in spec.input_signal.pumps():
        pumps.append({"wavelength": ch.wavelength, "power_in_f": ch.power,
                      "loss": bg_loss, "overlap": _overlap(ch.wavelength, manual_gamma_pump, is_pump=True),
                      "quantum_yield": _pump_quantum_yield(ch.wavelength)})
    for ch in spec.backward_pumps:
        pumps.append({"wavelength": ch.wavelength, "power_in_b": ch.power,
                      "loss": bg_loss, "overlap": _overlap(ch.wavelength, manual_gamma_pump, is_pump=True),
                      "quantum_yield": _pump_quantum_yield(ch.wavelength)})
    if not pumps:
        warnings.append(f"'{label}': no pump reaches this gain fiber.")

    signals = []
    for ch in spec.input_signal.signals():
        signals.append({
            "wavelength": ch.wavelength, "power_in_f": ch.power,
            "loss": bg_loss, "overlap": _overlap(ch.wavelength, manual_gamma_signal, is_pump=False),
            "R1": spec.r1_signal, "R2": spec.r2_signal,
        })
    if spec.laser_line is not None and not any(
        abs(s["wavelength"] - spec.laser_line) < 0.5e-9 for s in signals
    ):
        # tiny seed starts the intracavity field on the grating line
        signals.append({
            "wavelength": spec.laser_line, "power_in_f": 1e-6,
            "loss": bg_loss, "overlap": _overlap(spec.laser_line, manual_gamma_signal, is_pump=False),
            "R1": spec.r1_signal, "R2": spec.r2_signal,
        })

    incoming_ase = _bin_ase_onto_grid(spec.input_signal.ase(), ase_grid)
    # ASE spans a band around the gain peak; a single representative Γ at the
    # band center is the same approximation the old manual scalar made.
    gamma_ase = _overlap(0.5 * (wl_min + wl_max), manual_gamma_signal, is_pump=False)

    num_z = _auto_num_z(fiber, node, length)
    res = solve_ase(
        active_fiber=fiber,
        length=length,
        pumps=pumps,
        signals=signals,
        ase_config={
            "wl_min": wl_min, "wl_max": wl_max, "num_channels": n_ase,
            "loss": bg_loss, "overlap": gamma_ase,
            "R1": spec.r1_ase, "R2": spec.r2_ase,
            "power_in_f": incoming_ase,
        },
        num_z_points=num_z,
        max_iterations=300,
        tolerance=1e-5,
        progress_callback=progress,
    )

    # Forward output at z = L (before any boundary reflector — cavities apply T2 outside)
    out_channels: list[SpectralChannel] = []
    for idx, wl in enumerate(res.pump_wavelengths):
        out_channels.append(SpectralChannel(wl, float(res.pumps_f[idx, -1]), "pump"))
    for idx, wl in enumerate(res.signal_wavelengths):
        out_channels.append(SpectralChannel(wl, float(res.signals_f[idx, -1]), "signal"))
    dwl = (wl_max - wl_min) / (n_ase - 1) if n_ase > 1 else 10e-9
    for idx, wl in enumerate(res.ase_wavelengths):
        out_channels.append(SpectralChannel(wl, float(res.ase_f[idx, -1]), "ase", width=dwl))

    signal_out = OpticalSignal.from_channels(out_channels).dropped_below()

    pump_in_total = sum(p.get("power_in_f", 0.0) + p.get("power_in_b", 0.0) for p in pumps)
    signal_in_total = sum(s["power_in_f"] for s in signals)
    signal_out_total = float(np.sum(res.signals_f[:, -1])) if len(signals) else 0.0
    nonlinear_info = _check_nonlinear_thresholds(
        fiber, label, length, bg_loss, res.signal_wavelengths, res.signals_f, warnings,
    )
    photodarkening_info = (
        _check_photodarkening(label, res.z, res.n2_fraction, warnings) if ion_kind == "yb" else {}
    )
    esa_upconversion_info: dict = {}
    if ion_kind == "tm" and any(p["quantum_yield"] > 1.0 for p in pumps):
        esa_upconversion_info["tm_cross_relaxation_yield"] = _TM_CROSS_RELAXATION_QUANTUM_YIELD
    if ion_kind == "er" and fiber.ion.upconversion_coeff_m3_s > 0.0:
        esa_upconversion_info["er_upconversion_coeff_m3_s"] = fiber.ion.upconversion_coeff_m3_s
    tmi_info = (
        _check_tmi_risk(
            fiber, label, res.z, np.sum(res.pumps_f, axis=0), np.sum(res.pumps_b, axis=0),
            res.pump_wavelengths, res.signal_wavelengths, warnings,
        ) if ion_kind == "yb" else {}
    )
    node_result = {
        "kind": "fiber_active",
        "ion": ion_kind,
        "length_m": length,
        "num_z_points": num_z,
        "z_m": res.z.tolist(),
        "pump_forward_w": np.sum(res.pumps_f, axis=0).tolist(),
        "pump_backward_w": np.sum(res.pumps_b, axis=0).tolist(),
        "signal_forward_w": np.sum(res.signals_f, axis=0).tolist() if len(signals) else [],
        "signal_backward_w": np.sum(res.signals_b, axis=0).tolist() if len(signals) else [],
        "ase_forward_w": np.sum(res.ase_f, axis=0).tolist(),
        "ase_backward_w": np.sum(res.ase_b, axis=0).tolist(),
        "n2_fraction": res.n2_fraction.tolist(),
        "pump_in_w": pump_in_total,
        "signal_in_w": signal_in_total,
        "signal_out_w": signal_out_total,
        "gain_db": (10.0 * math.log10(signal_out_total / signal_in_total)
                    if signal_in_total > 0 and signal_out_total > 0 else None),
        "backward_ase_out_w": float(np.sum(res.ase_b[:, 0])),
        **nonlinear_info,
        **photodarkening_info,
        **esa_upconversion_info,
        **tmi_info,
    }
    return signal_out, node_result


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class _Evaluator:
    def __init__(self, graph: SystemGraph, progress: Optional[ProgressCallback]):
        self.g = graph
        self.progress = progress
        self.warnings: list[str] = []
        self.edge_signals: dict[str, OpticalSignal] = {}
        self.node_outputs: dict[str, OpticalSignal] = {}
        self.node_results: dict[str, dict] = {}
        self.outputs: dict[str, dict] = {}

        self.cavities = graph.detect_cavities()
        self.cavity_member: dict[str, CavitySegment] = {}
        for cav in self.cavities:
            for n in [cav.left_fbg, cav.right_fbg, *cav.inner_nodes]:
                self.cavity_member[n.id] = cav

        # Pre-resolved counter-propagating pumps: active fiber id -> pump channels
        self.backward_pumps: dict[str, list[SpectralChannel]] = {}
        self.consumed_pump_wdm: set[str] = set()
        self._route_wdm_pumps()

        self._active_total = max(len(graph.nodes_of_kind("fiber_active")), 1)
        self._active_done = 0

    # -- pump routing -------------------------------------------------------
    def _pump_branch_signal(self, node_id: str) -> Optional[OpticalSignal]:
        """Evaluates a pure pump branch (pump_source -> passive/splice chain)."""
        node = self.g.node(node_id)
        if node.kind == "pump_source":
            wl = float(node.param("wavelength_nm", 976.0)) * 1e-9
            power = float(node.param("power_w", 0.5))
            return OpticalSignal.line(wl, power, "pump")
        if node.kind in {"fiber_passive", "splice"}:
            ins = [e for e in self.g.in_edges(node_id) if e.target_port != "pump"]
            if len(ins) != 1:
                return None
            upstream = self._pump_branch_signal(ins[0].source)
            if upstream is None:
                return None
            return self._apply_passive(node, upstream)
        return None

    def _nearest_active(self, node_id: str, direction: str) -> Optional[str]:
        """Nearest fiber_active on the main chain, walking up or down."""
        steps = 0
        current = node_id
        while steps < len(self.g.nodes):
            steps += 1
            if direction == "down":
                nxt = self.g.main_chain_successor(current)
                if nxt is None:
                    return None
                if nxt.kind == "fiber_active":
                    return nxt.id
                current = nxt.id
            else:
                ins = [e for e in self.g.in_edges(current) if e.target_port != "pump"]
                if not ins:
                    return None
                prev = self.g.node(ins[0].source)
                if prev.kind == "fiber_active":
                    return prev.id
                current = prev.id
        return None

    def _route_wdm_pumps(self) -> None:
        """Decides, per WDM pump port, whether the pump co- or counter-propagates.

        Convention: the pump travels toward the nearest gain fiber on the main
        chain. A WDM placed after the fiber therefore counter-pumps it.
        """
        for wdm in self.g.nodes_of_kind("coupler_wdm"):
            pump_edges = [e for e in self.g.in_edges(wdm.id) if e.target_port == "pump"]
            if not pump_edges:
                continue
            down = self._nearest_active(wdm.id, "down")
            up = self._nearest_active(wdm.id, "up")
            if down is None and up is None:
                self.warnings.append(
                    f"'{wdm.label or wdm.id}': pump injected but no gain fiber on the chain."
                )
                continue
            direction = "forward" if down is not None else "backward"
            if direction == "backward":
                loss_db = float(wdm.param("insertion_loss_port2_db", 0.4))
                for e in pump_edges:
                    branch = self._pump_branch_signal(e.source)
                    if branch is None:
                        self.warnings.append(
                            f"'{wdm.label or wdm.id}': counter-propagating pump must come "
                            "from a dedicated pump branch; treating as forward."
                        )
                        continue
                    self.edge_signals.setdefault(e.id, branch.attenuated_db(e.loss_db))
                    branch = branch.attenuated_db(loss_db + e.loss_db)
                    self.backward_pumps.setdefault(up, []).extend(branch.pumps())
                    self.consumed_pump_wdm.add(e.id)

    # -- passive elements ---------------------------------------------------
    def _apply_passive(self, node: SystemNode, sig: OpticalSignal) -> OpticalSignal:
        if node.kind == "fiber_passive":
            length_m = float(node.param("length_m", 1.0))
            att_db = float(node.param("attenuation_db_km", 0.35)) * length_m / 1000.0
            return sig.attenuated_db(att_db)
        if node.kind == "splice":
            return sig.attenuated_db(float(node.param("loss_db", 0.05)))
        return sig

    # -- memoized evaluation --------------------------------------------------
    def edge_signal(self, edge) -> OpticalSignal:
        if edge.id in self.edge_signals:
            return self.edge_signals[edge.id]
        sig = self.node_output(edge.source)
        if edge.loss_db:
            sig = sig.attenuated_db(edge.loss_db)
        self.edge_signals[edge.id] = sig
        return sig

    def _main_input(self, node_id: str) -> OpticalSignal:
        ins = [e for e in self.g.in_edges(node_id) if e.target_port != "pump"]
        if not ins:
            return OpticalSignal.empty()
        return self.edge_signal(ins[0])

    def node_output(self, node_id: str) -> OpticalSignal:
        if node_id in self.node_outputs:
            return self.node_outputs[node_id]

        node = self.g.node(node_id)
        cav = self.cavity_member.get(node_id)
        if cav is not None:
            self._solve_cavity(cav)
            return self.node_outputs[node_id]

        out = self._solve_plain(node)
        self.node_outputs[node_id] = out
        return out

    def _progress_for_active(self) -> Optional[ProgressCallback]:
        if self.progress is None:
            return None
        done = self._active_done
        total = self._active_total

        def cb(v: float) -> Optional[bool]:
            return self.progress((done + min(max(v, 0.0), 1.0)) / total)

        return cb

    def _solve_plain(self, node: SystemNode) -> OpticalSignal:
        kind = node.kind
        if kind == "pump_source":
            wl = float(node.param("wavelength_nm", 976.0)) * 1e-9
            return OpticalSignal.line(wl, float(node.param("power_w", 0.5)), "pump")
        if kind == "seed":
            wl = float(node.param("wavelength_nm", 1064.0)) * 1e-9
            return OpticalSignal.line(wl, float(node.param("power_w", 0.01)), "signal")
        if kind in {"fiber_passive", "splice"}:
            return self._apply_passive(node, self._main_input(node.id))
        if kind == "power_combiner":
            ins = [e for e in self.g.in_edges(node.id) if e.target_port != "pump"]
            combined = OpticalSignal.empty()
            for e in ins:
                combined = combined.merged(self.edge_signal(e))
            loss_db = float(node.param("insertion_loss_db", 0.5))
            combined = combined.attenuated_db(loss_db)
            self.node_results[node.id] = {
                "kind": "power_combiner",
                "num_inputs": len(ins),
                "combined_power_w": combined.total_power(),
            }
            return combined
        if kind == "coupler_wdm":
            main = self._main_input(node.id).attenuated_db(
                float(node.param("insertion_loss_port1_db", 0.3))
            )
            merged = main
            for e in self.g.in_edges(node.id):
                if e.target_port == "pump" and e.id not in self.consumed_pump_wdm:
                    pump_sig = self.edge_signal(e).attenuated_db(
                        float(node.param("insertion_loss_port2_db", 0.4))
                    )
                    merged = merged.merged(pump_sig)
            return merged
        if kind == "fbg":
            # standalone grating: transmission filter
            refl = _fbg_reflectivity_fn(node)
            sig_in = self._main_input(node.id)
            sig_out = sig_in.filtered(lambda wl: 1.0 - float(refl(np.array([wl]))[0]))
            self.node_results[node.id] = {
                "kind": "fbg",
                "role": "filter",
                "reflected_power_w": sig_in.total_power() - sig_out.total_power(),
            }
            return sig_out
        if kind == "fiber_active":
            spec = _ActiveSolveSpec(
                node=node,
                input_signal=self._main_input(node.id),
                backward_pumps=self.backward_pumps.get(node.id, []),
            )
            out, result = _solve_active(spec, self.warnings, self._progress_for_active())
            self._active_done += 1
            self.node_results[node.id] = result
            return out
        # Sinks pass nothing forward
        return OpticalSignal.empty()

    # -- cavity ---------------------------------------------------------------
    def _solve_cavity(self, cav: CavitySegment) -> None:
        left, right = cav.left_fbg, cav.right_fbg
        actives = [n for n in cav.inner_nodes if n.kind == "fiber_active"]
        gain = actives[0]
        if len(actives) > 1:
            self.warnings.append(
                "Cavity contains multiple gain fibers; only the first is solved as gain, "
                "the others are ignored (not yet supported)."
            )

        refl_left = _fbg_reflectivity_fn(left)
        refl_right = _fbg_reflectivity_fn(right)

        lam_left = float(left.param("central_wavelength_nm", 1064.0)) * 1e-9
        lam_right = float(right.param("central_wavelength_nm", 1064.0)) * 1e-9
        bw = min(float(left.param("bandwidth_nm", 0.3)), float(right.param("bandwidth_nm", 0.3))) * 1e-9
        if abs(lam_left - lam_right) > bw:
            self.warnings.append(
                f"Cavity FBGs are detuned ({lam_left*1e9:.2f} vs {lam_right*1e9:.2f} nm) "
                "by more than their bandwidth — laser may not build up."
            )
        # Reference the higher-R grating for the laser line
        r_l = float(left.param("reflectivity", 0.99))
        r_r = float(right.param("reflectivity", 0.99))
        laser_line = lam_left if r_l >= r_r else lam_right

        # Intracavity passive losses lumped onto the boundaries
        idx_gain = cav.inner_nodes.index(gain)
        loss_before_db = sum(self._passive_loss_db(n) for n in cav.inner_nodes[:idx_gain])
        loss_after_db = sum(self._passive_loss_db(n) for n in cav.inner_nodes[idx_gain + 1:])
        t_before = 10.0 ** (-loss_before_db / 10.0)
        t_after = 10.0 ** (-loss_after_db / 10.0)
        if loss_before_db + loss_after_db > 0:
            self.warnings.append(
                f"Intracavity passive losses lumped at the boundaries "
                f"({loss_before_db + loss_after_db:.2f} dB round-trip contribution)."
            )

        # Forward pumps: injected by inner WDMs routed toward the gain fiber, plus
        # anything arriving through the left grating (out-of-band transmission).
        forward_pumps: list[SpectralChannel] = []
        for pos, inner in enumerate(cav.inner_nodes):
            if inner.kind != "coupler_wdm":
                continue
            for e in self.g.in_edges(inner.id):
                if e.target_port == "pump" and e.id not in self.consumed_pump_wdm:
                    pump_sig = self.edge_signal(e).attenuated_db(
                        float(inner.param("insertion_loss_port2_db", 0.4))
                    )
                    if pos <= idx_gain:
                        forward_pumps.extend(pump_sig.pumps())
                    else:
                        self.backward_pumps.setdefault(gain.id, []).extend(pump_sig.pumps())

        seed_in = self._main_input(left.id)
        seed_through = seed_in.filtered(lambda wl: 1.0 - float(refl_left(np.array([wl]))[0]))
        seed_through = seed_through.attenuated_db(loss_before_db)
        forward_pumps.extend(seed_through.pumps())

        # ASE-band reflectivity arrays for the gain fiber's grid
        fiber_tmp, ion_kind = _build_active_fiber(gain)
        wl_min, wl_max = ION_BANDS[ion_kind]
        n_ase = 40
        ase_grid = np.linspace(wl_min, wl_max, n_ase)
        r1_arr = refl_left(ase_grid) * t_before**2
        r2_arr = refl_right(ase_grid) * t_after**2

        input_signal = OpticalSignal.from_channels(
            forward_pumps + seed_through.signals() + seed_through.ase()
        )
        r1_line = float(refl_left(np.array([laser_line]))[0]) * t_before**2
        r2_line = float(refl_right(np.array([laser_line]))[0]) * t_after**2

        spec = _ActiveSolveSpec(
            node=gain,
            input_signal=input_signal,
            backward_pumps=self.backward_pumps.get(gain.id, []),
            r1_signal=r1_line,
            r2_signal=r2_line,
            r1_ase=r1_arr,
            r2_ase=r2_arr,
            laser_line=laser_line,
            num_ase_channels=n_ase,
        )
        fiber_out, result = _solve_active(spec, self.warnings, self._progress_for_active())
        self._active_done += 1
        result["role"] = "cavity_gain"
        result["laser_wavelength_nm"] = laser_line * 1e9
        result["r1_at_laser"] = r1_line
        result["r2_at_laser"] = r2_line
        self.node_results[gain.id] = result

        # Output through the right grating: T2(lambda) applied to the forward field.
        after_loss = fiber_out.attenuated_db(loss_after_db)
        out = after_loss.filtered(lambda wl: 1.0 - float(refl_right(np.array([wl]))[0]))
        laser_out = out.power_in_band(laser_line - 2e-9, laser_line + 2e-9)

        self.node_results[left.id] = {"kind": "fbg", "role": "cavity_hr" if r_l >= r_r else "cavity_oc"}
        self.node_results[right.id] = {
            "kind": "fbg",
            "role": "cavity_oc" if r_l >= r_r else "cavity_hr",
            "laser_output_w": laser_out,
        }

        # Register outputs for every cavity member so downstream taps resolve.
        intracavity = fiber_out
        for n in [left, *cav.inner_nodes]:
            self.node_outputs[n.id] = intracavity
        self.node_outputs[right.id] = out

    def _passive_loss_db(self, node: SystemNode) -> float:
        if node.kind == "fiber_passive":
            return float(node.param("attenuation_db_km", 0.35)) * float(node.param("length_m", 1.0)) / 1000.0
        if node.kind == "splice":
            return float(node.param("loss_db", 0.05))
        if node.kind == "coupler_wdm":
            return float(node.param("insertion_loss_port1_db", 0.3))
        if node.kind == "power_combiner":
            return float(node.param("insertion_loss_db", 0.5))
        return 0.0

    # -- sinks ------------------------------------------------------------------
    def evaluate_sinks(self) -> None:
        sinks = self.g.nodes_of_kind(*INSTRUMENT_KINDS)
        for sink in sinks:
            ins = self.g.in_edges(sink.id)
            if not ins:
                continue
            sig = self.edge_signal(ins[0])
            upstream_fiber = self._nearest_fiber_node(ins[0].source)
            summary = {
                "kind": sink.kind,
                "signal": sig.to_dict(),
                "total_power_w": sig.total_power(),
                "signal_power_w": sig.power_of_kind("signal"),
                "pump_power_w": sig.power_of_kind("pump"),
                "ase_power_w": sig.power_of_kind("ase"),
                "source_fiber": (
                    {"node_id": upstream_fiber.id, "kind": upstream_fiber.kind, "params": dict(upstream_fiber.params)}
                    if upstream_fiber is not None else None
                ),
            }

            if sink.kind == "osa":
                trace = osa_trace(
                    sig,
                    rbw_nm=float(sink.param("rbw_nm", 0.1)),
                    span_nm=sink.params.get("span_nm"),
                    center_nm=sink.params.get("center_nm"),
                )
                summary["osa"] = _osa_trace_to_dict(trace)
            elif sink.kind == "power_meter":
                reading = power_meter_reading(sig)
                summary["power_meter"] = {
                    "total_power_w": reading.total_power_w,
                    "total_power_dbm": reading.total_power_dbm,
                    "band_power_w": reading.band_power_w,
                    "band_power_dbm": reading.band_power_dbm,
                }
            elif sink.kind == "beam_profiler":
                if upstream_fiber is None:
                    self.warnings.append(
                        f"'{sink.label or sink.id}': no upstream fiber found — cannot profile the beam."
                    )
                else:
                    try:
                        geometry = _fiber_geometry_from_params(upstream_fiber.kind, upstream_fiber.params)
                        wl = _dominant_wavelength(sig)
                        result = analyze_beam(
                            geometry,
                            wl,
                            grid_n=int(sink.param("grid_n", 128)),
                            num_z=int(sink.param("num_z", 21)),
                            z_span_factor=float(sink.param("z_span_factor", 12.0)),
                        )
                        summary["beam"] = _beam_result_to_dict(result)
                        upstream_result = self.node_results.get(upstream_fiber.id, {})
                        if "tmi_risk_fraction" in upstream_result:
                            summary["beam"]["tmi_risk_fraction"] = upstream_result["tmi_risk_fraction"]
                    except ValueError as exc:
                        self.warnings.append(f"'{sink.label or sink.id}': {exc}")

            self.outputs[sink.id] = summary
            self.node_results[sink.id] = summary

    def _nearest_fiber_node(self, node_id: str) -> Optional[SystemNode]:
        """Walks upstream to find the fiber the light exits from (beam profiler input)."""
        current: Optional[str] = node_id
        for _ in range(len(self.g.nodes)):
            node = self.g.node(current)
            if node.kind in {"fiber_active", "fiber_passive"}:
                return node
            ins = [e for e in self.g.in_edges(current) if e.target_port != "pump"]
            if not ins:
                return None
            current = ins[0].source
        return None


def simulate_system(graph: SystemGraph,
                    progress_callback: Optional[ProgressCallback] = None) -> SystemResult:
    """Runs the full system simulation. Raises GraphValidationError on bad graphs."""
    issues = graph.validate()
    if issues:
        raise GraphValidationError(issues)

    ev = _Evaluator(graph, progress_callback)
    ev.evaluate_sinks()

    result = SystemResult(warnings=ev.warnings)
    for edge in graph.edges:
        if edge.id in ev.edge_signals:
            result.edges[edge.id] = ev.edge_signals[edge.id].to_dict()
    result.nodes = ev.node_results
    result.outputs = ev.outputs

    if progress_callback is not None:
        progress_callback(1.0)
    return result
