"""Backend API tests using an isolated in-memory SQLite database."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
import backend.app.models.device  # noqa: F401 — registers ORM model


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_devices_shelf_seeded_on_first_list(client):
    resp = client.get("/api/devices")
    assert resp.status_code == 200
    devices = resp.json()
    shelf = [d for d in devices if d["category"] == "shelf"]
    assert len(shelf) > 0, "shelf catalogue should be auto-seeded"


def test_device_crud_lifecycle(client):
    payload = {
        "name": "Test Yb Fiber",
        "device_type": "fiber_active",
        "parameters": {"core_radius_um": 5.0},
    }
    created = client.post("/api/devices", json=payload)
    assert created.status_code == 201
    device = created.json()
    assert device["category"] == "custom"
    device_id = device["id"]

    fetched = client.get(f"/api/devices/{device_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Test Yb Fiber"

    updated = client.put(f"/api/devices/{device_id}", json={"name": "Renamed"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"

    deleted = client.delete(f"/api/devices/{device_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/devices/{device_id}").status_code == 404


def test_shelf_devices_are_immutable(client):
    devices = client.get("/api/devices").json()
    shelf_id = next(d["id"] for d in devices if d["category"] == "shelf")
    assert client.put(f"/api/devices/{shelf_id}", json={"name": "x"}).status_code == 403
    assert client.delete(f"/api/devices/{shelf_id}").status_code == 403


def test_invalid_device_type_rejected(client):
    resp = client.post("/api/devices", json={"name": "Bad", "device_type": "not_a_type"})
    assert resp.status_code == 422


STEP_FIBER = {
    "kind": "step",
    "core_radius_um": 5.0,
    "cladding_radius_um": 62.5,
    "core_material": {"kind": "constant", "index": 1.45},
    "cladding_material": {"kind": "constant", "index": 1.4407},
}


def test_modes_analytical_endpoint(client):
    resp = client.post(
        "/api/modes/analytical",
        json={"fiber": STEP_FIBER, "wavelength_nm": 1030.0, "grid_size": 64},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["method"] == "analytical"
    # V = 5.00 -> LP01, LP02, LP11, LP21
    assert body["num_modes"] == 4
    labels = {(m["l"], m["m"]) for m in body["modes"]}
    assert labels == {(0, 1), (0, 2), (1, 1), (2, 1)}
    for m in body["modes"]:
        assert 1.4407 < m["n_eff"] < 1.45


def test_solver_error_is_clean_422(client):
    """Physically invalid input -> 422 with a short message, never a traceback."""
    inverted = dict(STEP_FIBER)
    inverted["core_material"] = {"kind": "constant", "index": 1.40}  # n_core < n_clad
    resp = client.post(
        "/api/modes/analytical",
        json={"fiber": inverted, "wavelength_nm": 1030.0},
    )
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert "Traceback" not in detail
    assert "\n" not in detail


def test_index_preview_endpoint(client):
    resp = client.post(
        "/api/fibers/preview-index",
        json={"fiber": STEP_FIBER, "wavelength_nm": 1030.0, "num_points": 100},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["n_core"] == pytest.approx(1.45)
    assert body["n_cladding"] == pytest.approx(1.4407)
    assert len(body["r_um"]) == len(body["n"]) == 100


def test_ion_cross_sections_endpoint_matches_ion_model(client):
    resp = client.post(
        "/api/fibers/ion-cross-sections",
        json={"ion": "yb", "wavelengths_nm": [976.0, 1064.0]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["sigma_abs_m2"]) == 2
    assert len(body["sigma_em_m2"]) == 2

    from fibersim.core.ions import ActiveIon
    yb = ActiveIon.create_yb3()
    a976, e976 = yb.get_cross_sections(976e-9)
    assert body["sigma_abs_m2"][0] == pytest.approx(a976, rel=1e-9)
    assert body["sigma_em_m2"][0] == pytest.approx(e976, rel=1e-9)


def test_ion_cross_sections_endpoint_supports_er_and_tm(client):
    resp = client.post(
        "/api/fibers/ion-cross-sections",
        json={"ion": "er", "wavelengths_nm": [1530.0]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["sigma_abs_m2"][0] > 0

    resp = client.post(
        "/api/fibers/ion-cross-sections",
        json={"ion": "tm", "wavelengths_nm": [790.0]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["sigma_abs_m2"][0] > 0


def test_catalog_absorption_carries_its_own_wavelength(client):
    devices = client.get("/api/devices").json()
    by_ion = {}
    for d in devices:
        p = d["parameters"]
        if d["device_type"] == "fiber_active" and d["category"] == "shelf":
            assert "peak_absorption_dB_m_976nm" not in p
            by_ion.setdefault(p.get("ion", "yb"), set()).add(p["absorption_wavelength_nm"])
    # Yb DC fibers specify cladding absorption at 915/920 nm, core-pumped Nufern at 976
    assert by_ion == {"yb": {915, 920, 976}, "er": {1530, 1535}, "tm": {790}}


def test_legacy_absorption_key_is_migrated():
    import json
    from sqlalchemy.orm import Session
    from backend.app.models.device import Device
    from backend.app.routers.devices import _seed_shelf

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        db.add(Device(name="ER12-6", device_type="fiber_active", category="shelf",
                      parameters=json.dumps({"ion": "er", "peak_absorption_dB_m_976nm": 12.0})))
        db.add(Device(name="DCF-YB-20/128E", device_type="fiber_active", category="shelf",
                      parameters=json.dumps({"peak_absorption_dB_m": 3.0, "absorption_wavelength_nm": 976})))
        db.add(Device(name="My fiber", device_type="fiber_active", category="custom",
                      parameters=json.dumps({"peak_absorption_dB_m_976nm": 300.0})))
        db.commit()
        _seed_shelf(db)
        er = json.loads(db.query(Device).filter_by(name="ER12-6").one().parameters)
        mine = json.loads(db.query(Device).filter_by(name="My fiber").one().parameters)
        dcf = json.loads(db.query(Device).filter_by(name="DCF-YB-20/128E").one().parameters)
    assert er["peak_absorption_dB_m"] == 12.0 and er["absorption_wavelength_nm"] == 1530
    assert dcf["absorption_wavelength_nm"] == 915  # earlier mislabeled row re-synced
    assert mine["peak_absorption_dB_m"] == 300.0 and mine["absorption_wavelength_nm"] == 976
    assert "peak_absorption_dB_m_976nm" not in er and "peak_absorption_dB_m_976nm" not in mine
