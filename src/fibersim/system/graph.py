"""Typed circuit graph for laser-system simulation.

The graph mirrors what the frontend System Builder produces: nodes carry a
`kind` plus a free parameter dict (validated upstream by the API schemas), and
directed edges connect named ports. Light flows source -> output; laser
cavities are expressed as an FBG pair enclosing an active fiber on the chain.

Node kinds and ports:
    pump_source     out
    seed            out                          (a.k.a. seed_source)
    fiber_passive   in -> out
    fiber_active    in -> out
    fbg             in -> out (transmitted; reflection is cavity physics)
    coupler_wdm     in, pump -> out
    splice          in -> out
    power_combiner  in (N inputs) -> out          (sums multiple pump/signal lines)
    osa / power_meter / beam_profiler  in         (monitor taps, terminal)

Every terminal node is a measurement tap (osa/power_meter/beam_profiler); any
number of them can branch off the same node — they only read the signal, they
don't consume it — so there is no separate non-tap "output" sink kind.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

SOURCE_KINDS = {"pump_source", "seed"}
THROUGH_KINDS = {"fiber_passive", "fiber_active", "fbg", "coupler_wdm", "splice", "power_combiner"}
SINK_KINDS = {"osa", "power_meter", "beam_profiler"}
INSTRUMENT_KINDS = SINK_KINDS
ALL_KINDS = SOURCE_KINDS | THROUGH_KINDS | SINK_KINDS


class GraphValidationError(ValueError):
    """Raised when the assembled system cannot be simulated; carries all issues."""

    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


@dataclass
class SystemNode:
    id: str
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    label: str = ""

    def param(self, name: str, default: float | str | None = None):
        value = self.params.get(name, default)
        return default if value is None else value


@dataclass
class SystemEdge:
    id: str
    source: str
    target: str
    source_port: str = "out"
    target_port: str = "in"
    loss_db: float = 0.0  # optional splice/connector loss on the link


@dataclass
class CavitySegment:
    """An FBG pair enclosing part of the main chain — solved as a laser cavity."""
    left_fbg: SystemNode
    right_fbg: SystemNode
    inner_nodes: list[SystemNode]  # chain nodes strictly between the FBGs


class SystemGraph:
    def __init__(self, nodes: list[SystemNode], edges: list[SystemEdge]):
        self.nodes = {n.id: n for n in nodes}
        self.edges = list(edges)
        self._out_edges: dict[str, list[SystemEdge]] = {}
        self._in_edges: dict[str, list[SystemEdge]] = {}
        for e in self.edges:
            self._out_edges.setdefault(e.source, []).append(e)
            self._in_edges.setdefault(e.target, []).append(e)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def node(self, node_id: str) -> SystemNode:
        return self.nodes[node_id]

    def out_edges(self, node_id: str) -> list[SystemEdge]:
        return self._out_edges.get(node_id, [])

    def in_edges(self, node_id: str) -> list[SystemEdge]:
        return self._in_edges.get(node_id, [])

    def nodes_of_kind(self, *kinds: str) -> list[SystemNode]:
        return [n for n in self.nodes.values() if n.kind in kinds]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self) -> list[str]:
        """Returns a list of human-readable issues (empty = simulable)."""
        issues: list[str] = []

        if not self.nodes:
            return ["The system is empty — drop some components on the canvas."]

        for node in self.nodes.values():
            if node.kind not in ALL_KINDS:
                issues.append(f"Node '{node.label or node.id}': unknown kind '{node.kind}'.")

        for e in self.edges:
            if e.source not in self.nodes or e.target not in self.nodes:
                issues.append(f"Edge '{e.id}' references a missing node.")

        if issues:
            return issues

        # Port rules
        for node in self.nodes.values():
            label = node.label or node.id
            n_in = len(self.in_edges(node.id))
            n_out = len(self.out_edges(node.id))
            non_tap_out = [
                e for e in self.out_edges(node.id)
                if self.nodes[e.target].kind not in INSTRUMENT_KINDS
            ]

            if node.kind in SOURCE_KINDS:
                if n_in:
                    issues.append(f"'{label}' is a source and cannot have inputs.")
                if not n_out:
                    issues.append(f"'{label}' is not connected to anything.")
            elif node.kind in SINK_KINDS:
                if n_out:
                    issues.append(f"'{label}' is a terminal element and cannot have outputs.")
                if not n_in:
                    issues.append(f"'{label}' has no input connection.")
                if n_in > 1:
                    issues.append(f"'{label}' has multiple inputs; connect exactly one.")
            else:  # THROUGH_KINDS
                main_inputs = [e for e in self.in_edges(node.id) if e.target_port != "pump"]
                pump_inputs = [e for e in self.in_edges(node.id) if e.target_port == "pump"]
                if len(main_inputs) > 1 and node.kind != "power_combiner":
                    issues.append(f"'{label}' has {len(main_inputs)} main inputs; only one is allowed.")
                if pump_inputs and node.kind != "coupler_wdm":
                    issues.append(f"'{label}' cannot take a pump input (only WDM couplers can).")
                if len(non_tap_out) > 1:
                    issues.append(f"'{label}' splits into {len(non_tap_out)} outputs; splitting is not supported yet.")
                if not main_inputs and not pump_inputs and node.kind != "fbg":
                    # An FBG with no input is a valid cavity end-mirror (HR grating).
                    issues.append(f"'{label}' has no input connection.")

        for e in self.edges:
            src, dst = self.nodes[e.source], self.nodes[e.target]
            if dst.kind in SOURCE_KINDS:
                issues.append(f"Cannot connect into source '{dst.label or dst.id}'.")
            if src.kind in SINK_KINDS:
                issues.append(f"Cannot connect out of terminal '{src.label or src.id}'.")
            if e.target_port == "pump":
                upstream_ok = src.kind in {"pump_source", "coupler_wdm", "fiber_passive", "splice", "power_combiner"}
                if not upstream_ok:
                    issues.append(
                        f"Pump port of '{dst.label or dst.id}' must be fed by a pump source "
                        f"(directly or through passive routing), got '{src.kind}'."
                    )

        # Acyclic check (explicit cycles are not allowed; cavities use FBG pairs)
        if self._has_cycle():
            issues.append(
                "The connection graph contains a cycle. Laser cavities are modeled by "
                "placing two FBGs around the gain fiber, not by wiring a loop."
            )

        # Must have at least one pump/seed and something to observe
        if not self.nodes_of_kind(*SOURCE_KINDS):
            issues.append("Add at least one pump or seed source.")
        if not self.nodes_of_kind(*SINK_KINDS):
            issues.append("Add an instrument (OSA, power meter, or beam profiler) to observe results.")

        return issues

    def _has_cycle(self) -> bool:
        colors: dict[str, int] = {}

        def visit(nid: str) -> bool:
            colors[nid] = 1
            for e in self.out_edges(nid):
                state = colors.get(e.target, 0)
                if state == 1:
                    return True
                if state == 0 and visit(e.target):
                    return True
            colors[nid] = 2
            return False

        return any(colors.get(nid, 0) == 0 and visit(nid) for nid in self.nodes)

    # ------------------------------------------------------------------
    # Ordering & structure
    # ------------------------------------------------------------------
    def topological_order(self) -> list[SystemNode]:
        indeg = {nid: 0 for nid in self.nodes}
        for e in self.edges:
            indeg[e.target] += 1
        queue = sorted([nid for nid, d in indeg.items() if d == 0])
        order: list[SystemNode] = []
        while queue:
            nid = queue.pop(0)
            order.append(self.nodes[nid])
            for e in self.out_edges(nid):
                indeg[e.target] -= 1
                if indeg[e.target] == 0:
                    queue.append(e.target)
        if len(order) != len(self.nodes):
            raise GraphValidationError(["Graph contains a cycle; cannot order nodes."])
        return order

    def main_chain_successor(self, node_id: str) -> Optional[SystemNode]:
        """Next non-instrument node downstream on the main optical path."""
        for e in self.out_edges(node_id):
            target = self.nodes[e.target]
            if target.kind not in INSTRUMENT_KINDS:
                return target
        return None

    def detect_cavities(self) -> list[CavitySegment]:
        """Finds FBG -> ... -> FBG segments with at least one active fiber inside.

        Walks the main chain from each FBG; nested/overlapping cavities are not
        supported — the first enclosing pair wins and inner FBGs are treated as
        filters.
        """
        cavities: list[CavitySegment] = []
        consumed: set[str] = set()

        for fbg in self.nodes_of_kind("fbg"):
            if fbg.id in consumed:
                continue
            inner: list[SystemNode] = []
            current = self.main_chain_successor(fbg.id)
            while current is not None:
                if current.kind == "fbg":
                    if any(n.kind == "fiber_active" for n in inner):
                        cavities.append(CavitySegment(fbg, current, inner))
                        consumed.add(fbg.id)
                        consumed.add(current.id)
                    break
                inner.append(current)
                current = self.main_chain_successor(current.id)

        return cavities
