import { useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { toast } from "sonner";
import { Play, Plus, Trash2, Save, Loader2, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { NumberField } from "@/components/common/NumberField";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/layout/PageHeader";
import { FiberConfigForm } from "@/components/fiber/FiberConfigForm";
import { PowerEvolutionPlot } from "@/components/plots/PowerEvolutionPlot";
import { ASESpectrumPlot } from "@/components/plots/ASESpectrumPlot";
import { JobProgress } from "@/components/jobs/JobProgress";
import { api } from "@/lib/api";
import { useJobSocket } from "@/lib/ws";
import { useFiberStore } from "@/stores/useFiberStore";
import { useJobsStore } from "@/stores/useJobsStore";
import type {
  PumpConfig, SignalConfig, ASEConfig, PowerASERequest, PowerASEResponse,
} from "@/types/power";
import type { IonKind } from "@/types/fiber";
import { savePreset } from "@/lib/presets";
import { PresetsDialog } from "@/components/common/PresetsDialog";
import { formatNumber, MOD_KEY } from "@/lib/utils";
import type { FiberConfig } from "@/types/fiber";

interface PowerAsePreset {
  fiber: FiberConfig;
  ion: IonKind;
  dopantDensity: number;
  length_m: number;
  pumps: PumpConfig[];
  signals: SignalConfig[];
  ase: ASEConfig;
}

const ION_DEFAULTS: Record<
  IonKind,
  { pump_nm: number; signal_nm: number; aseMin: number; aseMax: number; dopant: number }
> = {
  yb: { pump_nm: 976, signal_nm: 1064, aseMin: 1020, aseMax: 1100, dopant: 1.2e25 },
  er: { pump_nm: 1480, signal_nm: 1550, aseMin: 1520, aseMax: 1620, dopant: 5e24 },
  tm: { pump_nm: 1650, signal_nm: 1900, aseMin: 1800, aseMax: 2050, dopant: 8e24 },
};

const defaultPump = (ion: IonKind = "yb"): PumpConfig => ({
  name: "Pump",
  wavelength_nm: ION_DEFAULTS[ion].pump_nm,
  power_forward_w: 4.0,
  power_backward_w: 0.0,
  overlap: 0.85,
  loss_db_per_m: 0.0,
});
const defaultSignal = (ion: IonKind = "yb"): SignalConfig => ({
  name: "Signal",
  wavelength_nm: ION_DEFAULTS[ion].signal_nm,
  power_forward_w: 0.001,
  power_backward_w: 0.0,
  overlap: 0.85,
  loss_db_per_m: 0.005,
  reflectivity_input: 0.0,
  reflectivity_output: 0.0,
});

export function PowerSimPage() {
  const { fiber, setFiber } = useFiberStore();
  const [ion, setIon] = useState<IonKind>("yb");
  const [dopantDensity, setDopantDensity] = useState(ION_DEFAULTS.yb.dopant);
  const [length_m, setLength] = useState(2.0);
  const [pumps, setPumps] = useState<PumpConfig[]>([defaultPump("yb")]);
  const [signals, setSignals] = useState<SignalConfig[]>([defaultSignal("yb")]);
  const [ase, setASE] = useState<ASEConfig>({
    enabled: true,
    wavelength_min_nm: ION_DEFAULTS.yb.aseMin,
    wavelength_max_nm: ION_DEFAULTS.yb.aseMax,
    num_channels: 30,
    overlap: 0.85,
    loss_db_per_m: 0.005,
  });
  const [showPresets, setShowPresets] = useState(false);

  function applyIonDefaults(nextIon: IonKind) {
    const d = ION_DEFAULTS[nextIon];
    setIon(nextIon);
    setDopantDensity(d.dopant);
    setPumps([defaultPump(nextIon)]);
    setSignals([defaultSignal(nextIon)]);
    setASE((prev) => ({
      ...prev,
      wavelength_min_nm: d.aseMin,
      wavelength_max_nm: d.aseMax,
    }));
  }

  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const sock = useJobSocket<PowerASEResponse>(jobId);
  const pushJob = useJobsStore((s) => s.pushJob);
  const updateJob = useJobsStore((s) => s.updateJob);

  useEffect(() => {
    if (!jobId) return;
    updateJob(jobId, { progress: sock.progress, status: sock.status });
    if (sock.status === "completed") {
      updateJob(jobId, { result: sock.result });
      toast.success("ASE simulation complete");
    } else if (sock.status === "error") {
      updateJob(jobId, { error: sock.error });
      toast.error(sock.error ?? "Simulation failed");
    } else if (sock.status === "cancelled") {
      toast.warning("Simulation cancelled");
    }
  }, [sock, jobId, updateJob]);

  async function runASE() {
    setSubmitting(true);
    try {
      const req: PowerASERequest = {
        active_fiber: {
          geometry: fiber,
          ion,
          dopant_density_per_m3: dopantDensity,
          doping_profile: "uniform",
        },
        length_m,
        pumps,
        signals,
        ase,
        num_z_points: 150,
        max_iterations: 100,
        tolerance: 1e-5,
        relaxation_factor: 0.6,
      };
      const { job_id } = await api.startASE(req);
      pushJob({
        jobId: job_id,
        kind: "ase",
        label: `ASE ${length_m}m ${signals[0]?.wavelength_nm.toFixed(0) ?? ""}nm`,
        config: req,
      });
      setJobId(job_id);
      toast.info("ASE job started");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  useHotkeys("mod+enter", (e) => { e.preventDefault(); if (!submitting) runASE(); },
    [submitting, fiber, ion, dopantDensity, length_m, pumps, signals, ase]);

  function handleSavePreset() {
    const name = prompt("Preset name?", `ASE ${new Date().toLocaleTimeString()}`);
    if (!name) return;
    savePreset<PowerAsePreset>("power-ase", name, { fiber, ion, dopantDensity, length_m, pumps, signals, ase });
    toast.success("Preset saved");
  }

  function handleLoadPreset(config: PowerAsePreset) {
    setFiber(config.fiber);
    setIon(config.ion);
    setDopantDensity(config.dopantDensity);
    setLength(config.length_m);
    setPumps(config.pumps);
    setSignals(config.signals);
    setASE(config.ase);
  }

  const result = sock.result;

  return (
    <div className="container mx-auto py-8 max-w-7xl">
      <PageHeader
        eyebrow="Solver"
        title="Power & ASE"
        description="Steady-state bidirectional rate equations for Yb / Er / Tm doped fibers, with amplified spontaneous emission across a wavelength band."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => setShowPresets(true)}>
              <FolderOpen className="h-3.5 w-3.5" />
              Load preset
            </Button>
            <Button variant="outline" size="sm" onClick={handleSavePreset}>
              <Save className="h-3.5 w-3.5" />
              Save preset
            </Button>
            <Button variant="glow" size="sm" onClick={runASE} disabled={submitting || sock.status === "running"}>
              {(submitting || sock.status === "running") ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              {sock.status === "running" ? "Running..." : "Run ASE"}
              <kbd className="ml-1.5 rounded bg-black/20 px-1.5 py-0.5 text-[10px] font-mono">{MOD_KEY}↵</kbd>
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-4">
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Fiber & active medium</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <FiberConfigForm value={fiber} onChange={setFiber} />
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-1.5">
                  <Label>Active ion</Label>
                  <Select value={ion} onValueChange={(v) => applyIonDefaults(v as IonKind)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="yb">Ytterbium (Yb³⁺) · 900–1100 nm</SelectItem>
                      <SelectItem value="er">Erbium (Er³⁺) · 1450–1650 nm</SelectItem>
                      <SelectItem value="tm">Thulium (Tm³⁺) · 1600–2100 nm</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <NumberField label="Dopant density" unit="ions/m³" step={1e24}
                  value={dopantDensity} onChange={setDopantDensity}
                  hint="~1e25 typical for Yb double-clad" />
                <NumberField label="Fiber length" unit="m" step={0.1} min={0.01}
                  value={length_m} onChange={setLength} />
              </div>
            </CardContent>
          </Card>

          {/* Pumps */}
          <ChannelList
            title="Pumps"
            description="Forward (left) and backward (right) launched at fiber endpoints"
            items={pumps}
            onChange={setPumps}
            defaultItem={() => defaultPump(ion)}
            renderRow={(p, i, onPatch) => (
              <PumpRow key={i} pump={p} onChange={onPatch} />
            )}
          />

          {/* Signals */}
          <ChannelList
            title="Signals"
            description="Reflectivities R₁/R₂ enable laser-cavity simulation"
            items={signals}
            onChange={setSignals}
            defaultItem={() => defaultSignal(ion)}
            renderRow={(s, i, onPatch) => (
              <SignalRow key={i} signal={s} onChange={onPatch} />
            )}
          />

          {/* ASE */}
          <Card>
            <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle className="text-sm">Amplified Spontaneous Emission</CardTitle>
                <CardDescription className="text-xs">Discretize a wavelength band into channels</CardDescription>
              </div>
              <Switch checked={ase.enabled} onCheckedChange={(v) => setASE({ ...ase, enabled: v })} />
            </CardHeader>
            <CardContent className="grid grid-cols-3 gap-4">
              <NumberField label="λ min" unit="nm" step={5} disabled={!ase.enabled}
                value={ase.wavelength_min_nm}
                onChange={(v) => setASE({ ...ase, wavelength_min_nm: v })} />
              <NumberField label="λ max" unit="nm" step={5} disabled={!ase.enabled}
                value={ase.wavelength_max_nm}
                onChange={(v) => setASE({ ...ase, wavelength_max_nm: v })} />
              <NumberField label="Channels" step={1} min={4} max={200} disabled={!ase.enabled}
                value={ase.num_channels}
                onChange={(v) => setASE({ ...ase, num_channels: v })} />
            </CardContent>
          </Card>
        </div>

        {/* Right column: status + summary */}
        <div className="space-y-4">
          {jobId && (
            <JobProgress
              jobId={jobId}
              status={sock.status}
              progress={sock.progress}
              error={sock.error}
            />
          )}

          {result?.summary && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Output metrics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {Object.entries(result.summary).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground capitalize">{k.replace(/_/g, " ")}</span>
                    <Badge variant="accent" className="font-mono">{formatUnits(k, v)}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {!jobId && (
            <Card className="border-dashed">
              <CardContent className="pt-6 text-center text-sm text-muted-foreground">
                Configure channels and press <kbd className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[11px]">{MOD_KEY} Enter</kbd> to run.
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {result && (
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-4 animate-fade-in">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Power evolution along fiber</CardTitle>
            </CardHeader>
            <CardContent>
              <PowerEvolutionPlot response={result} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">ASE output spectrum</CardTitle>
            </CardHeader>
            <CardContent>
              <ASESpectrumPlot response={result} />
            </CardContent>
          </Card>
        </div>
      )}

      <PresetsDialog<PowerAsePreset>
        kind="power-ase"
        open={showPresets}
        onClose={() => setShowPresets(false)}
        onLoad={handleLoadPreset}
      />
    </div>
  );
}

function formatUnits(key: string, value: number): string {
  if (key.endsWith("_w")) return `${formatNumber(value, 4)} W`;
  if (key === "gain_db") return `${formatNumber(value, 2)} dB`;
  if (key === "efficiency") return `${(value * 100).toFixed(2)} %`;
  return formatNumber(value, 4);
}

function ChannelList<T>({
  title, description, items, onChange, defaultItem, renderRow,
}: {
  title: string;
  description: string;
  items: T[];
  onChange: (next: T[]) => void;
  defaultItem: () => T;
  renderRow: (item: T, index: number, onPatch: (patch: Partial<T>) => void, remove: () => void) => React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-sm">{title}</CardTitle>
          <CardDescription className="text-xs">{description}</CardDescription>
        </div>
        <Button
          variant="outline" size="sm"
          onClick={() => onChange([...items, defaultItem()])}
          disabled={items.length >= 4}
        >
          <Plus className="h-3.5 w-3.5" /> Add
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.length === 0 && (
          <div className="text-xs text-muted-foreground text-center py-4">No {title.toLowerCase()} configured</div>
        )}
        {items.map((item, i) => (
          <div key={i} className="relative rounded-lg border border-border bg-card/40 p-3">
            <Button
              variant="ghost" size="icon"
              className="absolute right-2 top-2 h-7 w-7 text-muted-foreground hover:text-destructive"
              onClick={() => onChange(items.filter((_, j) => j !== i))}
              aria-label={`Remove ${title.toLowerCase()} ${i + 1}`}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
            {renderRow(
              item,
              i,
              (patch) => onChange(items.map((it, j) => (j === i ? { ...it, ...patch } : it))),
              () => onChange(items.filter((_, j) => j !== i)),
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function PumpRow({ pump, onChange }: { pump: PumpConfig; onChange: (patch: Partial<PumpConfig>) => void }) {
  return (
    <div className="grid grid-cols-4 gap-3 pr-8">
      <NumberField label="λ" unit="nm" step={1} value={pump.wavelength_nm}
        onChange={(v) => onChange({ wavelength_nm: v })} />
      <NumberField label="P forward" unit="W" step={0.1} min={0}
        value={pump.power_forward_w} onChange={(v) => onChange({ power_forward_w: v })} />
      <NumberField label="P backward" unit="W" step={0.1} min={0}
        value={pump.power_backward_w} onChange={(v) => onChange({ power_backward_w: v })} />
      <NumberField label="Overlap" step={0.05} min={0} max={1}
        value={pump.overlap} onChange={(v) => onChange({ overlap: v })} />
    </div>
  );
}

function SignalRow({ signal, onChange }: { signal: SignalConfig; onChange: (patch: Partial<SignalConfig>) => void }) {
  return (
    <div className="space-y-3 pr-8">
      <div className="grid grid-cols-4 gap-3">
        <NumberField label="λ" unit="nm" step={1}
          value={signal.wavelength_nm} onChange={(v) => onChange({ wavelength_nm: v })} />
        <NumberField label="P forward" unit="W" step={0.001} min={0}
          value={signal.power_forward_w} onChange={(v) => onChange({ power_forward_w: v })} />
        <NumberField label="P backward" unit="W" step={0.001} min={0}
          value={signal.power_backward_w} onChange={(v) => onChange({ power_backward_w: v })} />
        <NumberField label="Overlap" step={0.05} min={0} max={1}
          value={signal.overlap} onChange={(v) => onChange({ overlap: v })} />
      </div>
      <Separator />
      <div className="grid grid-cols-3 gap-3">
        <NumberField label="Loss" unit="dB/m" step={0.001} min={0}
          value={signal.loss_db_per_m} onChange={(v) => onChange({ loss_db_per_m: v })} />
        <NumberField label="R input" step={0.01} min={0} max={1}
          value={signal.reflectivity_input} onChange={(v) => onChange({ reflectivity_input: v })} />
        <NumberField label="R output" step={0.01} min={0} max={1}
          value={signal.reflectivity_output} onChange={(v) => onChange({ reflectivity_output: v })} />
      </div>
    </div>
  );
}
