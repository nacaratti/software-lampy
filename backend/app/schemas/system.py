"""System Builder schemas: typed circuit graph + persistence models.

Node parameters are discriminated by node kind, giving per-device-type
validation (the Device Library's free-form JSON gap does not propagate into
simulations). Extra keys are tolerated so catalog metadata (fiber_type,
connector_type, ...) passes through untouched.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Per-kind parameter models
# ---------------------------------------------------------------------------


class _Params(BaseModel):
    model_config = {"extra": "allow"}


class PumpSourceParams(_Params):
    wavelength_nm: float = Field(976.0, gt=200.0, lt=20000.0)
    power_w: float = Field(0.5, ge=0.0, le=100000.0)
    linewidth_nm: float = Field(0.5, ge=0.0, le=100.0)


class SeedParams(_Params):
    wavelength_nm: float = Field(1064.0, gt=200.0, lt=20000.0)
    power_w: float = Field(0.01, ge=0.0, le=100000.0)
    linewidth_nm: float = Field(0.1, ge=0.0, le=100.0)


class ActiveFiberParams(_Params):
    ion: Literal["yb", "er", "tm"] = "yb"
    core_radius_um: float = Field(2.5, gt=0.0, le=500.0)
    clad_radius_um: float = Field(62.5, gt=0.0, le=2000.0)
    n_core: float = Field(1.46, ge=1.0, le=3.0)
    n_clad: float = Field(1.454, ge=1.0, le=3.0)
    N_total: float = Field(3e25, gt=0.0, le=1e28)
    tau_ms: float = Field(0.84, gt=0.0, le=100.0)
    # Overlap Γ is computed automatically from the guided-mode/dopant overlap
    # integral (fibersim.system.overlap) — no manual scalar to guess anymore.
    # Set these only to force a specific value (e.g. for regression testing
    # against a known reference); leave unset for the physically-derived one.
    gamma_pump: Optional[float] = Field(None, gt=0.0, le=1.0)
    gamma_signal: Optional[float] = Field(None, gt=0.0, le=1.0)
    background_loss_db_m: float = Field(0.005, ge=0.0, le=10.0)
    length_m: float = Field(2.0, gt=0.0, le=1000.0)
    # Optional double-clad geometry: when both are set, the fiber is treated
    # as cladding-pumped (Γ_pump ≈ A_core / A_inner_cladding) rather than
    # core-pumped. clad_radius_um above becomes the OUTER cladding in that case.
    inner_cladding_radius_um: Optional[float] = Field(None, gt=0.0, le=2000.0)


class PassiveFiberParams(_Params):
    core_radius_um: float = Field(4.1, gt=0.0, le=500.0)
    clad_radius_um: float = Field(62.5, gt=0.0, le=2000.0)
    n_core: float = Field(1.468, ge=1.0, le=3.0)
    n_clad: float = Field(1.463, ge=1.0, le=3.0)
    attenuation_db_km: float = Field(0.35, ge=0.0, le=10000.0)
    length_m: float = Field(1.0, gt=0.0, le=100000.0)


class FBGParams(_Params):
    central_wavelength_nm: float = Field(1064.0, gt=200.0, lt=20000.0)
    reflectivity: float = Field(0.99, ge=0.0, le=1.0)
    bandwidth_nm: float = Field(0.3, gt=0.0, le=100.0)
    length_mm: float = Field(10.0, gt=0.0, le=1000.0)
    n_eff: float = Field(1.45, ge=1.0, le=3.0)


class WdmParams(_Params):
    insertion_loss_port1_db: float = Field(0.3, ge=0.0, le=30.0)
    insertion_loss_port2_db: float = Field(0.4, ge=0.0, le=30.0)
    isolation_db: float = Field(20.0, ge=0.0, le=100.0)


class SpliceParams(_Params):
    loss_db: float = Field(0.05, ge=0.0, le=30.0)


class PowerCombinerParams(_Params):
    """N x 1 fused-fiber combiner: sums whatever arrives on its (multiple)
    input edges, unlike coupler_wdm which is wavelength-selective."""
    insertion_loss_db: float = Field(0.5, ge=0.0, le=30.0)


class MonitorParams(_Params):
    """Power-meter nodes — display settings live on the frontend."""


class OsaParams(_Params):
    rbw_nm: float = Field(0.1, gt=0.0, le=50.0, description="Resolution bandwidth")
    span_nm: Optional[float] = Field(None, gt=0.0, le=5000.0)
    center_nm: Optional[float] = Field(None, gt=200.0, lt=20000.0)


class BeamProfilerParams(_Params):
    grid_n: int = Field(128, ge=32, le=512)
    num_z: int = Field(21, ge=5, le=101)
    z_span_factor: float = Field(6.0, gt=0.5, le=50.0)


# ---------------------------------------------------------------------------
# Node union discriminated by kind
# ---------------------------------------------------------------------------


class _NodeBase(BaseModel):
    id: str = Field(..., min_length=1, max_length=100)
    label: str = ""


class PumpSourceNode(_NodeBase):
    kind: Literal["pump_source"]
    params: PumpSourceParams = PumpSourceParams()


class SeedNode(_NodeBase):
    kind: Literal["seed"]
    params: SeedParams = SeedParams()


class ActiveFiberNode(_NodeBase):
    kind: Literal["fiber_active"]
    params: ActiveFiberParams = ActiveFiberParams()


class PassiveFiberNode(_NodeBase):
    kind: Literal["fiber_passive"]
    params: PassiveFiberParams = PassiveFiberParams()


class FBGNode(_NodeBase):
    kind: Literal["fbg"]
    params: FBGParams = FBGParams()


class WdmNode(_NodeBase):
    kind: Literal["coupler_wdm"]
    params: WdmParams = WdmParams()


class SpliceNode(_NodeBase):
    kind: Literal["splice"]
    params: SpliceParams = SpliceParams()


class PowerCombinerNode(_NodeBase):
    kind: Literal["power_combiner"]
    params: PowerCombinerParams = PowerCombinerParams()


class OsaNode(_NodeBase):
    kind: Literal["osa"]
    params: OsaParams = OsaParams()


class PowerMeterNode(_NodeBase):
    kind: Literal["power_meter"]
    params: MonitorParams = MonitorParams()


class BeamProfilerNode(_NodeBase):
    kind: Literal["beam_profiler"]
    params: BeamProfilerParams = BeamProfilerParams()


SystemNodeConfig = Annotated[
    Union[
        PumpSourceNode,
        SeedNode,
        ActiveFiberNode,
        PassiveFiberNode,
        FBGNode,
        WdmNode,
        SpliceNode,
        PowerCombinerNode,
        OsaNode,
        PowerMeterNode,
        BeamProfilerNode,
    ],
    Field(discriminator="kind"),
]


class SystemEdgeConfig(BaseModel):
    id: str = Field(..., min_length=1, max_length=100)
    source: str
    target: str
    source_port: str = "out"
    target_port: str = "in"
    loss_db: float = Field(0.0, ge=0.0, le=30.0)


# ---------------------------------------------------------------------------
# Simulation request/response
# ---------------------------------------------------------------------------


class SystemSimulateRequest(BaseModel):
    nodes: list[SystemNodeConfig] = Field(..., max_length=200)
    edges: list[SystemEdgeConfig] = Field(..., max_length=400)


class SystemValidateResponse(BaseModel):
    valid: bool
    issues: list[str]


class SystemSimulationResult(BaseModel):
    """Engine output — loosely typed JSON payload streamed via the job WS."""
    edges: dict[str, Any]
    nodes: dict[str, Any]
    outputs: dict[str, Any]
    warnings: list[str]


# ---------------------------------------------------------------------------
# Saved systems (persistence)
# ---------------------------------------------------------------------------


class SystemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    graph: dict[str, Any] = Field(
        default_factory=dict,
        description="Frontend document (React Flow nodes with positions + edges).",
    )


class SystemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    graph: Optional[dict[str, Any]] = None


class SystemOut(BaseModel):
    id: str
    name: str
    description: str
    graph: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemSummary(BaseModel):
    id: str
    name: str
    description: str
    node_count: int
    created_at: datetime
    updated_at: datetime
