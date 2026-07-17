import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  BackgroundVariant,
  type Node,
  type Edge,
  type Connection,
  type NodeProps,
  type ReactFlowInstance,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { toast } from "sonner";
import {
  Activity, Minus, Layers, GitMerge, Zap,
  Trash2, Save, FolderOpen, Play, Package, X, ChevronDown, ChevronRight,
  Loader2, RotateCcw, Copy, Pencil, BarChart3, Gauge, ScanEye, Merge, FlaskConical,
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

type InstrumentKind = "osa" | "power_meter" | "beam_profiler";

type SystemNodeData = {
  label: string;
  nodeKind: DeviceType | "seed" | "power_combiner" | InstrumentKind;
  deviceId?: string;
  deviceName?: string;
  params: Record<string, unknown>;
  resultSummary?: string;
};

type SystemNode = Node<SystemNodeData>;

const STORAGE_KEY = "lampy-system-v1";

// ---------------------------------------------------------------------------
// Node visual styles
// ---------------------------------------------------------------------------

const KIND_META: Record<string, { icon: React.ComponentType<{ className?: string }>; color: string; border: string; bg: string }> = {
  fiber_active: { icon: Activity,  color: "text-emerald-400", border: "border-emerald-500/50", bg: "bg-emerald-950/60" },
  fiber_passive: { icon: Minus,    color: "text-sky-400",     border: "border-sky-500/50",     bg: "bg-sky-950/60" },
  fbg:           { icon: Layers,   color: "text-violet-400",  border: "border-violet-500/50",  bg: "bg-violet-950/60" },
  coupler_wdm:   { icon: GitMerge, color: "text-amber-400",   border: "border-amber-500/50",   bg: "bg-amber-950/60" },
  pump_source:   { icon: Zap,      color: "text-rose-400",    border: "border-rose-500/50",    bg: "bg-rose-950/60" },
  seed:          { icon: Zap,      color: "text-yellow-400",  border: "border-yellow-500/50",  bg: "bg-yellow-950/60" },
  power_combiner: { icon: Merge,   color: "text-indigo-400",  border: "border-indigo-500/50",  bg: "bg-indigo-950/60" },
  osa:           { icon: BarChart3, color: "text-cyan-400",   border: "border-cyan-500/50",    bg: "bg-cyan-950/60" },
  power_meter:   { icon: Gauge,     color: "text-orange-400", border: "border-orange-500/50",  bg: "bg-orange-950/60" },
  beam_profiler: { icon: ScanEye,   color: "text-pink-400",   border: "border-pink-500/50",    bg: "bg-pink-950/60" },
};

function getKindMeta(kind: string) {
  return KIND_META[kind] ?? { icon: Package, color: "text-muted-foreground", border: "border-border", bg: "bg-card" };
}

function formatParam(v: unknown): string {
  if (typeof v === "number") {
    if (Math.abs(v) < 1e-3 && v !== 0) return v.toExponential(2);
    if (Math.abs(v) > 1e4) return v.toExponential(2);
    return String(v);
  }
  return String(v ?? "");
}

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

// Primary key params to show per node kind
const SUMMARY_KEYS: Record<string, string[]> = {
  fiber_active:  ["length_m", "core_radius_um", "peak_absorption_dB_m_976nm"],
  fiber_passive: ["length_m", "core_radius_um", "attenuation_db_km"],
  fbg:           ["central_wavelength_nm", "reflectivity", "bandwidth_nm"],
  coupler_wdm:   ["wavelength_1_nm", "wavelength_2_nm", "insertion_loss_port1_db"],
  pump_source:   ["wavelength_nm", "power_w"],
  seed:          ["wavelength_nm", "power_w"],
  power_combiner: ["insertion_loss_db"],
  osa:           ["rbw_nm"],
  power_meter:   [],
  beam_profiler: ["grid_n", "num_z"],
};

// Kinds that only ever take one input and produce one output (used by the
// connection-validation rules below — the engine can't yet solve splitters).
const SOURCE_KINDS = new Set(["pump_source", "seed"]);
// Every terminal node is a measurement tap — any number of them can hang off
// the same node, since they only read the signal (matches the engine's
// non_tap_out rule). There is no separate non-tap "output" sink anymore.
const INSTRUMENT_KINDS = new Set(["osa", "power_meter", "beam_profiler"]);
const SINK_KINDS = INSTRUMENT_KINDS;

// ---------------------------------------------------------------------------
// Custom node component
// ---------------------------------------------------------------------------

function SystemNodeComponent({ data, selected }: NodeProps<SystemNode>) {
  const meta = getKindMeta(data.nodeKind);
  const Icon = meta.icon;
  const summaryKeys = SUMMARY_KEYS[data.nodeKind] ?? [];
  const isPump = data.nodeKind === "pump_source" || data.nodeKind === "seed";
  const isInstrument = data.nodeKind === "osa" || data.nodeKind === "power_meter" || data.nodeKind === "beam_profiler";
  const isTerminal = isInstrument;
  const isCoupler = data.nodeKind === "coupler_wdm";

  return (
    <div
      className={`rounded-lg border ${meta.border} ${meta.bg} backdrop-blur-sm min-w-[140px] max-w-[180px] shadow-lg transition-all ${
        selected ? "ring-2 ring-primary ring-offset-1 ring-offset-background" : ""
      }`}
    >
      {/* Input handles */}
      {!isPump && (
        <Handle
          type="target"
          position={Position.Left}
          className="!w-2.5 !h-2.5 !border-2 !border-muted-foreground !bg-background"
        />
      )}
      {isCoupler && (
        <Handle
          type="target"
          id="pump"
          position={Position.Top}
          className="!w-2.5 !h-2.5 !border-2 !border-rose-400 !bg-background"
          style={{ left: "50%" }}
        />
      )}

      {/* Node body */}
      <div className="px-3 py-2.5">
        <div className="flex items-center gap-1.5 mb-1.5">
          <Icon className={`h-3.5 w-3.5 shrink-0 ${meta.color}`} />
          <span className="text-[11px] font-semibold leading-tight line-clamp-2 text-foreground">
            {data.label}
          </span>
        </div>
        {summaryKeys.length > 0 && (
          <div className="space-y-0.5">
            {summaryKeys
              .filter((k) => data.params[k] !== undefined)
              .map((k) => (
                <div key={k} className="flex justify-between gap-2 text-[10px]">
                  <span className="text-muted-foreground truncate">{k.replace(/_/g, " ")}</span>
                  <span className="font-mono text-foreground shrink-0">{formatParam(data.params[k])}</span>
                </div>
              ))}
          </div>
        )}
        {isInstrument && (
          <div className="text-[10px] text-muted-foreground">
            {data.nodeKind === "osa" && "Spectrum analyzer"}
            {data.nodeKind === "power_meter" && "Power meter"}
            {data.nodeKind === "beam_profiler" && "Beam profiler (CCD)"}
          </div>
        )}
        {data.resultSummary && (
          <div className="mt-1.5 pt-1.5 border-t border-border/60 text-[10px] font-mono text-primary">
            {data.resultSummary}
          </div>
        )}
      </div>

      {/* Output handles */}
      {!isTerminal && (
        <Handle
          type="source"
          position={Position.Right}
          className="!w-2.5 !h-2.5 !border-2 !border-muted-foreground !bg-background"
        />
      )}
    </div>
  );
}

const nodeTypes = {
  fiber_active: SystemNodeComponent,
  fiber_passive: SystemNodeComponent,
  fbg: SystemNodeComponent,
  coupler_wdm: SystemNodeComponent,
  pump_source: SystemNodeComponent,
  seed: SystemNodeComponent,
  power_combiner: SystemNodeComponent,
  osa: SystemNodeComponent,
  power_meter: SystemNodeComponent,
  beam_profiler: SystemNodeComponent,
};

// ---------------------------------------------------------------------------
// Palette
// ---------------------------------------------------------------------------

const GENERIC_BLOCKS: Array<{ kind: string; label: string; params: Record<string, unknown> }> = [
  { kind: "pump_source",    label: "976 nm Pump",         params: { wavelength_nm: 976, power_w: 0.5 } },
  { kind: "seed",           label: "1064 nm Seed Signal", params: { wavelength_nm: 1064, power_w: 1e-3 } },
  { kind: "power_combiner", label: "Power Combiner (N×1)", params: { insertion_loss_db: 0.5 } },
];

const INSTRUMENT_BLOCKS: Array<{ kind: string; label: string; params: Record<string, unknown> }> = [
  { kind: "osa",           label: "OSA (Spectrum)",   params: { rbw_nm: 0.1 } },
  { kind: "power_meter",   label: "Power Meter",      params: {} },
  { kind: "beam_profiler", label: "Beam Profiler (CCD)", params: { grid_n: 128, num_z: 21 } },
];

function PaletteItem({
  label,
  kind,
  onDragStart,
}: {
  label: string;
  kind: string;
  onDragStart: (e: React.DragEvent, kind: string, label: string, deviceId?: string, params?: Record<string, unknown>) => void;
  deviceId?: string;
  params?: Record<string, unknown>;
}) {
  const meta = getKindMeta(kind);
  const Icon = meta.icon;
  return (
    <div
      className={`flex items-center gap-2 rounded-md px-2.5 py-2 cursor-grab active:cursor-grabbing border ${meta.border} ${meta.bg} hover:opacity-90 transition-opacity select-none`}
      draggable
      onDragStart={(e) => onDragStart(e, kind, label)}
    >
      <Icon className={`h-3.5 w-3.5 shrink-0 ${meta.color}`} />
      <span className="text-xs truncate">{label}</span>
    </div>
  );
}

function DevicePaletteSection({
  title,
  devices,
  onDragStart,
}: {
  title: string;
  devices: Device[];
  onDragStart: (e: React.DragEvent, kind: string, label: string, deviceId?: string, params?: Record<string, unknown>) => void;
}) {
  const [open, setOpen] = useState(true);
  if (devices.length === 0) return null;
  return (
    <div>
      <button
        className="flex items-center gap-1.5 w-full text-[10px] uppercase tracking-wider text-muted-foreground font-medium py-1 hover:text-foreground transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {title}
      </button>
      {open && (
        <div className="space-y-1 mt-1 mb-3">
          {devices.map((d) => (
            <div
              key={d.id}
              className={`flex items-center gap-2 rounded-md px-2.5 py-2 cursor-grab active:cursor-grabbing border ${getKindMeta(d.device_type).border} ${getKindMeta(d.device_type).bg} hover:opacity-90 transition-opacity select-none`}
              draggable
              onDragStart={(e) => onDragStart(e, d.device_type, d.name, d.id, d.parameters)}
            >
              {(() => { const Icon = getKindMeta(d.device_type).icon; return <Icon className={`h-3.5 w-3.5 shrink-0 ${getKindMeta(d.device_type).color}`} />; })()}
              <div className="min-w-0">
                <div className="text-xs truncate">{d.name}</div>
                {d.manufacturer && <div className="text-[10px] text-muted-foreground truncate">{d.manufacturer}</div>}
              </div>
            </div>
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

  const meta = getKindMeta(node.data.nodeKind);
  const Icon = meta.icon;

  return (
    <div className="w-80 shrink-0 border-l border-border bg-card/50 flex flex-col h-full z-20 relative">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${meta.color}`} />
          <span className="text-sm font-medium">
            {deviceTypeLabels[node.data.nodeKind as DeviceType] ?? node.data.nodeKind}
          </span>
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
            onClick={() => {
              if (!window.confirm(`Remove "${node.data.label}" and its connections?`)) return;
              onDelete(node.id);
              onClose();
            }}
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
                  const meta = getKindMeta(out.kind);
                  const Icon = meta.icon;
                  return (
                    <TabsTrigger key={nodeId} value={nodeId} className="gap-1.5">
                      <Icon className={`h-3 w-3 ${meta.color}`} />
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

const DEFAULT_EDGE_OPTS = {
  animated: true,
  style: { stroke: "hsl(var(--primary))", strokeWidth: 1.5 },
  markerEnd: { type: MarkerType.ArrowClosed, color: "hsl(var(--primary))" },
};

export function SystemBuilderPage() {
  const [nodes, setNodes, onNodesChange] = useNodesState<SystemNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
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

  // Load saved draft
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const { nodes: n, edges: e } = JSON.parse(saved);
        setNodes(n ?? []);
        setEdges(e ?? []);
      } catch { /* ignore */ }
    }
  }, [setNodes, setEdges]);

  // Autosave draft on change
  useEffect(() => {
    if (nodes.length === 0 && edges.length === 0) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ nodes, edges }));
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
    (connection: Connection) => setEdges((eds) => addEdge({ ...connection, ...DEFAULT_EDGE_OPTS }, eds)),
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

  const handleDeleteNode = useCallback(
    (id: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== id));
      setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
    },
    [setNodes, setEdges],
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
    for (const d of devices) {
      if (d.device_type in groups) groups[d.device_type].push(d);
    }
    return groups;
  }, [devices]);

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

      <div className="relative flex flex-1 min-h-0 rounded-xl overflow-hidden border border-border">
        {/* ---- Palette ---- */}
        <div className="w-52 shrink-0 border-r border-border bg-card/50 flex flex-col">
          <div className="px-3 py-2.5 border-b border-border">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
              Components
            </p>
            <p className="text-[10px] text-muted-foreground mt-0.5">Drag to canvas</p>
          </div>
          <ScrollArea className="flex-1 p-3">
            <div className="mb-3">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium mb-2">Generic</p>
              <div className="space-y-1">
                {GENERIC_BLOCKS.map((b) => (
                  <PaletteItem key={b.kind} label={b.label} kind={b.kind} onDragStart={onDragStart} />
                ))}
              </div>
            </div>
            <div className="mb-3">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium mb-2">Instruments</p>
              <div className="space-y-1">
                {INSTRUMENT_BLOCKS.map((b) => (
                  <PaletteItem key={b.kind} label={b.label} kind={b.kind} onDragStart={onDragStart} />
                ))}
              </div>
            </div>
            <Separator className="mb-3" />
            {Object.entries(paletteGroups).map(([type, devs]) => (
              <DevicePaletteSection
                key={type}
                title={deviceTypeLabels[type as DeviceType]}
                devices={devs}
                onDragStart={onDragStart}
              />
            ))}
          </ScrollArea>
          <div className="p-3 border-t border-border">
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              Tip: connect ports by dragging from one handle to another. Click a node to edit.
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
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            onInit={setRfInstance}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onDrop={onDrop}
            onDragOver={onDragOver}
            nodeTypes={nodeTypes}
            fitView
            deleteKeyCode="Delete"
            className="bg-background"
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} className="opacity-30" />
            <Controls className="!border-border !bg-card !rounded-lg !shadow-md" />
            <MiniMap
              className="!border-border !bg-card/80 !rounded-lg"
              nodeColor={(n) => {
                const kind = (n.data as SystemNodeData).nodeKind;
                const colors: Record<string, string> = {
                  fiber_active: "#34d399", fiber_passive: "#38bdf8",
                  fbg: "#a78bfa", coupler_wdm: "#fbbf24",
                  pump_source: "#f87171", output: "#2dd4bf", seed: "#fde047",
                };
                return colors[kind] ?? "#6b7280";
              }}
            />
            {nodes.length === 0 && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <Package className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground/50">Drag components from the palette to get started</p>
                <p className="text-xs text-muted-foreground/30 mt-1">Press Delete to remove selected nodes</p>
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
