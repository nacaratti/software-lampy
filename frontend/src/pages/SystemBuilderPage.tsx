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
  Activity, Minus, Layers, GitMerge, Zap, Monitor,
  Trash2, Plus, Save, FolderOpen, Play, Package, X, ChevronDown, ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/layout/PageHeader";
import { api } from "@/lib/api";
import type { Device, DeviceType } from "@/types/device";
import { deviceTypeLabels } from "@/types/device";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SystemNodeData = {
  label: string;
  nodeKind: DeviceType | "output" | "seed";
  deviceId?: string;
  deviceName?: string;
  params: Record<string, unknown>;
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
  output:        { icon: Monitor,  color: "text-teal-400",    border: "border-teal-500/50",    bg: "bg-teal-950/60" },
  seed:          { icon: Zap,      color: "text-yellow-400",  border: "border-yellow-500/50",  bg: "bg-yellow-950/60" },
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

// Primary key params to show per node kind
const SUMMARY_KEYS: Record<string, string[]> = {
  fiber_active:  ["length_m", "core_radius_um", "peak_absorption_dB_m_976nm"],
  fiber_passive: ["length_m", "core_radius_um", "attenuation_db_km"],
  fbg:           ["central_wavelength_nm", "reflectivity", "bandwidth_nm"],
  coupler_wdm:   ["wavelength_1_nm", "wavelength_2_nm", "insertion_loss_port1_db"],
  pump_source:   ["wavelength_nm", "power_w"],
  output:        [],
  seed:          ["wavelength_nm", "power_w"],
};

// ---------------------------------------------------------------------------
// Custom node component
// ---------------------------------------------------------------------------

function SystemNodeComponent({ data, selected }: NodeProps<SystemNode>) {
  const meta = getKindMeta(data.nodeKind);
  const Icon = meta.icon;
  const summaryKeys = SUMMARY_KEYS[data.nodeKind] ?? [];
  const isPump = data.nodeKind === "pump_source" || data.nodeKind === "seed";
  const isOutput = data.nodeKind === "output";
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
        {isOutput && (
          <div className="text-[10px] text-muted-foreground">Output monitor</div>
        )}
      </div>

      {/* Output handles */}
      {!isOutput && (
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
  output: SystemNodeComponent,
  seed: SystemNodeComponent,
};

// ---------------------------------------------------------------------------
// Palette
// ---------------------------------------------------------------------------

const GENERIC_BLOCKS: Array<{ kind: string; label: string; params: Record<string, unknown> }> = [
  { kind: "output",      label: "Output / Monitor",   params: {} },
  { kind: "pump_source", label: "976 nm Pump",        params: { wavelength_nm: 976, power_w: 0.5 } },
  { kind: "seed",        label: "1064 nm Seed Signal",params: { wavelength_nm: 1064, power_w: 1e-3 } },
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
  onUpdate,
  onDelete,
  onClose,
}: {
  node: SystemNode;
  onUpdate: (id: string, data: Partial<SystemNodeData>) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}) {
  const [label, setLabel] = useState(node.data.label);
  const [paramsText, setParamsText] = useState(JSON.stringify(node.data.params, null, 2));
  const [paramErr, setParamErr] = useState("");

  useEffect(() => {
    setLabel(node.data.label);
    setParamsText(JSON.stringify(node.data.params, null, 2));
    setParamErr("");
  }, [node.id, node.data.label, node.data.params]);

  function handleParamsChange(t: string) {
    setParamsText(t);
    try {
      JSON.parse(t);
      setParamErr("");
    } catch {
      setParamErr("Invalid JSON");
    }
  }

  function handleApply() {
    try {
      const params = JSON.parse(paramsText);
      onUpdate(node.id, { label, params });
      toast.success("Node updated");
    } catch {
      toast.error("Fix the JSON before applying");
    }
  }

  const meta = getKindMeta(node.data.nodeKind);
  const Icon = meta.icon;

  return (
    <div className="w-64 shrink-0 border-l border-border bg-card/50 flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${meta.color}`} />
          <span className="text-sm font-medium">
            {deviceTypeLabels[node.data.nodeKind as DeviceType] ?? node.data.nodeKind}
          </span>
        </div>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
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
          <div>
            <Label className="text-xs">Label</Label>
            <Input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="mt-1 h-7 text-xs"
            />
          </div>
          <div>
            <Label className="text-xs">Parameters (JSON)</Label>
            <textarea
              className="w-full mt-1 h-52 rounded-md border border-border bg-background font-mono text-[10px] p-2 resize-none focus:outline-none focus:ring-1 focus:ring-ring"
              value={paramsText}
              onChange={(e) => handleParamsChange(e.target.value)}
              spellCheck={false}
            />
            {paramErr && <p className="text-[10px] text-destructive mt-0.5">{paramErr}</p>}
          </div>
          <Button size="sm" className="w-full" onClick={handleApply}>
            Apply
          </Button>
          <Separator />
          <Button
            size="sm"
            variant="destructive"
            className="w-full"
            onClick={() => { onDelete(node.id); onClose(); }}
          >
            <Trash2 className="h-3.5 w-3.5 mr-1.5" />Remove node
          </Button>
        </div>
      </ScrollArea>
    </div>
  );
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

  // Load devices from library
  useEffect(() => {
    api.listDevices().then(setDevices).catch(() => {});
  }, []);

  // Load saved system
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

  // Save on change
  useEffect(() => {
    if (nodes.length === 0 && edges.length === 0) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ nodes, edges }));
  }, [nodes, edges]);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge({ ...connection, ...DEFAULT_EDGE_OPTS }, eds)),
    [setEdges],
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
      if (!rfInstance || !wrapperRef.current) return;
      const raw = e.dataTransfer.getData("application/lampy-node");
      if (!raw) return;
      const { kind, label, deviceId, params } = JSON.parse(raw) as {
        kind: string; label: string; deviceId?: string; params: Record<string, unknown>;
      };
      const bounds = wrapperRef.current.getBoundingClientRect();
      const position = rfInstance.screenToFlowPosition({
        x: e.clientX - bounds.left,
        y: e.clientY - bounds.top,
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

  function handleSave() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ nodes, edges }));
    toast.success("System saved locally");
  }

  function handleClear() {
    setNodes([]);
    setEdges([]);
    setSelectedNode(null);
    localStorage.removeItem(STORAGE_KEY);
    toast("Canvas cleared");
  }

  function handleSimulate() {
    if (nodes.length === 0) { toast.error("Add at least one component to the canvas first"); return; }
    toast.info("System-level simulation is under development. Use the individual solvers in the meantime.", {
      duration: 5000,
    });
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

  return (
    <div className="container mx-auto py-8 max-w-7xl h-full flex flex-col">
      <PageHeader
        eyebrow="Platform"
        title="Laser System Builder"
        description="Assemble your fiber laser schematic by connecting blocks on the canvas. Drag components from the palette and link optical ports."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleSave}>
              <Save className="h-3.5 w-3.5 mr-1.5" />Save
            </Button>
            <Button variant="outline" size="sm" onClick={handleClear}>
              <FolderOpen className="h-3.5 w-3.5 mr-1.5" />Clear
            </Button>
            <Button size="sm" onClick={handleSimulate}>
              <Play className="h-3.5 w-3.5 mr-1.5" />Simulate
            </Button>
          </div>
        }
      />

      <div className="flex flex-1 min-h-0 rounded-xl overflow-hidden border border-border">
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
            onUpdate={handleUpdateNode}
            onDelete={handleDeleteNode}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>
    </div>
  );
}
