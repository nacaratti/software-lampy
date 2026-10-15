import {
  Activity, Minus, Layers, GitMerge, Zap, Radio, Merge, BarChart3, Gauge, ScanEye, Package,
} from "lucide-react";
import type { Node } from "@xyflow/react";
import type { DeviceType } from "@/types/device";

export type InstrumentKind = "osa" | "power_meter" | "beam_profiler";

export type SystemNodeData = {
  label: string;
  nodeKind: DeviceType | "seed" | "power_combiner" | InstrumentKind;
  deviceId?: string;
  deviceName?: string;
  params: Record<string, unknown>;
  resultSummary?: string;
};

export type SystemNode = Node<SystemNodeData>;

export type KindGroup = "source" | "fiber" | "passive" | "instrument";

export interface KindStyle {
  label: string;
  group: KindGroup;
  icon: React.ComponentType<{ className?: string }>;
  /** Hex accent — minimap, edges, anything outside Tailwind. */
  hex: string;
  /** Icon + chip colors. Full literal class names so Tailwind's JIT sees them. */
  chip: string;
  /** 3 px accent bar along the top of the card. */
  bar: string;
}

// One accent per *role*, not per kind, so the canvas reads at a glance:
// light sources warm, fibers green/blue, passive optics violet/amber,
// instruments cyan. Cards themselves are neutral (bg-card) in both themes.
export const KIND_STYLES: Record<string, KindStyle> = {
  seed: {
    label: "Seed laser", group: "source", icon: Radio, hex: "#f59e0b",
    chip: "bg-amber-500/15 text-amber-600 dark:text-amber-400", bar: "bg-amber-500",
  },
  pump_source: {
    label: "Pump diode", group: "source", icon: Zap, hex: "#f43f5e",
    chip: "bg-rose-500/15 text-rose-600 dark:text-rose-400", bar: "bg-rose-500",
  },
  fiber_active: {
    label: "Active fiber", group: "fiber", icon: Activity, hex: "#10b981",
    chip: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400", bar: "bg-emerald-500",
  },
  fiber_passive: {
    label: "Passive fiber", group: "fiber", icon: Minus, hex: "#0ea5e9",
    chip: "bg-sky-500/15 text-sky-600 dark:text-sky-400", bar: "bg-sky-500",
  },
  fbg: {
    label: "FBG / mirror", group: "passive", icon: Layers, hex: "#8b5cf6",
    chip: "bg-violet-500/15 text-violet-600 dark:text-violet-400", bar: "bg-violet-500",
  },
  coupler_wdm: {
    label: "WDM / pump combiner", group: "passive", icon: GitMerge, hex: "#a855f7",
    chip: "bg-purple-500/15 text-purple-600 dark:text-purple-400", bar: "bg-purple-500",
  },
  power_combiner: {
    label: "Power combiner (N×1)", group: "passive", icon: Merge, hex: "#6366f1",
    chip: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400", bar: "bg-indigo-500",
  },
  osa: {
    label: "Optical spectrum analyzer", group: "instrument", icon: BarChart3, hex: "#06b6d4",
    chip: "bg-cyan-500/15 text-cyan-600 dark:text-cyan-400", bar: "bg-cyan-500",
  },
  power_meter: {
    label: "Power meter", group: "instrument", icon: Gauge, hex: "#06b6d4",
    chip: "bg-cyan-500/15 text-cyan-600 dark:text-cyan-400", bar: "bg-cyan-500",
  },
  beam_profiler: {
    label: "Beam profiler (CCD)", group: "instrument", icon: ScanEye, hex: "#06b6d4",
    chip: "bg-cyan-500/15 text-cyan-600 dark:text-cyan-400", bar: "bg-cyan-500",
  },
};

const FALLBACK_STYLE: KindStyle = {
  label: "Component", group: "passive", icon: Package, hex: "#6b7280",
  chip: "bg-muted text-muted-foreground", bar: "bg-muted-foreground",
};

export function kindStyle(kind: string): KindStyle {
  return KIND_STYLES[kind] ?? FALLBACK_STYLE;
}

export const INSTRUMENT_KINDS = new Set(["osa", "power_meter", "beam_profiler"]);
export const SOURCE_KINDS = new Set(["pump_source", "seed"]);

/** Edge color: pump lines rose, everything else the theme primary. */
export const PUMP_EDGE_COLOR = "#f43f5e";
