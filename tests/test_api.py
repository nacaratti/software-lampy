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
