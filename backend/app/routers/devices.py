from __future__ import annotations
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.device import Device
from backend.app.schemas.device import DeviceCreate, DeviceUpdate, DeviceOut

router = APIRouter(prefix="/api/devices", tags=["devices"])


# ---------------------------------------------------------------------------
# Shelf catalogue — pre-defined commercial devices
# ---------------------------------------------------------------------------

_SHELF: list[dict] = [
    {
        "name": "Nufern SM-YSF-HI",
        "description": "Single-mode Yb-doped fiber, high-NA, widely used in fiber lasers",
        "device_type": "fiber_active",
        "category": "shelf",
        "manufacturer": "Nufern",
        "part_number": "SM-YSF-HI",
        "parameters": {
            "core_radius_um": 1.9,
            "clad_radius_um": 62.5,
            "coating_radius_um": 87.5,
            "NA": 0.12,
            "n_core": 1.4607,
            "n_clad": 1.4537,
            "cutoff_wavelength_nm": 900,
            "background_loss_db_m": 0.005,
            "peak_absorption_dB_m_976nm": 250,
            "tau_ms": 0.84,
            "gamma_pump": 0.85,
            "gamma_signal": 0.82,
            "N_total": 3.3e25,
        },
    },
    {
        "name": "Nufern LMA-YDF-10/125-M",
        "description": "Large-mode-area Yb-doped fiber, 10/125 µm",
        "device_type": "fiber_active",
        "category": "shelf",
        "manufacturer": "Nufern",
        "part_number": "LMA-YDF-10/125-M",
        "parameters": {
            "core_radius_um": 5.0,
            "clad_radius_um": 62.5,
            "coating_radius_um": 87.5,
            "NA": 0.075,
            "n_core": 1.4575,
            "n_clad": 1.4556,
            "cutoff_wavelength_nm": 1200,
            "background_loss_db_m": 0.005,
            "peak_absorption_dB_m_976nm": 3.7,
            "tau_ms": 0.84,
            "gamma_pump": 0.18,
            "gamma_signal": 0.72,
            "N_total": 1.5e25,
        },
    },
    {
        "name": "Corning HI 1060",
        "description": "Single-mode fiber optimized for 980–1060 nm, low loss",
        "device_type": "fiber_passive",
        "category": "shelf",
        "manufacturer": "Corning",
        "part_number": "HI 1060",
        "parameters": {
            "core_radius_um": 2.75,
            "clad_radius_um": 62.5,
            "coating_radius_um": 87.5,
            "NA": 0.14,
            "n_core": 1.4625,
            "n_clad": 1.4537,
            "MFD_um": 6.2,
            "cutoff_wavelength_nm": 920,
            "attenuation_db_km_1060nm": 1.0,
        },
    },
    {
        "name": "Corning SMF-28e+",
        "description": "Standard telecom single-mode fiber, 8.2/125 µm, low loss at 1310/1550 nm",
        "device_type": "fiber_passive",
        "category": "shelf",
        "manufacturer": "Corning",
        "part_number": "SMF-28e+",
        "parameters": {
            "core_radius_um": 4.1,
            "clad_radius_um": 62.5,
            "coating_radius_um": 87.5,
            "NA": 0.14,
            "n_core": 1.4682,
            "n_clad": 1.4629,
            "MFD_um": 9.2,
            "cutoff_wavelength_nm": 1260,
            "attenuation_db_km_1310nm": 0.33,
            "attenuation_db_km_1550nm": 0.18,
        },
    },
    {
        "name": "976 nm Pump Diode (standard)",
        "description": "Generic 976 nm single-emitter pump diode, fiber-coupled, 500 mW",
        "device_type": "pump_source",
        "category": "shelf",
        "manufacturer": "Generic",
        "part_number": "N/A",
        "parameters": {
            "wavelength_nm": 976.0,
            "power_w": 0.5,
            "linewidth_nm": 0.5,
            "fiber_type": "HI1060",
            "connector_type": "FC/APC",
            "polarization": "unpolarized",
        },
    },
    {
        "name": "915 nm Pump Diode (standard)",
        "description": "Generic 915 nm pump diode, broader absorption, 1 W fiber-coupled",
        "device_type": "pump_source",
        "category": "shelf",
        "manufacturer": "Generic",
        "part_number": "N/A",
        "parameters": {
            "wavelength_nm": 915.0,
            "power_w": 1.0,
            "linewidth_nm": 3.0,
            "fiber_type": "HI1060",
            "connector_type": "FC/APC",
            "polarization": "unpolarized",
        },
    },
    {
        "name": "WDM 976/1064 nm",
        "description": "Wavelength-division multiplexer for 976 nm pump and 1064 nm signal, standard SMF",
        "device_type": "coupler_wdm",
        "category": "shelf",
        "manufacturer": "Generic",
        "part_number": "WDM-976/1064",
        "parameters": {
            "port_count": 3,
            "wavelength_1_nm": 976.0,
            "wavelength_2_nm": 1064.0,
            "insertion_loss_port1_db": 0.3,
            "insertion_loss_port2_db": 0.4,
            "isolation_db": 20.0,
            "fiber_type": "HI1060",
        },
    },
    {
        "name": "WDM 976/1550 nm",
        "description": "Wavelength-division multiplexer for 976 nm pump and C-band signal",
        "device_type": "coupler_wdm",
        "category": "shelf",
        "manufacturer": "Generic",
        "part_number": "WDM-976/1550",
        "parameters": {
            "port_count": 3,
            "wavelength_1_nm": 976.0,
            "wavelength_2_nm": 1550.0,
            "insertion_loss_port1_db": 0.3,
            "insertion_loss_port2_db": 0.3,
            "isolation_db": 25.0,
            "fiber_type": "SMF-28",
        },
    },
    {
        "name": "FBG HR 1064 nm",
        "description": "High-reflectivity FBG at 1064 nm, uniform, for Yb fiber laser cavity",
        "device_type": "fbg",
        "category": "shelf",
        "manufacturer": "Generic",
        "part_number": "FBG-HR-1064",
        "parameters": {
            "grating_type": "uniform",
            "central_wavelength_nm": 1064.0,
            "reflectivity": 0.99,
            "bandwidth_nm": 0.3,
            "period_nm": 366.0,
            "length_mm": 10.0,
            "dn": 5e-4,
            "n_eff": 1.453,
        },
    },
    {
        "name": "FBG OC 1064 nm (10%)",
        "description": "Output coupler FBG at 1064 nm, ~10% reflectivity, for Yb fiber laser",
        "device_type": "fbg",
        "category": "shelf",
        "manufacturer": "Generic",
        "part_number": "FBG-OC-1064",
        "parameters": {
            "grating_type": "uniform",
            "central_wavelength_nm": 1064.0,
            "reflectivity": 0.10,
            "bandwidth_nm": 0.15,
            "period_nm": 366.0,
            "length_mm": 5.0,
            "dn": 1e-4,
            "n_eff": 1.453,
        },
    },
]


def _seed_shelf(db: Session) -> None:
    existing = db.query(Device).filter(Device.category == "shelf").count()
    if existing > 0:
        return
    for item in _SHELF:
        data = dict(item)
        params = data.pop("parameters")
        device = Device(**data, parameters=json.dumps(params))
        db.add(device)
    db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_out(d: Device) -> DeviceOut:
    params = json.loads(d.parameters) if isinstance(d.parameters, str) else d.parameters
    return DeviceOut(
        id=d.id,
        name=d.name,
        description=d.description,
        device_type=d.device_type,
        category=d.category,
        manufacturer=d.manufacturer,
        part_number=d.part_number,
        parameters=params,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[DeviceOut])
def list_devices(
    device_type: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    _seed_shelf(db)
    q = db.query(Device)
    if device_type:
        q = q.filter(Device.device_type == device_type)
    if category:
        q = q.filter(Device.category == category)
    return [_row_to_out(d) for d in q.order_by(Device.category, Device.name).all()]


@router.post("", response_model=DeviceOut, status_code=201)
def create_device(body: DeviceCreate, db: Session = Depends(get_db)):
    device = Device(
        name=body.name,
        description=body.description,
        device_type=body.device_type,
        category="custom",
        manufacturer=body.manufacturer,
        part_number=body.part_number,
        parameters=json.dumps(body.parameters),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return _row_to_out(device)


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(device_id: str, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return _row_to_out(device)


@router.put("/{device_id}", response_model=DeviceOut)
def update_device(device_id: str, body: DeviceUpdate, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.category == "shelf":
        raise HTTPException(status_code=403, detail="Shelf devices cannot be edited")
    if body.name is not None:
        device.name = body.name
    if body.description is not None:
        device.description = body.description
    if body.manufacturer is not None:
        device.manufacturer = body.manufacturer
    if body.part_number is not None:
        device.part_number = body.part_number
    if body.parameters is not None:
        device.parameters = json.dumps(body.parameters)
    db.commit()
    db.refresh(device)
    return _row_to_out(device)


@router.delete("/{device_id}", status_code=204)
def delete_device(device_id: str, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.category == "shelf":
        raise HTTPException(status_code=403, detail="Shelf devices cannot be deleted")
    db.delete(device)
    db.commit()
