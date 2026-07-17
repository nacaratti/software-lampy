"""API tests for the GNLSE pulse-propagation job endpoint."""
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
import backend.app.models.device  # noqa: F401


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


def _wait_for_job(client, job_id, timeout_s=15.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        info = client.get(f"/api/jobs/{job_id}").json()
        if info["status"] in ("completed", "error", "cancelled"):
            return info
        time.sleep(0.05)
    raise TimeoutError(f"job {job_id} did not finish in {timeout_s}s")


def _base_payload(**overrides):
    payload = {
        "pulse_shape": "sech2",
        "wavelength_nm": 1550.0,
        "peak_power_w": 1000.0,
        "duration_fs": 100.0,
        "time_window_ps": 10.0,
        "num_points": 512,
        "length_mm": 5.0,
        "gamma_per_w_per_km": 1.3,
        "beta2_ps2_per_km": -20.0,
        "beta3_ps3_per_km": 0.0,
        "loss_db_per_m": 0.0,
        "self_steepening": True,
        "raman": True,
        "enable_gain": False,
        "z_steps": 100,
        "save_z_slices": 30,
    }
    payload.update(overrides)
    return payload


def test_gnlse_passive_pulse_broadens_spectrum(client):
    created = client.post("/api/gnlse", json=_base_payload())
    assert created.status_code == 200, created.text
    job_id = created.json()["job_id"]

    info = _wait_for_job(client, job_id)
    assert info["status"] == "completed", info

    result = client.get(f"/api/jobs/{job_id}/result").json()
    assert len(result["z_mm"]) == 30
    assert len(result["wavelength_nm"]) == 512
    assert result["saturated_gain_db_per_m"] is None
    # SPM broadens the spectrum for a high-peak-power pulse in anomalous dispersion.
    in_width = sum(1 for p in result["input_spectral_power"] if p > max(result["input_spectral_power"]) * 0.1)
    out_width = sum(1 for p in result["output_spectral_power"] if p > max(result["output_spectral_power"]) * 0.1)
    assert out_width >= in_width


def test_gnlse_with_gain_reports_saturated_gain_and_amplifies(client):
    created = client.post("/api/gnlse", json=_base_payload(
        enable_gain=True, small_signal_gain_db_per_m=5.0, saturation_energy_nj=50.0, loss_db_per_m=0.0,
    ))
    assert created.status_code == 200, created.text
    job_id = created.json()["job_id"]

    info = _wait_for_job(client, job_id)
    assert info["status"] == "completed", info

    result = client.get(f"/api/jobs/{job_id}/result").json()
    assert result["saturated_gain_db_per_m"] is not None
    assert result["saturated_gain_db_per_m"] > 0.0
    assert result["output_energy_nj"] > result["input_energy_nj"]


def test_gnlse_rejects_invalid_pulse_shape(client):
    resp = client.post("/api/gnlse", json=_base_payload(pulse_shape="not_a_shape"))
    assert resp.status_code == 422
