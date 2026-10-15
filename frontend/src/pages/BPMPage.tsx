import { useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { toast } from "sonner";
import { Play, Loader2, Save, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { NumberField } from "@/components/common/NumberField";
import { PageHeader } from "@/components/layout/PageHeader";
import { FiberConfigForm } from "@/components/fiber/FiberConfigForm";
import { IndexProfilePreview } from "@/components/fiber/IndexProfilePreview";
import { BPMZSlice } from "@/components/plots/BPMZSlice";
import { BPMPowerVsZ } from "@/components/plots/BPMPowerVsZ";
import { BPMLongitudinalSlice } from "@/components/plots/BPMLongitudinalSlice";
import { JobProgress } from "@/components/jobs/JobProgress";
import { api } from "@/lib/api";
import { useJobSocket } from "@/lib/ws";
import { useFiberStore } from "@/stores/useFiberStore";
import { useJobsStore } from "@/stores/useJobsStore";
import type { BPMRequest, BPMResponse, InitialFieldConfig } from "@/types/bpm";
import { savePreset } from "@/lib/presets";
import { PresetsDialog } from "@/components/common/PresetsDialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import type { FiberConfig } from "@/types/fiber";

import { MOD_KEY } from "@/lib/utils";
interface BpmPreset {
  fiber: FiberConfig;
  wavelength_nm: number;
  length_mm: number;
  gridSize: number;
  zSteps: number;
  initial: InitialFieldConfig;
}

const defaultInitial: InitialFieldConfig = {
  kind: "gaussian",
  waist_um: 4.0,
  x_offset_um: 0.0,
  y_offset_um: 0.0,
  tilt_x_mrad: 0.0,
  tilt_y_mrad: 0.0,
};

export function BPMPage() {
  const { fiber, setFiber, wavelength_nm, setWavelength } = useFiberStore();
  const [length_mm, setLength] = useState(10.0);
  const [gridSize, setGridSize] = useState(64);
  const [zSteps, setZSteps] = useState(200);
  const [initial, setInitial] = useState<InitialFieldConfig>(defaultInitial);
  const [showPresets, setShowPresets] = useState(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const sock = useJobSocket<BPMResponse>(jobId);
  const pushJob = useJobsStore((s) => s.pushJob);
  const updateJob = useJobsStore((s) => s.updateJob);

  useEffect(() => {
    if (!jobId) return;
    updateJob(jobId, { progress: sock.progress, status: sock.status });
    if (sock.status === "completed") {
      updateJob(jobId, { result: sock.result });
      toast.success("BPM simulation complete");
    } else if (sock.status === "error") {
      updateJob(jobId, { error: sock.error });
      toast.error(sock.error ?? "Simulation failed");
    } else if (sock.status === "cancelled") {
      toast.warning("Simulation cancelled");
    }
  }, [sock, jobId, updateJob]);

  async function runBPM() {
    setSubmitting(true);
    try {
      const req: BPMRequest = {
        fiber,
        wavelength_nm,
        length_mm,
        initial_field: initial,
        grid_size: gridSize,
        z_steps: zSteps,
        grid_width_factor: 3.0,
        save_z_slices: 60,
      };
      const { job_id } = await api.startBPM(req);
      pushJob({
        jobId: job_id,
        kind: "bpm",
        label: `BPM ${length_mm}mm ${gridSize}²`,
        config: req,
      });
      setJobId(job_id);
      toast.info("BPM job started");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  useHotkeys("mod+enter", (e) => {
    e.preventDefault();
    if (!submitting) runBPM();
  }, [submitting, fiber, wavelength_nm, length_mm, gridSize, zSteps, initial]);

  function handleSavePreset() {
    const name = prompt("Preset name?", `BPM ${new Date().toLocaleTimeString()}`);
    if (!name) return;
    savePreset<BpmPreset>("bpm", name, { fiber, wavelength_nm, length_mm, gridSize, zSteps, initial });
    toast.success("Preset saved");
  }

  function handleLoadPreset(config: BpmPreset) {
    setFiber(config.fiber);
    setWavelength(config.wavelength_nm);
    setLength(config.length_mm);
    setGridSize(config.gridSize);
    setZSteps(config.zSteps);
    setInitial(config.initial);
  }

  const result = sock.result;

  return (
    <div className="container mx-auto py-8 max-w-7xl">
      <PageHeader
        eyebrow="Solver"
        title="Beam Propagation (BPM)"
        description="Paraxial split-step Fourier propagator. Watch a launched field evolve along the fiber — perfect for studying tapers, bends, mismatched launches, and double-clad geometries."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => setShowPresets(true)}>
              <FolderOpen className="h-3.5 w-3.5" /> Load preset
            </Button>
            <Button variant="outline" size="sm" onClick={handleSavePreset}>
              <Save className="h-3.5 w-3.5" /> Save preset
            </Button>
            <Button
              variant="glow"
              size="sm"
              onClick={runBPM}
              disabled={submitting || sock.status === "running"}
            >
              {submitting || sock.status === "running" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
              {sock.status === "running" ? "Propagating..." : "Propagate"}
              <kbd className="ml-1.5 rounded bg-black/20 px-1.5 py-0.5 text-[10px] font-mono">{MOD_KEY}↵</kbd>
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-4">
        <div className="space-y-4">
          <FiberConfigForm value={fiber} onChange={setFiber} />

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Propagation parameters</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <NumberField label="Wavelength" unit="nm" step={1}
                value={wavelength_nm} onChange={setWavelength} />
              <NumberField label="Length" unit="mm" step={0.5} min={0.01}
                value={length_mm} onChange={setLength} />
              <NumberField label="Grid size" unit="px²" step={8} min={32} max={192}
                value={gridSize} onChange={setGridSize} />
              <NumberField label="Z steps" step={20} min={20} max={2000}
                value={zSteps} onChange={setZSteps} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Initial launched field</CardTitle>
              <CardDescription className="text-xs">
                Offset and tilt the launch beam, or select the fundamental mode profile
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5 max-w-[220px]">
                <Label className="text-xs">Field Type</Label>
                <Select
                  value={initial.kind}
                  onValueChange={(v) => setInitial({ ...initial, kind: v as "gaussian" | "fundamental_mode" })}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="gaussian">Gaussian Beam</SelectItem>
                    <SelectItem value="fundamental_mode">Fundamental Mode (LP01)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <NumberField
                  label="Waist"
                  unit="µm"
                  step={0.1}
                  value={initial.waist_um}
                  disabled={initial.kind === "fundamental_mode"}
                  onChange={(v) => setInitial({ ...initial, waist_um: v })}
                />
                <NumberField label="x offset" unit="µm" step={0.1}
                  value={initial.x_offset_um}
                  onChange={(v) => setInitial({ ...initial, x_offset_um: v })} />
                <NumberField label="y offset" unit="µm" step={0.1}
                  value={initial.y_offset_um}
                  onChange={(v) => setInitial({ ...initial, y_offset_um: v })} />
                <NumberField label="x tilt" unit="mrad" step={0.1}
                  value={initial.tilt_x_mrad}
                  onChange={(v) => setInitial({ ...initial, tilt_x_mrad: v })} />
                <NumberField label="y tilt" unit="mrad" step={0.1}
                  value={initial.tilt_y_mrad}
                  onChange={(v) => setInitial({ ...initial, tilt_y_mrad: v })} />
              </div>
            </CardContent>
          </Card>

          <IndexProfilePreview fiber={fiber} wavelength_nm={wavelength_nm} />
        </div>

        <div className="space-y-4">
          {jobId && (
            <JobProgress
              jobId={jobId}
              status={sock.status}
              progress={sock.progress}
              error={sock.error}
            />
          )}

          {!jobId && (
            <Card className="border-dashed">
              <CardContent className="pt-6 text-center text-sm text-muted-foreground">
                Set the launched field and press{" "}
                <kbd className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[11px]">{MOD_KEY} Enter</kbd>.
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {result && (
        <div className="mt-6 space-y-4 animate-fade-in">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Longitudinal field propagation |E(y, z)|²</CardTitle>
              <CardDescription className="text-xs">
                Light intensity profile through the central YZ plane of the fiber waveguide
              </CardDescription>
            </CardHeader>
            <CardContent>
              <BPMLongitudinalSlice response={result} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Field intensity slice |E(x, y)|²</CardTitle>
              <CardDescription className="text-xs">
                Drag the slider to sweep along the propagation axis
              </CardDescription>
            </CardHeader>
            <CardContent>
              <BPMZSlice response={result} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Total power vs z</CardTitle>
              <CardDescription className="text-xs">
                Monitor leakage to the cladding / absorber
              </CardDescription>
            </CardHeader>
            <CardContent>
              <BPMPowerVsZ response={result} />
            </CardContent>
          </Card>
        </div>
      )}

      <PresetsDialog<BpmPreset>
        kind="bpm"
        open={showPresets}
        onClose={() => setShowPresets(false)}
        onLoad={handleLoadPreset}
      />
    </div>
  );
}
