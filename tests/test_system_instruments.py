"""System-level tests for instrument taps: OSA, power meter, beam profiler."""
import numpy as np
import pytest

from fibersim.system import SystemEdge, SystemGraph, SystemNode, simulate_system

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
    "length_m": 3.0,  # long enough to fully absorb the pump so the signal dominates the spectrum
    "ion": "yb",
}


def _node(nid, kind, **params):
    return SystemNode(id=nid, kind=kind, params=params, label=nid)


def _edge(eid, src, dst, target_port="in"):
    return SystemEdge(id=eid, source=src, target=dst, target_port=target_port)


def _amplifier_with_taps(*tap_kinds: str):
    """Seed -> WDM(+pump) -> Yb fiber -> Output, with extra instrument taps on the fiber's output edge."""
    nodes = [
        _node("seed", "seed", wavelength_nm=1064.0, power_w=0.01),
        _node("pump", "pump_source", wavelength_nm=976.0, power_w=2.0),
        _node("wdm", "coupler_wdm"),
        _node("yb", "fiber_active", **YB_FIBER),
        _node("out", "power_meter"),
    ]
    edges = [
        _edge("e0", "seed", "wdm"),
        _edge("e1", "pump", "wdm", target_port="pump"),
        _edge("e2", "wdm", "yb"),
        _edge("e3", "yb", "out"),
    ]
    for i, kind in enumerate(tap_kinds):
        tap_id = f"tap{i}"
        nodes.append(_node(tap_id, kind))
        edges.append(_edge(f"etap{i}", "yb", tap_id))
    return SystemGraph(nodes, edges)


# ---------------------------------------------------------------------------
# OSA
# ---------------------------------------------------------------------------

def test_osa_tap_reports_signal_peak():
    graph = _amplifier_with_taps("osa")
    res = simulate_system(graph)
    osa = res.outputs["tap0"]["osa"]
    assert osa["peak_wavelength_nm"] == pytest.approx(1064.0, abs=0.5)
    assert osa["peak_power_dbm"] > 0
    assert len(osa["wavelengths_nm"]) == len(osa["power_dbm"])


def test_osa_custom_rbw_param():
    nodes = list(_amplifier_with_taps().nodes.values())
    graph = _amplifier_with_taps("osa")
    # Override the tap's RBW via its params
    graph.node("tap0").params["rbw_nm"] = 0.5
    res = simulate_system(graph)
    assert res.outputs["tap0"]["osa"]["rbw_nm"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Power meter
# ---------------------------------------------------------------------------

def test_power_meter_tap_matches_output_breakdown():
    graph = _amplifier_with_taps("power_meter")
    res = simulate_system(graph)
    pm = res.outputs["tap0"]["power_meter"]
    out = res.outputs["tap0"]  # generic breakdown is present on every sink, incl. instruments
    assert pm["total_power_w"] == pytest.approx(out["total_power_w"])
    assert pm["band_power_w"]["signal"] == pytest.approx(out["signal_power_w"])
    assert pm["band_power_w"].get("pump", 0.0) == pytest.approx(out["pump_power_w"], abs=1e-9)


# ---------------------------------------------------------------------------
# Beam profiler
# ---------------------------------------------------------------------------

def test_beam_profiler_tap_reports_m2():
    graph = _amplifier_with_taps("beam_profiler")
    res = simulate_system(graph)
    beam = res.outputs["tap0"]["beam"]
    assert beam["m2x"] >= 1.0
    assert beam["m2y"] >= 1.0
    assert beam["is_single_mode"]  # YB_FIBER core_radius_um=2.5 -> single-mode at 1064nm
    assert np.array(beam["images"]).shape[1:] == (128, 128)


def test_beam_profiler_omits_tmi_badge_for_singlemode_fiber():
    """YB_FIBER is deeply single-mode (2.5um core) — no LP11 to couple to,
    so no TMI risk fraction should be reported at all."""
    graph = _amplifier_with_taps("beam_profiler")
    res = simulate_system(graph)
    assert "tmi_risk_fraction" not in res.outputs["tap0"]["beam"]
    assert "tmi_risk_fraction" not in res.nodes["yb"]


def test_beam_profiler_reports_tmi_badge_for_multimode_high_power_fiber():
    """A large-core, high-power Yb amplifier supports a distinct LP11 mode
    and generates enough quantum-defect heat that the TMI risk-fraction
    diagnostic (Fase 4b.5) should appear on both the fiber node and the
    downstream beam profiler's badge."""
    fiber_params = dict(YB_FIBER)
    fiber_params["core_radius_um"] = 15.0
    fiber_params["length_m"] = 1.5
    nodes = [
        _node("seed", "seed", wavelength_nm=1064.0, power_w=0.01),
        _node("pump", "pump_source", wavelength_nm=976.0, power_w=200.0),
        _node("wdm", "coupler_wdm"),
        _node("yb", "fiber_active", **fiber_params),
        _node("out", "power_meter"),
        _node("beam", "beam_profiler"),
    ]
    edges = [
        _edge("e0", "seed", "wdm"),
        _edge("e1", "pump", "wdm", target_port="pump"),
        _edge("e2", "wdm", "yb"),
        _edge("e3", "yb", "out"),
        _edge("e4", "yb", "beam"),
    ]
    res = simulate_system(SystemGraph(nodes, edges))
    yb = res.nodes["yb"]
    assert "tmi_risk_fraction" in yb
    assert yb["tmi_risk_fraction"] >= 0.0
    assert res.outputs["beam"]["beam"]["tmi_risk_fraction"] == pytest.approx(yb["tmi_risk_fraction"])


def test_beam_profiler_without_upstream_fiber_warns_instead_of_crashing():
    nodes = [
        _node("pump", "pump_source", wavelength_nm=976.0, power_w=1.0),
        _node("beam", "beam_profiler"),
    ]
    edges = [_edge("e0", "pump", "beam")]
    res = simulate_system(SystemGraph(nodes, edges))
    assert "beam" not in res.outputs["beam"]
    assert any("upstream fiber" in w for w in res.warnings)


# ---------------------------------------------------------------------------
# Multiple simultaneous taps
# ---------------------------------------------------------------------------

def test_all_three_instruments_can_tap_the_same_node():
    graph = _amplifier_with_taps("osa", "power_meter", "beam_profiler")
    res = simulate_system(graph)
    assert "osa" in res.outputs["tap0"]
    assert "power_meter" in res.outputs["tap1"]
    assert "beam" in res.outputs["tap2"]
    # The main chain output must be unaffected by the taps
    assert res.outputs["out"]["signal_power_w"] > 0.01
