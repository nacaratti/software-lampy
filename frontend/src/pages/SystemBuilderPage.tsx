import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
  type Node,
  type Edge,
  type Connection,
  type ReactFlowInstance,
  type OnBeforeDelete,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { toast } from "sonner";
import {
  Trash2, Save, FolderOpen, Play, Package, X, ChevronDown, ChevronRight,
  Loader2, RotateCcw, Copy, Pencil, FlaskConical, Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { PageHeader } from "@/components/layout/PageHeader";
import { OsaPanel } from "@/components/instruments/OsaPanel";
import { PowerMeterPanel } from "@/components/instruments/PowerMeterPanel";
import { BeamProfilerPanel } from "@/components/instruments/BeamProfilerPanel";
import { TypedParamEditor } from "@/components/devices/TypedParamEditor";
import type { ParamFormHandle } from "@/components/devices/ParamForm";
import { api } from "@/lib/api";
import { useJobSocket } from "@/lib/ws";
import type { Device, DeviceType } from "@/types/device";
import { deviceTypeLabels } from "@/types/device";
import { SystemNodeCard } from "@/components/system/SystemNodeCard";
import { SignalEdge } from "@/components/system/SignalEdge";
import { PaletteItem } from "@/components/system/PaletteItem";
import {
  INSTRUMENT_KINDS, PUMP_EDGE_COLOR, SOURCE_KINDS, kindStyle,
  type SystemNode, type SystemNodeData,
} from "@/components/system/nodeStyles";
import type {
  SystemNodeKind,
  SystemOutputSummary,
  SystemSimulateRequest,
  SystemSimulationResult,
  SystemSummary,
} from "@/types/system";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

const STORAGE_KEY = "lampy-system-v1";

function formatWatts(w: number): string {
  if (!Number.isFinite(w)) return "—";
  if (w >= 1) return `${w.toFixed(2)} W`;
  if (w >= 1e-3) return `${(w * 1e3).toFixed(1)} mW`;
  return `${(w * 1e6).toFixed(1)} µW`;
}

// Advanced-physics diagnostics that fiber_active nodes may report (Fase 4a/4b):
// SRS/SBS thresholds, photodarkening, Tm/Er ESA-upconversion, TMI risk. Only
// rendered when actually present in the last simulation's node result.
type DiagnosticRow = { label: string; value: string; warn?: boolean };

function buildFiberDiagnostics(nr: Record<string, unknown> | undefined): DiagnosticRow[] {
  if (!nr) return [];
  const rows: DiagnosticRow[] = [];
  const num = (k: string): number | undefined => (typeof nr[k] === "number" ? (nr[k] as number) : undefined);

  const aEff = num("effective_area_um2");
  if (aEff !== undefined) rows.push({ label: "Effective area", value: `${aEff.toFixed(1)} µm²` });

  const srs = num("srs_threshold_w");
  const sbs = num("sbs_threshold_w");
  const peakSignal = num("peak_signal_power_w");
  if (srs !== undefined) rows.push({ label: "SRS threshold", value: formatWatts(srs) });
  if (sbs !== undefined) {
    const warn = peakSignal !== undefined && peakSignal > 0.5 * sbs;
    rows.push({ label: "SBS threshold", value: formatWatts(sbs), warn });
  }

  const pdPeak = num("photodarkening_peak_db_m");
  const pdExtra = num("photodarkening_extra_loss_db_saturated");
  if (pdPeak !== undefined && pdExtra !== undefined) {
    rows.push({
      label: "Photodarkening (saturated)",
      value: `${pdPeak.toFixed(2)} dB/m peak, ${pdExtra.toFixed(2)} dB total`,
      warn: pdExtra > 1.0,
    });
  }

  const tmYield = num("tm_cross_relaxation_yield");
  if (tmYield !== undefined) rows.push({ label: "Tm cross-relaxation yield", value: `${tmYield.toFixed(2)}×` });

  const erUpconv = num("er_upconversion_coeff_m3_s");
  if (erUpconv !== undefined) rows.push({ label: "Er upconversion coeff.", value: `${erUpconv.toExponential(1)} m³/s` });

  const tmiRisk = num("tmi_risk_fraction");
  if (tmiRisk !== undefined) {
    rows.push({ label: "TMI risk fraction", value: tmiRisk.toFixed(2), warn: tmiRisk > 0.5 });
  }

  return rows;
}

function DiagnosticsSection({ rows }: { rows: DiagnosticRow[] }) {
  if (rows.length === 0) return null;
  return (
    <div>
      <Label className="text-[10px] uppercase tracking-wider text-muted-foreground">Diagnostics</Label>
      <div className="mt-1 space-y-1">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-2 text-[11px]">
            <span className="text-muted-foreground">{row.label}</span>
            <span className={`font-mono ${row.warn ? "text-amber-400" : ""}`}>{row.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Nonlinear-effects summary across every fiber_active node in the run —
 * surfaced in Simulation Results directly, so the reader doesn't have to
 * know to click each fiber node individually to find SRS/SBS/photodarkening/
 * ESA/TMI diagnostics. Fields that a given fiber doesn't produce (e.g. TMI
 * on a single-mode fiber, ESA on a Yb fiber) are simply absent from its
 * card, same as in the per-node Diagnostics panel. */
function NonlinearEffectsPanel({
  result,
  nodesById,
}: {
  result: SystemSimulationResult;
  nodesById: Map<string, SystemNode>;
}) {
  const fiberEntries = Object.entries(result.nodes).filter(
    ([, nr]) => (nr as Record<string, unknown>).kind === "fiber_active",
  );

  if (fiberEntries.length === 0) {
    return <p className="text-[11px] text-muted-foreground">No active fiber nodes in this simulation.</p>;
  }

  return (
    <div className="space-y-3">
      {fiberEntries.map(([nodeId, nr]) => {
        const rows = buildFiberDiagnostics(nr as Record<string, unknown>);
        const label = nodesById.get(nodeId)?.data.label ?? nodeId;
        return (
          <div key={nodeId} className="rounded-md border border-border bg-background/50 px-3 py-2.5">
            <div className="flex items-center gap-1.5 mb-1.5">
              <FlaskConical className="h-3 w-3 text-emerald-400" />
              <span className="text-xs font-medium">{label}</span>
            </div>
            {rows.length > 0 ? (
              <DiagnosticsSection rows={rows} />
            ) : (
              <p className="text-[11px] text-muted-foreground">
                No nonlinear-effect diagnostics for this fiber (no guided signal, or no data yet).
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

const SINK_KINDS = INSTRUMENT_KINDS;

const nodeTypes = {
  fiber_active: SystemNodeCard,
  fiber_passive: SystemNodeCard,
  fbg: SystemNodeCard,
  coupler_wdm: SystemNodeCard,
  pump_source: SystemNodeCard,
  seed: SystemNodeCard,
  power_combiner: SystemNodeCard,
  osa: SystemNodeCard,
  power_meter: SystemNodeCard,
  beam_profiler: SystemNodeCard,
};

// Overriding the built-in "default" type means every edge — including ones
// in systems saved before this existed — gets the removable SignalEdge.
const edgeTypes = { default: SignalEdge };

// ---------------------------------------------------------------------------
// Palette
// ---------------------------------------------------------------------------

type PaletteBlock = { kind: string; label: string; sublabel: string; params: Record<string, unknown> };

const GENERIC_BLOCKS: PaletteBlock[] = [
  { kind: "seed",           label: "Seed laser",        sublabel: "1064 nm · 1 mW",  params: { wavelength_nm: 1064, power_w: 1e-3 } },
  { kind: "pump_source",    label: "Pump diode",        sublabel: "976 nm · 0.5 W",  params: { wavelength_nm: 976, power_w: 0.5 } },
  { kind: "coupler_wdm",    label: "WDM / pump combiner", sublabel: "signal + pump port", params: { insertion_loss_port1_db: 0.3, insertion_loss_port2_db: 0.4 } },
  { kind: "power_combiner", label: "Power combiner",    sublabel: "N×1 · 0.5 dB",    params: { insertion_loss_db: 0.5 } },
];

const INSTRUMENT_BLOCKS: PaletteBlock[] = [
  { kind: "osa",           label: "Spectrum analyzer", sublabel: "OSA · 0.1 nm RBW", params: { rbw_nm: 0.1 } },
  { kind: "power_meter",   label: "Power meter",       sublabel: "total + per band",  params: {} },
  { kind: "beam_profiler", label: "Beam profiler",     sublabel: "CCD · M² (ISO 11146)", params: { grid_n: 128, num_z: 21 } },
];

type DragStart = (e: React.DragEvent, kind: string, label: string, deviceId?: string, params?: Record<string, unknown>) => void;

function DevicePaletteSection({
  title,
  devices,
  onDragStart,
  forceOpen,
}: {
  title: string;
  devices: Device[];
  onDragStart: DragStart;
  forceOpen: boolean;
}) {
  const [open, setOpen] = useState(true);
  if (devices.length === 0) return null;
  const expanded = open || forceOpen;
  return (
    <div>
      <button
        className="flex items-center gap-1.5 w-full text-[10px] uppercase tracking-wider text-muted-foreground font-medium py-1 hover:text-foreground transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {title}
        <span className="ml-auto font-mono normal-case tracking-normal">{devices.length}</span>
      </button>
      {expanded && (
        <div className="space-y-1 mt-1 mb-3">
          {devices.map((d) => (
            <PaletteItem
              key={d.id}
              kind={d.device_type}
              label={d.name}
              sublabel={d.manufacturer || undefined}
              onDragStart={(e) => onDragStart(e, d.device_type, d.name, d.id, d.parameters)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Node detail panel
// ---------------------------------------------------------------------------

function NodeDetailPanel({
  node,
  nodeResult,
  onUpdate,
  onDelete,
  onClose,
}: {
  node: SystemNode;
  nodeResult?: Record<string, unknown>;
  onUpdate: (id: string, data: Partial<SystemNodeData>) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}) {
  const [label, setLabel] = useState(node.data.label);
  const paramRef = useRef<ParamFormHandle>(null);
  const [jsonParams, setJsonParams] = useState(node.data.params);

  useEffect(() => {
    setLabel(node.data.label);
    setJsonParams(node.data.params);
  }, [node.id, node.data.label, node.data.params]);

  async function handleApply() {
    const params = await paramRef.current?.getValues();
    if (!params) { toast.error("Fix the highlighted parameters before applying"); return; }
    onUpdate(node.id, { label, params });
    toast.success("Node updated");
  }

  const style = kindStyle(node.data.nodeKind);
  const Icon = style.icon;

  return (
    <div className="w-80 shrink-0 border-l border-border bg-card flex flex-col h-full z-20 relative">
      <div className={`h-[3px] w-full ${style.bar}`} />
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${style.chip}`}>
            <Icon className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium truncate">{node.data.label}</div>
            <div className="text-[11px] text-muted-foreground">{style.label}</div>
          </div>
        </div>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose} aria-label="Close node details">
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
      <ScrollArea className="flex-1 px-4 py-3">
        <div className="space-y-4">
          {node.data.deviceName && (
            <div>
              <Label className="text-[10px] uppercase tracking-wider text-muted-foreground">Device</Label>
              <p className="text-xs mt-0.5">{node.data.deviceName}</p>
            </div>
          )}
          {node.data.resultSummary && (
            <div>
              <Label className="text-[10px] uppercase tracking-wider text-muted-foreground">Last simulation</Label>
              <p className="text-xs mt-0.5 font-mono text-primary">{node.data.resultSummary}</p>
            </div>
          )}
          {node.data.nodeKind === "fiber_active" && (
            <DiagnosticsSection rows={buildFiberDiagnostics(nodeResult)} />
          )}
          <div>
            <Label className="text-xs">Label</Label>
            <Input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="mt-1 h-7 text-xs"
            />
          </div>
          <div>
            <Label className="text-xs mb-1.5 block">Parameters</Label>
            <TypedParamEditor
              ref={paramRef}
              kind={node.data.nodeKind}
              values={jsonParams}
              onJsonChange={setJsonParams}
            />
          </div>
          <Button size="sm" className="w-full" onClick={handleApply}>
            Apply
          </Button>
          <Separator />
          <Button
            size="sm"
            variant="destructive"
            className="w-full"
            onClick={() => onDelete(node.id)}
          >
            <Trash2 className="h-3.5 w-3.5 mr-1.5" />Remove node
          </Button>
        </div>
      </ScrollArea>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Results panel
// ---------------------------------------------------------------------------

function InstrumentTabBody({ out }: { out: SystemOutputSummary }) {
  if (out.kind === "osa" && out.osa) return <OsaPanel trace={out.osa} />;
  if (out.kind === "power_meter" && out.power_meter) return <PowerMeterPanel reading={out.power_meter} />;
  if (out.kind === "beam_profiler" && out.beam) return <BeamProfilerPanel beam={out.beam} />;

  // Fallback for an instrument tap missing its specific result — e.g. a beam
  // profiler with no upstream fiber (see the warnings list for why).
  return (
    <div className="rounded-md border border-border bg-background/50 px-3 py-2.5 max-w-xs">
      <p className="text-sm font-mono font-medium">{formatWatts(out.total_power_w)}</p>
      <div className="mt-1 space-y-0.5 text-[11px] text-muted-foreground">
        {out.signal_power_w > 0 && <div>signal: {formatWatts(out.signal_power_w)}</div>}
        {out.pump_power_w > 0 && <div>pump: {formatWatts(out.pump_power_w)}</div>}
        {out.ase_power_w > 0 && <div>ASE: {formatWatts(out.ase_power_w)}</div>}
      </div>
    </div>
  );
}

const NONLINEAR_TAB_ID = "__nonlinear_effects__";

function ResultsPanel({
  result,
  nodesById,
  onClose,
}: {
  result: SystemSimulationResult;
  nodesById: Map<string, SystemNode>;
  onClose: () => void;
}) {
  const outputEntries = Object.entries(result.outputs);
  const hasFiberActive = Object.values(result.nodes).some(
    (nr) => (nr as Record<string, unknown>).kind === "fiber_active",
  );
  const [active, setActive] = useState(outputEntries[0]?.[0] ?? (hasFiberActive ? NONLINEAR_TAB_ID : undefined));

  return (
    <div className="absolute bottom-0 left-0 right-0 z-10 max-h-[420px] border-t border-border bg-card/95 backdrop-blur-md shadow-xl flex flex-col">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Simulation Results
        </span>
        <div className="flex items-center gap-2">
          {result.warnings.length > 0 && (
            <Badge variant="outline" className="text-amber-400 border-amber-500/50">
              {result.warnings.length} warning{result.warnings.length > 1 ? "s" : ""}
            </Badge>
          )}
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose} aria-label="Close simulation results">
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      <ScrollArea className="flex-1 px-4 py-3">
        <div className="space-y-3">
          {result.warnings.length > 0 && (
            <div className="space-y-1">
              {result.warnings.map((w, i) => (
                <p key={i} className="text-[11px] text-amber-400/90">⚠ {w}</p>
              ))}
            </div>
          )}
          {outputEntries.length > 0 || hasFiberActive ? (
            <Tabs value={active} onValueChange={setActive}>
              <TabsList className="flex-wrap h-auto">
                {hasFiberActive && (
                  <TabsTrigger value={NONLINEAR_TAB_ID} className="gap-1.5">
                    <FlaskConical className="h-3 w-3 text-emerald-400" />
                    Nonlinear effects
                  </TabsTrigger>
                )}
                {outputEntries.map(([nodeId, out]) => {
                  const Icon = kindStyle(out.kind).icon;
                  return (
                    <TabsTrigger key={nodeId} value={nodeId} className="gap-1.5">
                      <Icon className="h-3 w-3 text-cyan-600 dark:text-cyan-400" />
                      {nodesById.get(nodeId)?.data.label ?? nodeId}
                    </TabsTrigger>
                  );
                })}
              </TabsList>
              {hasFiberActive && (
                <TabsContent value={NONLINEAR_TAB_ID} className="mt-3">
                  <NonlinearEffectsPanel result={result} nodesById={nodesById} />
                </TabsContent>
              )}
              {outputEntries.map(([nodeId, out]) => (
                <TabsContent key={nodeId} value={nodeId} className="mt-3">
                  <InstrumentTabBody out={out} />
                </TabsContent>
              ))}
            </Tabs>
          ) : (
            <p className="text-[11px] text-muted-foreground">No output/instrument nodes to report.</p>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Projects dialog
// ---------------------------------------------------------------------------

function ProjectsDialog({
  open,
  onClose,
  onLoad,
}: {
  open: boolean;
  onClose: () => void;
  onLoad: (id: string) => void;
}) {
  const [projects, setProjects] = useState<SystemSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(() => {
    setLoading(true);
    api.listSystems().then(setProjects).catch(() => toast.error("Failed to load saved systems")).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (open) refresh();
  }, [open, refresh]);

  async function handleRename(s: SystemSummary) {
    const name = window.prompt("Rename system", s.name);
    if (!name || name === s.name) return;
    try {
      await api.updateSystem(s.id, { name });
      setProjects((prev) => prev.map((p) => (p.id === s.id ? { ...p, name } : p)));
    } catch {
      toast.error("Failed to rename system");
    }
  }

  async function handleDuplicate(s: SystemSummary) {
    try {
      await api.duplicateSystem(s.id);
      refresh();
      toast.success("System duplicated");
    } catch {
      toast.error("Failed to duplicate system");
    }
  }

  async function handleDelete(s: SystemSummary) {
    if (!window.confirm(`Delete "${s.name}"? This cannot be undone.`)) return;
    try {
      await api.deleteSystem(s.id);
      setProjects((prev) => prev.filter((p) => p.id !== s.id));
      toast.success("System deleted");
    } catch {
      toast.error("Failed to delete system");
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Saved systems</DialogTitle>
          <DialogDescription>Open a saved laser schematic, or manage your projects.</DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : projects.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4">
            No saved systems yet. Build something on the canvas and hit Save.
          </p>
        ) : (
          <div className="space-y-1.5">
            {projects.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2 hover:bg-accent/30 transition-colors"
              >
                <button className="min-w-0 flex-1 text-left" onClick={() => onLoad(p.id)}>
                  <p className="text-sm font-medium truncate">{p.name}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {p.node_count} component{p.node_count !== 1 ? "s" : ""} · updated{" "}
                    {new Date(p.updated_at).toLocaleString()}
                  </p>
                </button>
                <div className="flex items-center gap-1 shrink-0">
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleRename(p)} title="Rename">
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleDuplicate(p)} title="Duplicate">
                    <Copy className="h-3.5 w-3.5" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => handleDelete(p)} title="Delete">
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Connection validation helpers
// ---------------------------------------------------------------------------

function canReach(edges: Edge[], from: string, to: string): boolean {
  const visited = new Set<string>();
  const stack = [from];
  while (stack.length) {
    const cur = stack.pop()!;
    if (cur === to) return true;
    if (visited.has(cur)) continue;
    visited.add(cur);
    for (const e of edges) if (e.source === cur) stack.push(e.target);
  }
  return false;
}

// ---------------------------------------------------------------------------
// Result summarization
// ---------------------------------------------------------------------------

function summarizeInstrumentResult(out: SystemOutputSummary): string {
  if (out.kind === "osa" && out.osa) {
    return `${out.osa.peak_wavelength_nm.toFixed(1)} nm @ ${out.osa.peak_power_dbm.toFixed(1)} dBm`;
  }
  if (out.kind === "power_meter" && out.power_meter) {
    return `${formatWatts(out.power_meter.total_power_w)}`;
  }
  if (out.kind === "beam_profiler" && out.beam) {
    return `M² ${out.beam.m2x.toFixed(2)} / ${out.beam.m2y.toFixed(2)}`;
  }
  return `${formatWatts(out.total_power_w)} out`;
}

function summarizeNodeResult(nodeId: string, kind: string, result: SystemSimulationResult): string | undefined {
  const out = result.outputs[nodeId];
  if (out) return summarizeInstrumentResult(out);

  const nr = result.nodes[nodeId] as Record<string, unknown> | undefined;
  if (!nr) return undefined;

  if (kind === "fiber_active") {
    const gain = nr.gain_db;
    return typeof gain === "number" ? `${gain.toFixed(1)} dB gain` : "no gain (check pump)";
  }
  if (kind === "fbg") {
    if (nr.role === "cavity_hr") return "cavity HR mirror";
    if (nr.role === "cavity_oc" && typeof nr.laser_output_w === "number") {
      return `${formatWatts(nr.laser_output_w)} laser out`;
    }
    if (nr.role === "filter" && typeof nr.reflected_power_w === "number") {
      return `${formatWatts(nr.reflected_power_w)} reflected`;
    }
  }
  if (kind === "power_combiner" && typeof nr.combined_power_w === "number") {
    return `${formatWatts(nr.combined_power_w)} (${nr.num_inputs} in)`;
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

let nodeCounter = 1;

function makeId() { return `node-${Date.now()}-${nodeCounter++}`; }

function makeNode(
  kind: string,
  label: string,
  position: { x: number; y: number },
  params: Record<string, unknown> = {},
  deviceId?: string,
  deviceName?: string,
): SystemNode {
  return {
    id: makeId(),
    type: kind,
    position,
    data: {
      label,
      nodeKind: kind as SystemNodeData["nodeKind"],
      deviceId,
      deviceName,
      params,
    },
  };
}

function edgeOptsFor(connection: Connection) {
  const color = connection.targetHandle === "pump" ? PUMP_EDGE_COLOR : "hsl(var(--primary))";
  return { animated: true, markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 } };
}

/** Canvas draft from the last session, read synchronously so the very first
 * render already has it — an async load raced the autosave, which is why
 * autosave used to skip empty canvases (and deleting the last node never
 * stuck: it came back on reload). */
function loadDraft(): { nodes: SystemNode[]; edges: Edge[] } {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const { nodes, edges } = JSON.parse(saved);
      return { nodes: nodes ?? [], edges: edges ?? [] };
    }
  } catch { /* corrupt or unavailable storage — start empty */ }
  return { nodes: [], edges: [] };
}

export function SystemBuilderPage() {
  const [draft] = useState(loadDraft);
  const [nodes, setNodes, onNodesChange] = useNodesState<SystemNode>(draft.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(draft.edges);
  const [paletteQuery, setPaletteQuery] = useState("");
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance<SystemNode, Edge> | null>(null);
  const [selectedNode, setSelectedNode] = useState<SystemNode | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const [currentSystemId, setCurrentSystemId] = useState<string | null>(null);
  const [currentSystemName, setCurrentSystemName] = useState<string | null>(null);
  const [projectsOpen, setProjectsOpen] = useState(false);

  const [simJobId, setSimJobId] = useState<string | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState<SystemSimulationResult | null>(null);
  const [showResults, setShowResults] = useState(false);
  const simSocket = useJobSocket<SystemSimulationResult>(simJobId);

  // Load devices from library
  useEffect(() => {
    api.listDevices().then(setDevices).catch(() => {});
  }, []);

  // Autosave draft on change — including an emptied canvas.
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ nodes, edges }));
    } catch { /* storage full/blocked — the draft just isn't persisted */ }
  }, [nodes, edges]);

  // ---- Simulation job lifecycle ----
  useEffect(() => {
    if (!simJobId) return;
    if (simSocket.status === "completed" && simSocket.result) {
      setSimResult(simSocket.result);
      setShowResults(true);
      setSimulating(false);
      const result = simSocket.result;
      setNodes((prev) =>
        prev.map((n) => ({
          ...n,
          data: { ...n.data, resultSummary: summarizeNodeResult(n.id, n.data.nodeKind, result) },
        })),
      );
      toast.success(
        result.warnings.length > 0
          ? `Simulation completed with ${result.warnings.length} warning(s)`
          : "Simulation completed",
      );
    } else if (simSocket.status === "error") {
      setSimulating(false);
      toast.error(simSocket.error ?? "Simulation failed");
    } else if (simSocket.status === "cancelled") {
      setSimulating(false);
      toast("Simulation cancelled");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simSocket.status, simSocket.result, simJobId]);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge({ ...connection, ...edgeOptsFor(connection) }, eds)),
    [setEdges],
  );

  // ---- Connection validation ----
  const isValidConnection = useCallback(
    (conn: Connection | Edge): boolean => {
      const source = nodes.find((n) => n.id === conn.source);
      const target = nodes.find((n) => n.id === conn.target);
      if (!source || !target || source.id === target.id) return false;

      const sourceKind = source.data.nodeKind;
      const targetKind = target.data.nodeKind;

      if (SINK_KINDS.has(sourceKind)) return false; // outputs have no outgoing port
      if (SOURCE_KINDS.has(targetKind)) return false; // sources take no input

      const isPumpPort = conn.targetHandle === "pump";
      if (isPumpPort && targetKind !== "coupler_wdm") return false;

      const mainInputs = edges.filter((e) => e.target === target.id && e.targetHandle !== "pump");
      const pumpInputs = edges.filter((e) => e.target === target.id && e.targetHandle === "pump");
      // Power combiners are the one exception to "single main input" — they
      // exist specifically to sum N incoming lines (e.g. several pump diodes).
      if (!isPumpPort && mainInputs.length > 0 && targetKind !== "power_combiner") return false;
      if (isPumpPort && pumpInputs.length > 0) return false;

      // Splitting the main signal isn't solved by the engine yet — one
      // outgoing "main chain" edge per node — but any number of instrument
      // taps (OSA/power meter/beam profiler) can branch off the same node.
      if (!INSTRUMENT_KINDS.has(targetKind)) {
        const existingMainOutputs = edges.filter(
          (e) => e.source === source.id && !INSTRUMENT_KINDS.has(nodes.find((n) => n.id === e.target)?.data.nodeKind ?? ""),
        );
        if (existingMainOutputs.length > 0) return false;
      }

      // Reject connections that would close a loop.
      if (conn.target && conn.source && canReach(edges, conn.target, conn.source)) return false;

      return true;
    },
    [nodes, edges],
  );

  // ---- Drag-and-drop from palette ----

  const onDragStart = useCallback(
    (e: React.DragEvent, kind: string, label: string, deviceId?: string, params?: Record<string, unknown>) => {
      e.dataTransfer.setData("application/lampy-node", JSON.stringify({ kind, label, deviceId, params: params ?? {} }));
      e.dataTransfer.effectAllowed = "move";
    },
    [],
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!rfInstance) return;
      const raw = e.dataTransfer.getData("application/lampy-node");
      if (!raw) return;
      const { kind, label, deviceId, params } = JSON.parse(raw) as {
        kind: string; label: string; deviceId?: string; params: Record<string, unknown>;
      };
      // screenToFlowPosition takes raw client (viewport) coordinates — it already
      // accounts for the pane's own offset and the current pan/zoom internally.
      // Subtracting the wrapper's bounding rect here double-counted that offset,
      // dropping the node far from the cursor (worse the further the canvas sits
      // from the page's top-left corner).
      const position = rfInstance.screenToFlowPosition({
        x: e.clientX,
        y: e.clientY,
      });
      const deviceName = deviceId ? devices.find((d) => d.id === deviceId)?.name : undefined;
      const node = makeNode(kind, label, position, params, deviceId, deviceName);
      setNodes((prev) => [...prev, node]);
    },
    [rfInstance, devices, setNodes],
  );

  // ---- Node selection ----

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNode(node as SystemNode);
    },
    [],
  );

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // ---- Update / delete ----

  const handleUpdateNode = useCallback(
    (id: string, data: Partial<SystemNodeData>) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...data } } : n)),
      );
      setSelectedNode((prev) => (prev?.id === id ? { ...prev, data: { ...prev.data, ...data } } : prev));
    },
    [setNodes],
  );

  // Every removal — Delete/Backspace, the panel's "Remove node" button, an
  // edge's × button — goes through React Flow's delete pipeline, so they all
  // share one path: snapshot the canvas first, then offer Undo.
  const snapshotRef = useRef<{ nodes: SystemNode[]; edges: Edge[] } | null>(null);
  const latest = useRef({ nodes, edges });
  latest.current = { nodes, edges };

  const onBeforeDelete: OnBeforeDelete<SystemNode, Edge> = useCallback(async () => {
    snapshotRef.current = latest.current;
    return true;
  }, []);

  const onDelete = useCallback(
    ({ nodes: removedNodes, edges: removedEdges }: { nodes: SystemNode[]; edges: Edge[] }) => {
      const removedIds = new Set(removedNodes.map((n) => n.id));
      setSelectedNode((prev) => (prev && removedIds.has(prev.id) ? null : prev));
      const snapshot = snapshotRef.current;
      const what =
        removedNodes.length === 1
          ? `Removed "${removedNodes[0].data.label}"`
          : removedNodes.length > 1
            ? `Removed ${removedNodes.length} components`
            : removedEdges.length === 1
              ? "Removed connection"
              : `Removed ${removedEdges.length} connections`;
      toast(what, {
        action: snapshot
          ? {
              label: "Undo",
              onClick: () => {
                setNodes(snapshot.nodes);
                setEdges(snapshot.edges);
              },
            }
          : undefined,
      });
    },
    [setNodes, setEdges],
  );

  const handleDeleteNode = useCallback(
    (id: string) => {
      if (rfInstance) {
        void rfInstance.deleteElements({ nodes: [{ id }] });
        return;
      }
      setNodes((nds) => nds.filter((n) => n.id !== id));
      setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
      setSelectedNode(null);
    },
    [rfInstance, setNodes, setEdges],
  );

  // ---- Toolbar actions ----

  async function handleSave() {
    const doc = { nodes, edges };
    try {
      if (currentSystemId) {
        const updated = await api.updateSystem(currentSystemId, { graph: doc });
        setCurrentSystemName(updated.name);
        toast.success(`Saved "${updated.name}"`);
      } else {
        const name = window.prompt("Name this system", "Untitled system");
        if (!name) return;
        const created = await api.createSystem({ name, description: "", graph: doc });
        setCurrentSystemId(created.id);
        setCurrentSystemName(created.name);
        toast.success(`Saved "${created.name}"`);
      }
    } catch {
      toast.error("Failed to save system to the server");
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(doc));
  }

  function handleClear() {
    setNodes([]);
    setEdges([]);
    setSelectedNode(null);
    setCurrentSystemId(null);
    setCurrentSystemName(null);
    setSimResult(null);
    setShowResults(false);
    localStorage.removeItem(STORAGE_KEY);
    toast("Canvas cleared");
  }

  async function handleLoadProject(id: string) {
    try {
      const sys = await api.getSystem(id);
      const doc = sys.graph as { nodes?: SystemNode[]; edges?: Edge[] };
      setNodes(doc.nodes ?? []);
      setEdges(doc.edges ?? []);
      setCurrentSystemId(sys.id);
      setCurrentSystemName(sys.name);
      setSelectedNode(null);
      setSimResult(null);
      setShowResults(false);
      setProjectsOpen(false);
      toast.success(`Loaded "${sys.name}"`);
    } catch {
      toast.error("Failed to load system");
    }
  }

  async function handleSimulate() {
    if (nodes.length === 0) { toast.error("Add at least one component to the canvas first"); return; }
    const payload: SystemSimulateRequest = {
      nodes: nodes.map((n) => ({
        id: n.id,
        kind: n.data.nodeKind as SystemNodeKind,
        label: n.data.label,
        params: n.data.params,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        source_port: e.sourceHandle ?? "out",
        target_port: e.targetHandle ?? "in",
      })),
    };

    setSimulating(true);
    try {
      const check = await api.validateSystem(payload);
      if (!check.valid) {
        toast.error(check.issues[0] ?? "The system cannot be simulated", {
          description: check.issues.length > 1 ? `+${check.issues.length - 1} more issue(s)` : undefined,
        });
        setSimulating(false);
        return;
      }
      const { job_id } = await api.simulateSystem(payload);
      setSimJobId(job_id);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to start simulation");
      setSimulating(false);
    }
  }

  // ---- Device grouping for palette ----

  const paletteGroups = useMemo(() => {
    const groups: Record<string, Device[]> = {
      fiber_active: [], fiber_passive: [], fbg: [], coupler_wdm: [], pump_source: [],
    };
    const q = paletteQuery.trim().toLowerCase();
    for (const d of devices) {
      if (!(d.device_type in groups)) continue;
      if (q && !`${d.name} ${d.manufacturer ?? ""} ${d.part_number ?? ""}`.toLowerCase().includes(q)) continue;
      groups[d.device_type].push(d);
    }
    return groups;
  }, [devices, paletteQuery]);

  const nodesById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  return (
    <div className="container mx-auto py-8 max-w-7xl h-full flex flex-col">
      <PageHeader
        eyebrow="Platform"
        title={currentSystemName ? `Laser System Builder — ${currentSystemName}` : "Laser System Builder"}
        description="Assemble your fiber laser schematic by connecting blocks on the canvas. Drag components from the palette and link optical ports."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setProjectsOpen(true)}>
              <FolderOpen className="h-3.5 w-3.5 mr-1.5" />Projects
            </Button>
            <Button variant="outline" size="sm" onClick={handleSave}>
              <Save className="h-3.5 w-3.5 mr-1.5" />Save
            </Button>
            <Button variant="outline" size="sm" onClick={handleClear}>
              <RotateCcw className="h-3.5 w-3.5 mr-1.5" />Clear
            </Button>
            <Button size="sm" onClick={handleSimulate} disabled={simulating}>
              {simulating ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5 mr-1.5" />
              )}
              {simulating ? "Simulating…" : "Simulate"}
            </Button>
          </div>
        }
      />

      <div className="relative flex h-[calc(100vh-15rem)] min-h-[560px] rounded-xl overflow-hidden border border-border bg-card/30">
        {/* ---- Palette ---- */}
        <div className="w-60 shrink-0 border-r border-border bg-card/60 flex flex-col">
          <div className="px-3 pt-3 pb-2 border-b border-border space-y-2">
            <div className="flex items-baseline justify-between">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Components</p>
              <p className="text-[10px] text-muted-foreground">drag to canvas</p>
            </div>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={paletteQuery}
                onChange={(e) => setPaletteQuery(e.target.value)}
                placeholder="Search catalogue…"
                className="h-8 pl-7 text-xs"
              />
            </div>
          </div>
          {/* Radix's viewport wraps content in a display:table div, which lets long
              catalogue names push items past the panel edge and breaks truncate. */}
          <ScrollArea className="flex-1 p-3 [&_[data-radix-scroll-area-viewport]>div]:!block">
            {!paletteQuery && (
              <>
                <div className="mb-3">
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium mb-1.5">Sources &amp; optics</p>
                  <div className="space-y-1">
                    {GENERIC_BLOCKS.map((b) => (
                      <PaletteItem key={b.kind} kind={b.kind} label={b.label} sublabel={b.sublabel}
                        onDragStart={(e) => onDragStart(e, b.kind, b.label, undefined, b.params)} />
                    ))}
                  </div>
                </div>
                <div className="mb-3">
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium mb-1.5">Instruments</p>
                  <div className="space-y-1">
                    {INSTRUMENT_BLOCKS.map((b) => (
                      <PaletteItem key={b.kind} kind={b.kind} label={b.label} sublabel={b.sublabel}
                        onDragStart={(e) => onDragStart(e, b.kind, b.label, undefined, b.params)} />
                    ))}
                  </div>
                </div>
                <Separator className="mb-3" />
              </>
            )}
            {Object.entries(paletteGroups).map(([type, devs]) => (
              <DevicePaletteSection
                key={type}
                title={deviceTypeLabels[type as DeviceType]}
                devices={devs}
                onDragStart={onDragStart}
                forceOpen={!!paletteQuery}
              />
            ))}
            {paletteQuery && Object.values(paletteGroups).every((g) => g.length === 0) && (
              <p className="text-xs text-muted-foreground text-center py-6">No catalogue part matches “{paletteQuery}”.</p>
            )}
          </ScrollArea>
          <div className="p-3 border-t border-border">
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              Drag from a port to another to connect. Click a block to edit it; click a connection to remove it.
              <kbd className="ml-1 rounded bg-secondary px-1 font-mono">Del</kbd> removes the selection.
            </p>
          </div>
        </div>

        {/* ---- Canvas ---- */}
        <div ref={wrapperRef} className="flex-1 min-w-0">
          <ReactFlow<SystemNode, Edge>
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onBeforeDelete={onBeforeDelete}
            onDelete={onDelete}
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            onInit={setRfInstance}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onDrop={onDrop}
            onDragOver={onDragOver}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            fitViewOptions={{ padding: 0.25, maxZoom: 1.1 }}
            deleteKeyCode={["Delete", "Backspace"]}
            className="bg-background"
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} className="opacity-30" />
            <Controls showInteractive={false} />
            <MiniMap
              bgColor="hsl(var(--card))"
              maskColor="hsl(var(--background) / 0.65)"
              maskStrokeColor="hsl(var(--primary))"
              maskStrokeWidth={2}
              nodeColor={(n) => kindStyle((n.data as SystemNodeData).nodeKind).hex}
              nodeBorderRadius={6}
              pannable
              zoomable
            />
            {nodes.length === 0 && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <Package className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground/50">Drag components from the palette to get started</p>
                <p className="text-xs text-muted-foreground/40 mt-1">Click a block or connection, then Delete to remove it</p>
              </div>
            )}
          </ReactFlow>
        </div>

        {/* ---- Node detail ---- */}
        {selectedNode && (
          <NodeDetailPanel
            node={selectedNode}
            nodeResult={simResult?.nodes[selectedNode.id]}
            onUpdate={handleUpdateNode}
            onDelete={handleDeleteNode}
            onClose={() => setSelectedNode(null)}
          />
        )}

        {/* ---- Simulation results ---- */}
        {simResult && showResults && (
          <ResultsPanel result={simResult} nodesById={nodesById} onClose={() => setShowResults(false)} />
        )}
      </div>

      <ProjectsDialog
        open={projectsOpen}
        onClose={() => setProjectsOpen(false)}
        onLoad={handleLoadProject}
      />
    </div>
  );
}
