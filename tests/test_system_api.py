"""API tests for the System Builder: graph validation, async simulation job,
and multi-project persistence (/api/systems)."""
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
import backend.app.models.device  # noqa: F401
import backend.app.models.system  # noqa: F401


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _amplifier_payload():
    yb_params = {
        "ion": "yb",
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
    }
    return {
        "nodes": [
            {"id": "seed", "kind": "seed", "params": {"wavelength_nm": 1064.0, "power_w": 0.01}},
            {"id": "pump", "kind": "pump_source", "params": {"wavelength_nm": 976.0, "power_w": 2.0}},
            {"id": "wdm", "kind": "coupler_wdm", "params": {}},
            {"id": "yb", "kind": "fiber_active", "params": yb_params},
            {"id": "out", "kind": "power_meter", "params": {}},
        ],
        "edges": [
            {"id": "e0", "source": "seed", "target": "wdm"},
            {"id": "e1", "source": "pump", "target": "wdm", "target_port": "pump"},
            {"id": "e2", "source": "wdm", "target": "yb"},
            {"id": "e3", "source": "yb", "target": "out"},
        ],
    }


def _wait_for_job(client, job_id, timeout_s=15.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        info = client.get(f"/api/jobs/{job_id}").json()
        if info["status"] in ("completed", "error", "cancelled"):
            return info
        time.sleep(0.05)
    raise TimeoutError(f"job {job_id} did not finish in {timeout_s}s")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_validate_empty_graph(client):
    resp = client.post("/api/system/validate", json={"nodes": [], "edges": []})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert body["issues"]


def test_validate_good_graph(client):
    resp = client.post("/api/system/validate", json=_amplifier_payload())
    assert resp.status_code == 200
    assert resp.json() == {"valid": True, "issues": []}


def test_unknown_node_kind_rejected_by_schema(client):
    payload = _amplifier_payload()
    payload["nodes"][0]["kind"] = "not_a_kind"
    resp = client.post("/api/system/validate", json=payload)
    assert resp.status_code == 422


def test_power_combiner_simulates_end_to_end(client):
    payload = _amplifier_payload()
    payload["nodes"][1] = {"id": "pump", "kind": "pump_source", "params": {"wavelength_nm": 976.0, "power_w": 1.0}}
    payload["nodes"].append(
        {"id": "pump2", "kind": "pump_source", "params": {"wavelength_nm": 976.0, "power_w": 1.0}}
    )
    payload["nodes"].append(
        {"id": "combiner", "kind": "power_combiner", "params": {"insertion_loss_db": 0.0}}
    )
    # Route both pumps through the combiner instead of directly into the WDM
    payload["edges"] = [
        {"id": "e0", "source": "seed", "target": "wdm"},
        {"id": "e1", "source": "combiner", "target": "wdm", "target_port": "pump"},
        {"id": "ec1", "source": "pump", "target": "combiner"},
        {"id": "ec2", "source": "pump2", "target": "combiner"},
        {"id": "e2", "source": "wdm", "target": "yb"},
        {"id": "e3", "source": "yb", "target": "out"},
    ]

    created = client.post("/api/system/simulate", json=payload)
    assert created.status_code == 200, created.text
    info = _wait_for_job(client, created.json()["job_id"])
    assert info["status"] == "completed", info

    result = client.get(f"/api/jobs/{created.json()['job_id']}/result").json()
    assert result["nodes"]["combiner"]["combined_power_w"] == pytest.approx(2.0, rel=1e-6)
    assert result["nodes"]["combiner"]["num_inputs"] == 2


# ---------------------------------------------------------------------------
# Simulation (async job)
# ---------------------------------------------------------------------------

def test_simulate_amplifier_end_to_end(client):
    created = client.post("/api/system/simulate", json=_amplifier_payload())
    assert created.status_code == 200, created.text
    job_id = created.json()["job_id"]

    info = _wait_for_job(client, job_id)
    assert info["status"] == "completed", info

    result = client.get(f"/api/jobs/{job_id}/result").json()
    out = result["outputs"]["out"]
    assert out["signal_power_w"] > 0.01
    assert result["nodes"]["yb"]["gain_db"] > 3.0


def test_simulate_invalid_graph_returns_422(client):
    created = client.post("/api/system/simulate", json={"nodes": [], "edges": []})
    assert created.status_code == 200
    job_id = created.json()["job_id"]
    info = _wait_for_job(client, job_id)
    assert info["status"] == "error"
    assert "empty" in info["error_message"].lower()


def test_simulate_with_instrument_taps_encodes_beam_images(client):
    """The beam profiler's image stack must survive the job's JSON round-trip
    as base64 EncodedArray dicts, not raw (non-serializable) numpy arrays."""
    payload = _amplifier_payload()
    payload["nodes"][3]["params"]["length_m"] = 3.0  # fully absorb the pump
    payload["nodes"].extend([
        {"id": "osa1", "kind": "osa", "params": {"rbw_nm": 0.2}},
        {"id": "pm1", "kind": "power_meter", "params": {}},
        {"id": "beam1", "kind": "beam_profiler", "params": {"grid_n": 64, "num_z": 9}},
    ])
    payload["edges"].extend([
        {"id": "t0", "source": "yb", "target": "osa1"},
        {"id": "t1", "source": "yb", "target": "pm1"},
        {"id": "t2", "source": "yb", "target": "beam1"},
    ])

    created = client.post("/api/system/simulate", json=payload)
    assert created.status_code == 200, created.text
    info = _wait_for_job(client, created.json()["job_id"])
    assert info["status"] == "completed", info

    result = client.get(f"/api/jobs/{created.json()['job_id']}/result").json()
    osa = result["outputs"]["osa1"]["osa"]
    assert osa["peak_wavelength_nm"] == pytest.approx(1064.0, abs=0.5)

    pm = result["outputs"]["pm1"]["power_meter"]
    assert pm["total_power_w"] > 0

    beam = result["outputs"]["beam1"]["beam"]
    images = beam["images"]
    assert images["dtype"] == "float32"
    assert images["shape"] == [9, 64, 64]
    assert isinstance(images["data"], str)  # base64, not a raw array
    assert beam["m2x"] >= 1.0


# ---------------------------------------------------------------------------
# Persistence (/api/systems)
# ---------------------------------------------------------------------------

def test_systems_crud_lifecycle(client):
    doc = {"nodes": [{"id": "a", "position": {"x": 0, "y": 0}}], "edges": []}
    created = client.post(
        "/api/systems", json={"name": "My Laser", "description": "test", "graph": doc}
    )
    assert created.status_code == 201, created.text
    system = created.json()
    system_id = system["id"]
    assert system["graph"] == doc

    listed = client.get("/api/systems").json()
    assert any(s["id"] == system_id for s in listed)

    fetched = client.get(f"/api/systems/{system_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "My Laser"

    updated = client.put(f"/api/systems/{system_id}", json={"name": "Renamed"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"

    dup = client.post(f"/api/systems/{system_id}/duplicate")
    assert dup.status_code == 201
    assert dup.json()["name"] == "Renamed (copy)"
    assert dup.json()["id"] != system_id

    deleted = client.delete(f"/api/systems/{system_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/systems/{system_id}").status_code == 404


def test_get_missing_system_404(client):
    assert client.get("/api/systems/does-not-exist").status_code == 404
