import { useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { toast } from "sonner";
import { Play, Loader2, Save, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { NumberField } from "@/components/common/NumberField";
import { PageHeader } from "@/components/layout/PageHeader";
import { JobProgress } from "@/components/jobs/JobProgress";
import { GNLSEHeatmap } from "@/components/plots/GNLSEHeatmap";
import { GNLSEProfileComparison } from "@/components/plots/GNLSEProfileComparison";
import { api } from "@/lib/api";
import { useJobSocket } from "@/lib/ws";
import { useJobsStore } from "@/stores/useJobsStore";
import { savePreset } from "@/lib/presets";
import { PresetsDialog } from "@/components/common/PresetsDialog";
import type { GNLSERequest, GNLSEResponse } from "@/types/gnlse";

const defaultRequest: GNLSERequest = {
  pulse_shape: "sech2",
  wavelength_nm: 1550.0,
  peak_power_w: 1000.0,
  duration_fs: 100.0,
  time_window_ps: 10.0,
  num_points: 2048,

  length_mm: 10.0,
  gamma_per_w_per_km: 1.3,
  beta2_ps2_per_km: -20.0,
  beta3_ps3_per_km: 0.0,
  loss_db_per_m: 0.0,
  self_steepening: true,
  raman: true,

  enable_gain: false,
  small_signal_gain_db_per_m: 5.0,
  saturation_energy_nj: 50.0,
  gain_bandwidth_nm: null,

  z_steps: 300,
  save_z_slices: 60,
};

export function GNLSEPage() {
  const [req, setReq] = useState<GNLSERequest>(defaultRequest);
  const [showPresets, setShowPresets] = useState(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const sock = useJobSocket<GNLSEResponse>(jobId);
  const pushJob = useJobsStore((s) => s.pushJob);
  const updateJob = useJobsStore((s) => s.updateJob);

  function set<K extends keyof GNLSERequest>(key: K, value: GNLSERequest[K]) {
    setReq((r) => ({ ...r, [key]: value }));
  }

  useEffect(() => {
    if (!jobId) return;
    updateJob(jobId, { progress: sock.progress, status: sock.status });
    if (sock.status === "completed") {
      updateJob(jobId, { result: sock.result });
      toast.success("Pulse propagation complete");
    } else if (sock.status === "error") {
      updateJob(jobId, { error: sock.error });
      toast.error(sock.error ?? "Simulation failed");
    } else if (sock.status === "cancelled") {
      toast.warning("Simulation cancelled");
    }
  }, [sock, jobId, updateJob]);

  async function runGnlse() {
    setSubmitting(true);
    try {
      const { job_id } = await api.startGNLSE(req);
      pushJob({
        jobId: job_id,
        kind: "gnlse",
        label: `GNLSE ${req.duration_fs}fs, ${req.length_mm}mm${req.enable_gain ? " +gain" : ""}`,
        config: req,
      });
      setJobId(job_id);
      toast.info("Pulse propagation job started");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  useHotkeys("mod+enter", (e) => {
    e.preventDefault();
    if (!submitting) runGnlse();
  }, [submitting, req]);

  function handleSavePreset() {
    const name = prompt("Preset name?", `GNLSE ${new Date().toLocaleTimeString()}`);
    if (!name) return;
    savePreset<GNLSERequest>("gnlse", name, req);
    toast.success("Preset saved");
  }

  const result = sock.result;

  return (
    <div className="container mx-auto py-8 max-w-7xl">
      <PageHeader
        eyebrow="Solver"
        title="Ultrafast Pulse Propagation (GNLSE)"
        description="Generalized Nonlinear Schrödinger Equation solver — split-step Fourier with Raman scattering, self-steepening, and higher-order dispersion. Optionally couple a saturable rate-equation gain to model a single pass through a pulsed fiber amplifier."
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
              onClick={runGnlse}
              disabled={submitting || sock.status === "running"}
            >
              {submitting || sock.status === "running" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
              {sock.status === "running" ? "Propagating..." : "Propagate"}
              <kbd className="ml-1.5 rounded bg-black/20 px-1.5 py-0.5 text-[10px] font-mono">⌘↵</kbd>
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-4">
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Input pulse</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5 max-w-[220px]">
                <Label className="text-xs">Pulse shape</Label>
                <Select value={req.pulse_shape} onValueChange={(v) => set("pulse_shape", v as GNLSERequest["pulse_shape"])}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sech2">Sech² (soliton-like)</SelectItem>
                    <SelectItem value="gaussian">Gaussian</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <NumberField label="Wavelength" unit="nm" step={1} value={req.wavelength_nm} onChange={(v) => set("wavelength_nm", v)} />
                <NumberField label="Peak power" unit="W" step={10} min={0.001} value={req.peak_power_w} onChange={(v) => set("peak_power_w", v)} />
                <NumberField label="Duration (FWHM)" unit="fs" step={5} min={0.1} value={req.duration_fs} onChange={(v) => set("duration_fs", v)} />
                <NumberField label="Time window" unit="ps" step={1} min={0.01} value={req.time_window_ps} onChange={(v) => set("time_window_ps", v)} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Fiber parameters</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <NumberField label="Length" unit="mm" step={1} min={0.01} value={req.length_mm} onChange={(v) => set("length_mm", v)} />
              <NumberField label="γ (nonlinear)" unit="1/W/km" step={0.1} value={req.gamma_per_w_per_km} onChange={(v) => set("gamma_per_w_per_km", v)} />
              <NumberField label="β2" unit="ps²/km" step={1} value={req.beta2_ps2_per_km} onChange={(v) => set("beta2_ps2_per_km", v)} />
              <NumberField label="β3" unit="ps³/km" step={0.01} value={req.beta3_ps3_per_km} onChange={(v) => set("beta3_ps3_per_km", v)} />
              <NumberField label="Loss" unit="dB/m" step={0.001} min={0} value={req.loss_db_per_m} onChange={(v) => set("loss_db_per_m", v)} />
              <NumberField label="Z steps" step={20} min={20} max={2000} value={req.z_steps} onChange={(v) => set("z_steps", v)} />
              <div className="flex items-center gap-2 pt-5">
                <Switch checked={req.self_steepening} onCheckedChange={(v) => set("self_steepening", v)} />
                <Label className="text-xs">Self-steepening</Label>
              </div>
              <div className="flex items-center gap-2 pt-5">
                <Switch checked={req.raman} onCheckedChange={(v) => set("raman", v)} />
                <Label className="text-xs">Raman scattering</Label>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm">Saturable gain (pulsed amplifier)</CardTitle>
                  <CardDescription className="text-xs mt-1">
                    Gain is frozen for the whole pass and energy-saturated by the input pulse —
                    the upper-state lifetime (~ms) can't respond to a fs/ps pulse's own sub-structure.
                  </CardDescription>
                </div>
                <Switch checked={req.enable_gain} onCheckedChange={(v) => set("enable_gain", v)} />
              </div>
            </CardHeader>
            {req.enable_gain && (
              <CardContent className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <NumberField label="Small-signal gain" unit="dB/m" step={0.1} min={0} value={req.small_signal_gain_db_per_m} onChange={(v) => set("small_signal_gain_db_per_m", v)} />
                <NumberField label="Saturation energy" unit="nJ" step={1} min={0.001}
                  value={req.saturation_energy_nj ?? 0}
                  onChange={(v) => set("saturation_energy_nj", v)} />
                <NumberField label="Gain bandwidth" unit="nm" step={1} min={0.001}
                  value={req.gain_bandwidth_nm ?? 0}
                  onChange={(v) => set("gain_bandwidth_nm", v)} />
              </CardContent>
            )}
          </Card>
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
                Set the pulse and fiber parameters and press{" "}
                <kbd className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[11px]">⌘ Enter</kbd>.
              </CardContent>
            </Card>
          )}

          {result && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Pulse energy</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Input</span>
                  <span className="font-mono">{result.input_energy_nj.toFixed(3)} nJ</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Output</span>
                  <span className="font-mono">{result.output_energy_nj.toFixed(3)} nJ</span>
                </div>
                {result.saturated_gain_db_per_m !== null && (
                  <div className="pt-1">
                    <Badge variant="outline" className="text-primary border-primary/50">
                      saturated gain {result.saturated_gain_db_per_m.toFixed(2)} dB/m
                    </Badge>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {result && (
        <div className="mt-6 space-y-4 animate-fade-in">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Temporal power evolution |A(t, z)|²</CardTitle>
              <CardDescription className="text-xs">How the pulse envelope reshapes along the fiber</CardDescription>
            </CardHeader>
            <CardContent>
              <GNLSEHeatmap
                z_mm={result.z_mm}
                xAxis={result.t_ps}
                xLabel="t (ps)"
                slices={result.temporal_power_slices}
                zLabel="Power (W)"
                exportFilename="gnlse_temporal_evolution"
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Spectral power evolution</CardTitle>
              <CardDescription className="text-xs">Spectral broadening from SPM, Raman shift, and dispersion</CardDescription>
            </CardHeader>
            <CardContent>
              <GNLSEHeatmap
                z_mm={result.z_mm}
                xAxis={result.wavelength_nm}
                xLabel="Wavelength (nm)"
                slices={result.spectral_power_slices}
                zLabel="Power (a.u.)"
                exportFilename="gnlse_spectral_evolution"
              />
            </CardContent>
          </Card>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Temporal profile: input vs output</CardTitle>
              </CardHeader>
              <CardContent>
                <GNLSEProfileComparison
                  xAxis={result.t_ps}
                  xLabel="t (ps)"
                  yLabel="Power (W)"
                  inputValues={result.input_temporal_power_w}
                  outputValues={result.output_temporal_power_w}
                  exportFilename="gnlse_temporal_profile"
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Spectral profile: input vs output</CardTitle>
              </CardHeader>
              <CardContent>
                <GNLSEProfileComparison
                  xAxis={result.wavelength_nm}
                  xLabel="Wavelength (nm)"
                  yLabel="Power (a.u.)"
                  inputValues={result.input_spectral_power}
                  outputValues={result.output_spectral_power}
                  exportFilename="gnlse_spectral_profile"
                />
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      <PresetsDialog<GNLSERequest>
        kind="gnlse"
        open={showPresets}
        onClose={() => setShowPresets(false)}
        onLoad={(config) => setReq(config)}
      />
    </div>
  );
}
