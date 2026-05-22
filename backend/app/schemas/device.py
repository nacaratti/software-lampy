from __future__ import annotations
from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


DeviceType = Literal["fiber_active", "fiber_passive", "fbg", "coupler_wdm", "pump_source"]
DeviceCategory = Literal["custom", "shelf"]


class DeviceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    device_type: DeviceType
    category: DeviceCategory = "custom"
    manufacturer: str = ""
    part_number: str = ""
    parameters: dict[str, Any] = {}


class DeviceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    parameters: Optional[dict[str, Any]] = None


class DeviceOut(BaseModel):
    id: str
    name: str
    description: str
    device_type: str
    category: str
    manufacturer: str
    part_number: str
    parameters: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
