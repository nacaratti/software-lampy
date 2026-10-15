import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { fieldSpecsFor } from "@/lib/paramFieldSpecs";
import { cn } from "@/lib/utils";
import { INSTRUMENT_KINDS, SOURCE_KINDS, kindStyle, type SystemNode } from "./nodeStyles";

/** The 2–3 parameters worth seeing on the canvas without opening the node. */
const SUMMARY_KEYS: Record<string, string[]> = {
  seed: ["wavelength_nm", "power_w"],
  pump_source: ["wavelength_nm", "power_w"],
  fiber_active: ["length_m", "core_radius_um", "N_total"],
  fiber_passive: ["length_m", "core_radius_um"],
  fbg: ["central_wavelength_nm", "reflectivity", "bandwidth_nm"],
  coupler_wdm: ["insertion_loss_port1_db", "insertion_loss_port2_db"],
  power_combiner: ["insertion_loss_db"],
  osa: ["rbw_nm"],
  power_meter: [],
  beam_profiler: ["grid_n"],
};

const ION_LABEL: Record<string, string> = { yb: "Yb³⁺", er: "Er³⁺", tm: "Tm³⁺" };

function formatValue(v: unknown): string {
  if (typeof v !== "number") return String(v ?? "—");
  if (v === 0) return "0";
  const a = Math.abs(v);
  if (a >= 1e4 || a < 1e-3) return v.toExponential(1).replace("e+", "e");
  return Number(v.toPrecision(4)).toString();
}

function summaryRows(kind: string, params: Record<string, unknown>) {
  const specs = fieldSpecsFor(kind) ?? [];
  return (SUMMARY_KEYS[kind] ?? [])
    .filter((k) => params[k] !== undefined && params[k] !== null)
    .map((k) => {
      const spec = specs.find((s) => s.key === k);
      const unit = spec && spec.type === "number" ? spec.unit : undefined;
      return { key: k, label: spec?.label ?? k.replace(/_/g, " "), value: formatValue(params[k]), unit };
    });
}

function subtitle(kind: string, params: Record<string, unknown>): string {
  const base = kindStyle(kind).label;
  if (kind !== "fiber_active") return base;
  const ion = String(params.ion ?? "yb");
  return `${base} · ${ION_LABEL[ion] ?? ion}`;
}

const handleBase =
  "!h-3 !w-3 !rounded-full !border-2 !bg-card transition-transform hover:!scale-125";

function SystemNodeCardImpl({ data, selected }: NodeProps<SystemNode>) {
  const kind = data.nodeKind;
  const style = kindStyle(kind);
  const Icon = style.icon;
  const rows = summaryRows(kind, data.params);
  const isSource = SOURCE_KINDS.has(kind);
  const isInstrument = INSTRUMENT_KINDS.has(kind);
  const isWdm = kind === "coupler_wdm";
  const warn = data.resultSummary?.startsWith("no ");

  return (
    <div
      className={cn(
        "group relative w-[212px] overflow-hidden rounded-xl border bg-card text-card-foreground shadow-sm transition-shadow",
        selected ? "border-primary/70 shadow-lg ring-2 ring-primary/40" : "border-border hover:shadow-md",
      )}
    >
      <div className={cn("h-[3px] w-full", style.bar)} />

      {!isSource && (
        <Handle
          type="target"
          position={Position.Left}
          title="Optical input"
          className={cn(handleBase, "!border-primary")}
        />
      )}
      {isWdm && (
        <Handle
          type="target"
          id="pump"
          position={Position.Bottom}
          title="Pump input"
          className={cn(handleBase, "!border-rose-500")}
        />
      )}

      <div className="flex items-start gap-2.5 px-3 pt-2.5">
        <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", style.chip)}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[12.5px] font-semibold leading-tight" title={data.label}>
            {data.label}
          </div>
          <div className="truncate text-[10.5px] text-muted-foreground" title={data.deviceName}>
            {subtitle(kind, data.params)}
          </div>
        </div>
      </div>

      {rows.length > 0 ? (
        <dl className="mt-2 space-y-0.5 px-3 pb-2.5">
          {rows.map((r) => (
            <div key={r.key} className="flex items-baseline justify-between gap-3 text-[11px]">
              <dt className="truncate text-muted-foreground">{r.label}</dt>
              <dd className="shrink-0 font-mono tabular-nums">
                {r.value}
                {r.unit && <span className="ml-0.5 text-muted-foreground">{r.unit}</span>}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <div className="px-3 pb-2.5 pt-1 text-[11px] text-muted-foreground">
          {isWdm ? "Signal ← left · pump ↑ bottom" : isInstrument ? "Measurement tap" : "No parameters"}
        </div>
      )}

      {data.resultSummary && (
        <div
          className={cn(
            "border-t px-3 py-1.5 font-mono text-[11px] tabular-nums",
            warn
              ? "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400"
              : "border-primary/20 bg-primary/10 text-primary",
          )}
        >
          {data.resultSummary}
        </div>
      )}

      {!isInstrument && (
        <Handle
          type="source"
          position={Position.Right}
          title="Optical output"
          className={cn(handleBase, "!border-primary")}
        />
      )}
    </div>
  );
}

export const SystemNodeCard = memo(SystemNodeCardImpl);
