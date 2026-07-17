"""System-level simulation: assemble fiber-laser schematics and chain solvers.

Modules:
    signal  — OpticalSignal: discretized spectrum flowing along graph edges.
    graph   — SystemGraph: typed nodes/edges, validation, ordering, cavity detection.
    engine  — simulate_system: walks the graph mapping each node to a solver.
"""
from fibersim.system.signal import OpticalSignal, SpectralChannel
from fibersim.system.graph import SystemGraph, SystemNode, SystemEdge, GraphValidationError
from fibersim.system.engine import simulate_system, SystemResult
from fibersim.system.beam import analyze_beam, BeamProfilerResult
from fibersim.system.instruments import osa_trace, OsaTrace, power_meter_reading, PowerMeterReading

__all__ = [
    "OpticalSignal",
    "SpectralChannel",
    "SystemGraph",
    "SystemNode",
    "SystemEdge",
    "GraphValidationError",
    "simulate_system",
    "SystemResult",
    "analyze_beam",
    "BeamProfilerResult",
    "osa_trace",
    "OsaTrace",
    "power_meter_reading",
    "PowerMeterReading",
]
