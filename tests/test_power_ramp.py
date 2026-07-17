"""API tests for the Power Ramp / Nonlinear Effects Explorer job endpoint."""
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


def _wait_for_job(client, job_id, timeout_s=30.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        info = client.get(f"/api/jobs/{job_id}").json()
        if info["status"] in ("completed", "error", "cancelled"):
            return info
        time.sleep(0.05)
    raise TimeoutError(f"job {job_id} did not finish in {timeout_s}s")


def _run_ramp(client, payload):
    created = client.post("/api/power-ramp", json=payload)
    assert created.status_code == 200, created.text
    job_id = created.json()["job_id"]
    info = _wait_for_job(client, job_id)
    assert info["status"] == "completed", info
    return client.get(f"/api/jobs/{job_id}/result").json()


def _effect(result, key):
    return next(e for e in result["effects"] if e["key"] == key)


YB_MULTIMODE_DOUBLE_CLAD = {
    "ion": "yb",
    "core_radius_um": 15.0,
    "clad_radius_um": 62.5,
    "inner_cladding_radius_um": 100.0,
    "n_core": 1.46,
    "n_clad": 1.454,
    "N_total": 3e25,
    "tau_ms": 0.84,
    "background_loss_db_m": 0.005,
    "length_m": 2.0,
}

YB_SINGLEMODE = {
    "ion": "yb",
    "core_radius_um": 2.5,
    "clad_radius_um": 62.5,
    "n_core": 1.46,
    "n_clad": 1.454,
    "N_total": 3e25,
    "tau_ms": 0.84,
    "background_loss_db_m": 0.005,
    "length_m": 2.0,
}


def test_multimode_yb_shows_increasing_tmi_risk(client):
    result = _run_ramp(client, {
        "fiber": YB_MULTIMODE_DOUBLE_CLAD,
        "pump_wavelength_nm": 976.0,
        "seed_wavelength_nm": 1064.0,
        "seed_power_w": 0.01,
        "pump_power_min_w": 5.0,
        "pump_power_max_w": 200.0,
        "num_steps": 8,
    })
    tmi = _effect(result, "tmi")
    assert tmi["applicable"] is True
    assert tmi["reason"] is None
    assert len(tmi["values"]) == 8
    assert tmi["values"][-1] > tmi["values"][0]
    assert tmi["threshold"] == pytest.approx(1.0)

    # Real ISO 11146 M^2 (LP01/LP11 mixture blended by risk fraction) should
    # degrade (increase) monotonically alongside the risk fraction, and stay
    # diffraction-limited (M^2~1) at the lowest-risk step.
    assert len(result["tmi_m2x"]) == 8
    assert result["tmi_m2x"][0] == pytest.approx(1.0, abs=0.2)
    assert result["tmi_m2x"][-1] > result["tmi_m2x"][0]
    assert result["tmi_m2y"][-1] > result["tmi_m2y"][0]
    assert result["tmi_coupling_fraction"][-1] > result["tmi_coupling_fraction"][0]
    assert result["tmi_lp01_image"] is not None
    assert result["tmi_lp11_image"] is not None
    assert len(result["tmi_image_x_um"]) > 0


def test_singlemode_yb_reports_tmi_not_applicable_with_reason(client):
    result = _run_ramp(client, {
        "fiber": YB_SINGLEMODE,
        "pump_wavelength_nm": 976.0,
        "seed_wavelength_nm": 1064.0,
        "seed_power_w": 0.01,
        "pump_power_min_w": 1.0,
        "pump_power_max_w": 20.0,
        "num_steps": 5,
    })
    tmi = _effect(result, "tmi")
    assert tmi["applicable"] is False
    assert "single-mode" in tmi["reason"]
    assert result["tmi_m2x"] == []
    assert result["tmi_lp01_image"] is None
    assert result["tmi_lp11_image"] is None
    assert tmi["values"] == []


def test_tm_790nm_pump_shows_active_cross_relaxation(client):
    fiber = {
        "ion": "tm",
        "core_radius_um": 5.0,
        "clad_radius_um": 62.5,
        "n_core": 1.46,
        "n_clad": 1.454,
        "N_total": 4e25,
        "tau_ms": 0.3,
        "background_loss_db_m": 0.01,
        "length_m": 1.0,
    }
    result = _run_ramp(client, {
        "fiber": fiber,
        "pump_wavelength_nm": 790.0,
        "seed_wavelength_nm": 1900.0,
        "seed_power_w": 0.01,
        "pump_power_min_w": 1.0,
        "pump_power_max_w": 10.0,
        "num_steps": 5,
    })
    esa = _effect(result, "esa_upconversion")
    assert esa["applicable"] is True
    assert esa["values"] == pytest.approx([1.6] * 5)


def test_er_shows_active_upconversion(client):
    fiber = {
        "ion": "er",
        "core_radius_um": 3.0,
        "clad_radius_um": 62.5,
        "n_core": 1.46,
        "n_clad": 1.454,
        "N_total": 1e25,
        "tau_ms": 10.0,
        "background_loss_db_m": 0.01,
        "length_m": 5.0,
    }
    result = _run_ramp(client, {
        "fiber": fiber,
        "pump_wavelength_nm": 980.0,
        "seed_wavelength_nm": 1550.0,
        "seed_power_w": 0.001,
        "pump_power_min_w": 0.5,
        "pump_power_max_w": 20.0,
        "num_steps": 6,
    })
    esa = _effect(result, "esa_upconversion")
    assert esa["applicable"] is True
    assert "Er upconversion" in esa["label"]
    assert len(esa["values"]) == 6


def test_peak_signal_power_and_thresholds_present_and_finite(client):
    result = _run_ramp(client, {
        "fiber": YB_MULTIMODE_DOUBLE_CLAD,
        "pump_wavelength_nm": 976.0,
        "seed_wavelength_nm": 1064.0,
        "seed_power_w": 0.01,
        "pump_power_min_w": 5.0,
        "pump_power_max_w": 100.0,
        "num_steps": 6,
    })
    assert len(result["pump_power_w"]) == 6
    assert all(p > 0 for p in result["peak_signal_power_w"])
    srs = _effect(result, "srs")
    sbs = _effect(result, "sbs")
    assert srs["applicable"] is True and sbs["applicable"] is True
    assert len(srs["values"]) == 6 and len(sbs["values"]) == 6

    # Thresholds are geometry/wavelength-dependent, not power-dependent —
    # constant scalars the frontend can plot as flat reference lines against
    # peak_signal_power_w in native Watts.
    assert result["srs_threshold_w"] is not None and result["srs_threshold_w"] > 0
    assert result["sbs_threshold_w"] is not None and result["sbs_threshold_w"] > 0
    assert srs["values"][0] == pytest.approx(result["peak_signal_power_w"][0] / result["srs_threshold_w"])
