"""Adapter: SystemSimulateRequest (API schema) -> fibersim.system engine."""
from __future__ import annotations

from typing import Any, Callable, Optional

import numpy as np

from fibersim.system import SystemEdge, SystemGraph, SystemNode, simulate_system
from fibersim.system.graph import GraphValidationError

from backend.app.schemas.system import SystemSimulateRequest, SystemSimulationResult
from backend.app.services.encoders import encode_array


def _sanitize(obj: Any) -> Any:
    """Recursively encodes numpy arrays/scalars into JSON-safe values.

    The physics engine (`fibersim.system`) returns plain numpy where that's
    the natural type (e.g. the beam profiler's image stack); this walks the
    result tree once so the whole payload survives Pydantic's `mode="json"`
    dump the job manager applies before broadcasting it over the WebSocket.
    """
    if isinstance(obj, np.ndarray):
        return encode_array(obj).model_dump()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _build_graph(req: SystemSimulateRequest) -> SystemGraph:
    nodes = [
        SystemNode(id=n.id, kind=n.kind, params=n.params.model_dump(), label=n.label or n.id)
        for n in req.nodes
    ]
    edges = [
        SystemEdge(
            id=e.id,
            source=e.source,
            target=e.target,
            source_port=e.source_port,
            target_port=e.target_port,
            loss_db=e.loss_db,
        )
        for e in req.edges
    ]
    return SystemGraph(nodes, edges)


def validate_system(req: SystemSimulateRequest) -> list[str]:
    return _build_graph(req).validate()


def run_system_simulation(
    req: SystemSimulateRequest,
    progress_callback: Optional[Callable[[float], Optional[bool]]] = None,
) -> SystemSimulationResult:
    graph = _build_graph(req)
    try:
        result = simulate_system(graph, progress_callback=progress_callback)
    except GraphValidationError as exc:
        # Surfaced as a clean 422 by backend.app.errors.run_solver
        raise ValueError("; ".join(exc.issues)) from exc

    return SystemSimulationResult(
        edges=_sanitize(result.edges),
        nodes=_sanitize(result.nodes),
        outputs=_sanitize(result.outputs),
        warnings=result.warnings,
    )
