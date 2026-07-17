"""System-level engine tests: graph validation, amplifier chains, laser cavities."""
import numpy as np
import pytest

from fibersim.system import (
    GraphValidationError,
    OpticalSignal,
    SystemEdge,
    SystemGraph,
    SystemNode,
    simulate_system,
)

YB_FIBER = {
    "core_radius_um": 2.5,
    "clad_radius_um": 62.5,
    "n_core": 1.46,
    "n_clad": 1.454,
    "N_total": 3e25,
    "tau_ms": 0.84,
    "gamma_pump": 0.85,
    "gamma_signal": 0.82,
    "background_loss_db_m": 0.005,
    "length_m": 0.3,
    "ion": "yb",
}


def _node(nid, kind, **params):
    return SystemNode(id=nid, kind=kind, params=params, label=nid)


def _edge(eid, src, dst, target_port="in"):
    return SystemEdge(id=eid, source=src, target=dst, target_port=target_port)


# ---------------------------------------------------------------------------
# Graph validation
# ---------------------------------------------------------------------------

def test_empty_graph_rejected():
    graph = SystemGraph([], [])
    assert graph.validate()


def test_cycle_rejected():
    nodes = [
        _node("a", "fiber_passive"),
        _node("b", "fiber_passive"),
        _node("seed", "seed"),
        _node("out", "power_meter"),
    ]
    edges = [
        _edge("e0", "seed", "a"),
        _edge("e1", "a", "b"),
        _edge("e2", "b", "a"),  # cycle
        _edge("e3", "b", "out"),
    ]
    issues = SystemGraph(nodes, edges).validate()
    assert any("cycle" in i.lower() for i in issues)


def test_source_cannot_receive_input():
    nodes = [_node("seed", "seed"), _node("pump", "pump_source"), _node("out", "power_meter")]
    edges = [_edge("e0", "seed", "pump"), _edge("e1", "pump", "out")]
    issues = SystemGraph(nodes, edges).validate()
    assert any("source" in i.lower() for i in issues)


def test_valid_amplifier_graph_passes():
    graph = _amplifier_graph()
    assert graph.validate() == []


def test_simulate_invalid_graph_raises():
    with pytest.raises(GraphValidationError):
        simulate_system(SystemGraph([], []))


# ---------------------------------------------------------------------------
# Amplifier chain (MOPA stage)
# ---------------------------------------------------------------------------

def _amplifier_graph(pump_w=2.0, seed_w=0.01):
    nodes = [
        _node("seed", "seed", wavelength_nm=1064.0, power_w=seed_w),
        _node("pump", "pump_source", wavelength_nm=976.0, power_w=pump_w),
        _node("wdm", "coupler_wdm", insertion_loss_port1_db=0.3, insertion_loss_port2_db=0.4),
        _node("yb", "fiber_active", **YB_FIBER),
        _node("out", "power_meter"),
    ]
    edges = [
        _edge("e0", "seed", "wdm"),
        _edge("e1", "pump", "wdm", target_port="pump"),
        _edge("e2", "wdm", "yb"),
        _edge("e3", "yb", "out"),
    ]
    return SystemGraph(nodes, edges)


@pytest.fixture(scope="module")
def amplifier_result():
    return simulate_system(_amplifier_graph())


def test_amplifier_signal_gain(amplifier_result):
    out = amplifier_result.outputs["out"]
    assert out["signal_power_w"] > 0.01, "seed should be amplified"
    yb = amplifier_result.nodes["yb"]
    assert yb["gain_db"] is not None and yb["gain_db"] > 3.0


def test_amplifier_energy_conservation(amplifier_result):
    out = amplifier_result.outputs["out"]
    yb = amplifier_result.nodes["yb"]
    total_out = out["total_power_w"] + yb["backward_ase_out_w"]
    assert total_out <= (2.0 + 0.01) * 1.02


def test_amplifier_records_edge_spectra(amplifier_result):
    assert "e2" in amplifier_result.edges
    e2 = amplifier_result.edges["e2"]
    # WDM output carries both the pump line and the seed line
    kinds = set(e2["kinds"])
    assert {"pump", "signal"} <= kinds


def test_output_knows_source_fiber(amplifier_result):
    src = amplifier_result.outputs["out"]["source_fiber"]
    assert src is not None and src["node_id"] == "yb"


# ---------------------------------------------------------------------------
# Laser cavity (FBG pair)
# ---------------------------------------------------------------------------

def _cavity_graph(pump_w=10.0, r_oc=0.1):
    nodes = [
        _node("pump", "pump_source", wavelength_nm=976.0, power_w=pump_w),
        _node("hr", "fbg", central_wavelength_nm=1064.0, reflectivity=0.99,
              bandwidth_nm=0.5, length_mm=10.0, n_eff=1.45),
        _node("wdm", "coupler_wdm", insertion_loss_port1_db=0.2, insertion_loss_port2_db=0.3),
        _node("yb", "fiber_active", **YB_FIBER),
        _node("oc", "fbg", central_wavelength_nm=1064.0, reflectivity=r_oc,
              bandwidth_nm=0.5, length_mm=5.0, n_eff=1.45),
        _node("out", "power_meter"),
    ]
    edges = [
        _edge("e0", "hr", "wdm"),
        _edge("e1", "pump", "wdm", target_port="pump"),
        _edge("e2", "wdm", "yb"),
        _edge("e3", "yb", "oc"),
        _edge("e4", "oc", "out"),
    ]
    return SystemGraph(nodes, edges)


def test_cavity_is_detected():
    graph = _cavity_graph()
    cavities = graph.detect_cavities()
    assert len(cavities) == 1
    cav = cavities[0]
    assert cav.left_fbg.id == "hr" and cav.right_fbg.id == "oc"
    assert [n.id for n in cav.inner_nodes] == ["wdm", "yb"]


@pytest.fixture(scope="module")
def cavity_result():
    return simulate_system(_cavity_graph())


def test_cavity_lases(cavity_result):
    out = cavity_result.outputs["out"]
    laser_power = out["signal_power_w"] + out["ase_power_w"]
    assert laser_power > 1.0, f"expected lasing, got {laser_power:.3f} W"


def test_cavity_below_quantum_limit(cavity_result):
    out = cavity_result.outputs["out"]
    assert out["total_power_w"] <= 10.0 * (976.0 / 1064.0) * 1.05


def test_cavity_gain_node_annotated(cavity_result):
    yb = cavity_result.nodes["yb"]
    assert yb["role"] == "cavity_gain"
    assert yb["laser_wavelength_nm"] == pytest.approx(1064.0)
    assert yb["r1_at_laser"] > 0.9


# ---------------------------------------------------------------------------
# Two-stage MOPA with ASE hand-off
# ---------------------------------------------------------------------------

def test_mopa_second_stage_amplifies_further():
    nodes = [
        _node("seed", "seed", wavelength_nm=1064.0, power_w=0.001),
        _node("p1", "pump_source", wavelength_nm=976.0, power_w=1.0),
        _node("p2", "pump_source", wavelength_nm=976.0, power_w=5.0),
        _node("wdm1", "coupler_wdm"),
        _node("wdm2", "coupler_wdm"),
        _node("yb1", "fiber_active", **YB_FIBER),
        _node("yb2", "fiber_active", **YB_FIBER),
        _node("out", "power_meter"),
    ]
    edges = [
        _edge("e0", "seed", "wdm1"),
        _edge("e1", "p1", "wdm1", target_port="pump"),
        _edge("e2", "wdm1", "yb1"),
        _edge("e3", "yb1", "wdm2"),
        _edge("e4", "p2", "wdm2", target_port="pump"),
        _edge("e5", "wdm2", "yb2"),
        _edge("e6", "yb2", "out"),
    ]
    res = simulate_system(SystemGraph(nodes, edges))
    s1 = res.nodes["yb1"]["signal_out_w"]
    s2 = res.nodes["yb2"]["signal_out_w"]
    assert s2 > s1 > 0.001


# ---------------------------------------------------------------------------
# Counter-propagating pump
# ---------------------------------------------------------------------------

def test_counter_pumped_amplifier():
    nodes = [
        _node("seed", "seed", wavelength_nm=1064.0, power_w=0.01),
        _node("pump", "pump_source", wavelength_nm=976.0, power_w=2.0),
        _node("yb", "fiber_active", **YB_FIBER),
        _node("wdm", "coupler_wdm"),
        _node("out", "power_meter"),
    ]
    edges = [
        _edge("e0", "seed", "yb"),
        _edge("e1", "yb", "wdm"),
        _edge("e2", "pump", "wdm", target_port="pump"),
        _edge("e3", "wdm", "out"),
    ]
    res = simulate_system(SystemGraph(nodes, edges))
    yb = res.nodes["yb"]
    assert yb["gain_db"] is not None and yb["gain_db"] > 3.0
    # Pump entered backward: forward pump profile at z=0 must be ~zero
    assert res.nodes["yb"]["pump_forward_w"][0] == pytest.approx(0.0, abs=1e-9)
    assert res.nodes["yb"]["pump_backward_w"][-1] > 0.5


# ---------------------------------------------------------------------------
# Instrument taps
# ---------------------------------------------------------------------------

def test_instrument_tap_records_spectrum():
    graph = _amplifier_graph()
    graph_nodes = list(graph.nodes.values()) + [_node("osa1", "osa")]
    graph_edges = graph.edges + [_edge("t0", "yb", "osa1")]
    res = simulate_system(SystemGraph(graph_nodes, graph_edges))
    assert "osa1" in res.outputs
    spectrum = res.outputs["osa1"]["signal"]
    assert len(spectrum["wavelengths_nm"]) > 0
    assert res.outputs["osa1"]["total_power_w"] > 0


def test_progress_callback_reports_completion():
    values = []
    simulate_system(_amplifier_graph(), progress_callback=lambda v: values.append(v) or None)
    assert values and values[-1] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Power combiner (N x 1)
# ---------------------------------------------------------------------------

def _combiner_graph(pump_powers=(1.0, 1.5, 0.5), insertion_loss_db=0.5):
    nodes = [
        _node("seed", "seed", wavelength_nm=1064.0, power_w=0.01),
        _node("combiner", "power_combiner", insertion_loss_db=insertion_loss_db),
        _node("wdm", "coupler_wdm"),
        _node("yb", "fiber_active", **YB_FIBER),
        _node("out", "power_meter"),
    ]
    edges = [
        _edge("e0", "seed", "wdm"),
        _edge("e1", "combiner", "wdm", target_port="pump"),
        _edge("e2", "wdm", "yb"),
        _edge("e3", "yb", "out"),
    ]
    for i, p in enumerate(pump_powers):
        pid = f"pump{i}"
        nodes.append(_node(pid, "pump_source", wavelength_nm=976.0, power_w=p))
        edges.append(_edge(f"ep{i}", pid, "combiner"))
    return SystemGraph(nodes, edges)


def test_power_combiner_allows_multiple_main_inputs():
    graph = _combiner_graph()
    assert graph.validate() == []


def test_single_main_input_kinds_still_reject_multiple():
    nodes = [
        _node("p1", "pump_source", wavelength_nm=976.0, power_w=1.0),
        _node("p2", "pump_source", wavelength_nm=976.0, power_w=1.0),
        _node("fiber", "fiber_passive"),
        _node("out", "power_meter"),
    ]
    edges = [
        _edge("e0", "p1", "fiber"),
        _edge("e1", "p2", "fiber"),
        _edge("e2", "fiber", "out"),
    ]
    issues = SystemGraph(nodes, edges).validate()
    assert any("main input" in i for i in issues)


def test_power_combiner_sums_input_power():
    graph = _combiner_graph(pump_powers=(1.0, 1.5, 0.5), insertion_loss_db=0.0)
    res = simulate_system(graph)
    combined = res.nodes["combiner"]["combined_power_w"]
    assert combined == pytest.approx(3.0, rel=1e-9)
    assert res.nodes["combiner"]["num_inputs"] == 3


def test_power_combiner_applies_insertion_loss():
    lossless = simulate_system(_combiner_graph(pump_powers=(2.0,), insertion_loss_db=0.0))
    lossy = simulate_system(_combiner_graph(pump_powers=(2.0,), insertion_loss_db=3.0))
    combined_lossless = lossless.nodes["combiner"]["combined_power_w"]
    combined_lossy = lossy.nodes["combiner"]["combined_power_w"]
    # 3 dB insertion loss -> half the power
    assert combined_lossy == pytest.approx(combined_lossless * 10 ** (-3.0 / 10.0), rel=1e-9)


def test_power_combiner_feeds_gain_fiber():
    graph = _combiner_graph(pump_powers=(1.5, 1.5), insertion_loss_db=0.0)
    res = simulate_system(graph)
    yb = res.nodes["yb"]
    # Combiner sums to 3.0 W; the WDM's own pump-port insertion loss (0.4 dB
    # default) still applies on top of that.
    expected = 3.0 * 10 ** (-0.4 / 10.0)
    assert yb["pump_in_w"] == pytest.approx(expected, rel=1e-6)
    assert yb["gain_db"] is not None and yb["gain_db"] > 0


# ---------------------------------------------------------------------------
# Automatic Γ (mode/dopant overlap) — no manual scalar required
# ---------------------------------------------------------------------------

YB_FIBER_AUTO = {k: v for k, v in YB_FIBER.items() if k not in ("gamma_pump", "gamma_signal")}


def test_amplifier_works_without_manual_gamma():
    """Omitting gamma_pump/gamma_signal must still produce a working amplifier
    — Γ is derived from the real mode/dopant overlap instead."""
    nodes = [
        _node("seed", "seed", wavelength_nm=1064.0, power_w=0.01),
        _node("pump", "pump_source", wavelength_nm=976.0, power_w=2.0),
        _node("wdm", "coupler_wdm"),
        _node("yb", "fiber_active", **YB_FIBER_AUTO),
        _node("out", "power_meter"),
    ]
    edges = [
        _edge("e0", "seed", "wdm"),
        _edge("e1", "pump", "wdm", target_port="pump"),
        _edge("e2", "wdm", "yb"),
        _edge("e3", "yb", "out"),
    ]
    res = simulate_system(SystemGraph(nodes, edges))
    yb = res.nodes["yb"]
    assert yb["gain_db"] is not None and yb["gain_db"] > 3.0
    assert not res.warnings


def test_auto_gamma_close_to_historical_manual_default():
    """Sanity check: the physically-derived Γ for this fiber/wavelength combo
    should land in the same ballpark as the old hand-picked 0.82-0.85 default
    (single-mode step-index core, well above cutoff)."""
    auto = simulate_system(_amplifier_graph_from(YB_FIBER_AUTO))
    manual = simulate_system(_amplifier_graph_from(YB_FIBER))
    gain_auto = auto.nodes["yb"]["gain_db"]
    gain_manual = manual.nodes["yb"]["gain_db"]
    assert gain_auto == pytest.approx(gain_manual, rel=0.15)


def test_manual_gamma_override_still_respected():
    """An explicit gamma_pump/gamma_signal must win over the automatic value."""
    fiber_params = dict(YB_FIBER_AUTO)
    fiber_params["gamma_pump"] = 0.01  # deliberately tiny -> starves the fiber of pump
    graph = _amplifier_graph_from(fiber_params)
    res = simulate_system(graph)
    yb = res.nodes["yb"]
    # With almost no pump overlap, gain should be far below the auto-Γ case.
    auto_gain = simulate_system(_amplifier_graph_from(YB_FIBER_AUTO)).nodes["yb"]["gain_db"]
    assert yb["gain_db"] is None or yb["gain_db"] < auto_gain


def test_double_clad_pump_uses_area_ratio_overlap():
    """A cladding-pumped double-clad fiber should show markedly weaker pump
    absorption than an equivalent core-pumped single-clad fiber, since Γ_pump
    is the tiny core/inner-cladding area ratio rather than a near-unity modal
    overlap."""
    dc_params = dict(YB_FIBER_AUTO)
    dc_params["clad_radius_um"] = 125.0  # becomes the OUTER cladding
    dc_params["inner_cladding_radius_um"] = 100.0
    dc_params["length_m"] = 5.0  # cladding-pumped fibers are much longer

    graph = _amplifier_graph_from(dc_params)
    res = simulate_system(graph)
    yb = res.nodes["yb"]
    # Barely any pump absorbed over 5 m at this tiny overlap.
    assert yb["pump_in_w"] > 0
    pump_out = yb["pump_forward_w"][-1]
    absorbed_fraction = 1.0 - pump_out / yb["pump_in_w"]
    assert absorbed_fraction < 0.2


def _amplifier_graph_from(fiber_params: dict, pump_w=2.0, seed_w=0.01):
    nodes = [
        _node("seed", "seed", wavelength_nm=1064.0, power_w=seed_w),
        _node("pump", "pump_source", wavelength_nm=976.0, power_w=pump_w),
        _node("wdm", "coupler_wdm"),
        _node("yb", "fiber_active", **fiber_params),
        _node("out", "power_meter"),
    ]
    edges = [
        _edge("e0", "seed", "wdm"),
        _edge("e1", "pump", "wdm", target_port="pump"),
        _edge("e2", "wdm", "yb"),
        _edge("e3", "yb", "out"),
    ]
    return SystemGraph(nodes, edges)


# ---------------------------------------------------------------------------
# SRS/SBS threshold warnings
# ---------------------------------------------------------------------------

def test_low_power_fiber_reports_thresholds_without_warning():
    res = simulate_system(_amplifier_graph_from(YB_FIBER_AUTO, pump_w=2.0))
    yb = res.nodes["yb"]
    assert yb["srs_threshold_w"] > 0
    assert yb["sbs_threshold_w"] > 0
    assert yb["effective_area_um2"] > 0
    assert not res.warnings


def test_high_power_fiber_triggers_sbs_warning():
    fiber_params = dict(YB_FIBER_AUTO)
    fiber_params["length_m"] = 2.0
    res = simulate_system(_amplifier_graph_from(fiber_params, pump_w=50.0))
    yb = res.nodes["yb"]
    assert yb["peak_signal_power_w"] > yb["sbs_threshold_w"] * 0.5
    assert any("SBS threshold" in w for w in res.warnings)
    # SRS threshold is orders of magnitude higher than SBS for a narrow-linewidth
    # signal — the physically expected ordering for high-power fiber lasers.
    assert yb["srs_threshold_w"] > yb["sbs_threshold_w"] * 10


def test_effective_area_matches_core_geometry_order_of_magnitude():
    res = simulate_system(_amplifier_graph_from(YB_FIBER_AUTO))
    a_eff_um2 = res.nodes["yb"]["effective_area_um2"]
    core_area_um2 = 3.14159 * 2.5 ** 2  # core_radius_um = 2.5 in YB_FIBER
    assert 0.3 * core_area_um2 < a_eff_um2 < 5.0 * core_area_um2


# ---------------------------------------------------------------------------
# Photodarkening diagnostics (Yb only)
# ---------------------------------------------------------------------------

def test_yb_fiber_reports_photodarkening_diagnostics():
    res = simulate_system(_amplifier_graph_from(YB_FIBER_AUTO))
    yb = res.nodes["yb"]
    assert yb["photodarkening_peak_db_m"] >= 0.0
    assert yb["photodarkening_extra_loss_db_saturated"] >= 0.0


def test_long_high_inversion_yb_fiber_triggers_photodarkening_warning():
    fiber_params = dict(YB_FIBER_AUTO)
    fiber_params["length_m"] = 20.0
    res = simulate_system(_amplifier_graph_from(fiber_params, pump_w=50.0))
    yb = res.nodes["yb"]
    assert yb["photodarkening_extra_loss_db_saturated"] > 1.0
    assert any("photodarkening" in w for w in res.warnings)


# ---------------------------------------------------------------------------
# ESA/upconversion diagnostics (Tm cross-relaxation, Er cooperative upconversion)
# ---------------------------------------------------------------------------

def test_tm_fiber_reports_cross_relaxation_yield_for_790nm_pump():
    nodes = [
        _node("seed", "seed", wavelength_nm=1900.0, power_w=0.01),
        _node("pump", "pump_source", wavelength_nm=790.0, power_w=3.0),
        _node("wdm", "coupler_wdm", wavelength_1_nm=790.0, wavelength_2_nm=1900.0),
        _node("tm", "fiber_active", core_radius_um=3.0, clad_radius_um=62.5,
              n_core=1.46, n_clad=1.454, N_total=4e24, tau_ms=0.3,
              background_loss_db_m=0.005, length_m=1.0, ion="tm"),
        _node("out", "power_meter"),
    ]
    edges = [
        _edge("e0", "seed", "wdm"),
        _edge("e1", "pump", "wdm", target_port="pump"),
        _edge("e2", "wdm", "tm"),
        _edge("e3", "tm", "out"),
    ]
    res = simulate_system(SystemGraph(nodes, edges))
    tm = res.nodes["tm"]
    assert tm["tm_cross_relaxation_yield"] == pytest.approx(1.6)


def test_er_fiber_reports_upconversion_coefficient():
    nodes = [
        _node("seed", "seed", wavelength_nm=1550.0, power_w=0.001),
        _node("pump", "pump_source", wavelength_nm=980.0, power_w=1.0),
        _node("wdm", "coupler_wdm", wavelength_1_nm=980.0, wavelength_2_nm=1550.0),
        _node("er", "fiber_active", core_radius_um=3.0, clad_radius_um=62.5,
              n_core=1.46, n_clad=1.454, N_total=1e25, tau_ms=10.0,
              background_loss_db_m=0.005, length_m=5.0, ion="er"),
        _node("out", "power_meter"),
    ]
    edges = [
        _edge("e0", "seed", "wdm"),
        _edge("e1", "pump", "wdm", target_port="pump"),
        _edge("e2", "wdm", "er"),
        _edge("e3", "er", "out"),
    ]
    res = simulate_system(SystemGraph(nodes, edges))
    er = res.nodes["er"]
    assert er["er_upconversion_coeff_m3_s"] == pytest.approx(8e-24)
