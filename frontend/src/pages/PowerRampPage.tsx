import { useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { toast } from "sonner";
import { Play, Loader2, Save, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { NumberField } from "@/components/common/NumberField";
import { PageHeader } from "@/components/layout/PageHeader";
import { JobProgress } from "@/components/jobs/JobProgress";
import { PlotlyChart } from "@/components/plots/PlotlyChart";
import { TmiCrossSection } from "@/components/plots/TmiCrossSection";
import { api } from "@/lib/api";
import { useJobSocket } from "@/lib/ws";
import { useJobsStore } from "@/stores/useJobsStore";
import { savePreset } from "@/lib/presets";
import { PresetsDialog } from "@/components/common/PresetsDialog";
import type { EffectSeries, PowerRampRequest, PowerRampResponse } from "@/types/power_ramp";

const defaultRequest: PowerRampRequest = {
  fiber: {
    ion: "yb",
    core_radius_um: 15.0,
    clad_radius_um: 62.5,
    inner_cladding_radius_um: 100.0,
    n_core: 1.46,
    n_clad: 1.454,
    N_total: 3e25,
    tau_ms: 0.84,
    background_loss_db_m: 0.005,
    length_m: 2.0,
  },
  pump_wavelength_nm: 976.0,
  seed_wavelength_nm: 1064.0,
  seed_power_w: 0.01,
  pump_power_min_w: 1.0,
  pump_power_max_w: 200.0,
  num_steps: 20,
};

function statusBadge(value: number, threshold: number | null) {
  if (threshold === null) return null;
  const frac = value / threshold;
  if (frac >= 1.0) return <Badge variant="outline" className="text-red-400 border-red-500/50">crossed</Badge>;
  if (frac >= 0.5) return <Badge variant="outline" className="text-amber-400 border-amber-500/50">approaching</Badge>;
  return <Badge variant="outline" className="text-emerald-400 border-emerald-500/50">safe</Badge>;
}

function findEffect(result: PowerRampResponse, key: string): EffectSeries | undefined {
  return result.effects.find((e) => e.key === key);
}

function NotApplicableCard({ title, reason }: { title: string; reason: string | null }) {
  return (
    <Card className="border-dashed opacity-60">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">N/A — {reason}</p>
      </CardContent>
    </Card>
  );
}

export function PowerRampPage() {
  const [req, setReq] = useState<PowerRampRequest>(defaultRequest);
  const [showPresets, setShowPresets] = useState(false);
  const [powerIndex, setPowerIndex] = useState(0);

  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const sock = useJobSocket<PowerRampResponse>(jobId);
  const pushJob = useJobsStore((s) => s.pushJob);
  const updateJob = useJobsStore((s) => s.updateJob);

  function setFiber<K extends keyof PowerRampRequest["fiber"]>(key: K, value: PowerRampRequest["fiber"][K]) {
    setReq((r) => ({ ...r, fiber: { ...r.fiber, [key]: value } }));
  }
  function set<K extends keyof PowerRampRequest>(key: K, value: PowerRampRequest[K]) {
    setReq((r) => ({ ...r, [key]: value }));
  }

  useEffect(() => {
    if (!jobId) return;
    updateJob(jobId, { progress: sock.progress, status: sock.status });
    if (sock.status === "completed") {
      updateJob(jobId, { result: sock.result });
      setPowerIndex(0);
      toast.success("Power ramp complete");
    } else if (sock.status === "error") {
      updateJob(jobId, { error: sock.error });
      toast.error(sock.error ?? "Simulation failed");
    } else if (sock.status === "cancelled") {
      toast.warning("Simulation cancelled");
    }
  }, [sock, jobId, updateJob]);

  async function runRamp() {
    setSubmitting(true);
    try {
      const { job_id } = await api.startPowerRamp(req);
      pushJob({
        jobId: job_id,
        kind: "power_ramp",
        label: `Power ramp ${req.fiber.ion} ${req.pump_power_min_w}-${req.pump_power_max_w}W`,
        config: req,
      });
      setJobId(job_id);
      toast.info("Power ramp job started");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  useHotkeys("mod+enter", (e) => {
    e.preventDefault();
    if (!submitting) runRamp();
  }, [submitting, req]);

  function handleSavePreset() {
    const name = prompt("Preset name?", `Power Ramp ${new Date().toLocaleTimeString()}`);
    if (!name) return;
    savePreset<PowerRampRequest>("power_ramp", name, req);
    toast.success("Preset saved");
  }

  const result = sock.result;
  const currentPower = result?.pump_power_w[powerIndex];

  return (
    <div className="container mx-auto py-8 max-w-7xl">
      <PageHeader
        eyebrow="Solver"
        title="Power Ramp — Nonlinear Effects Explorer"
        description="Sweep pump power for a single fiber and watch SRS, SBS, photodarkening, TMI, and Tm/Er ESA-upconversion approach their limits — each fiber is re-solved in isolation at every power step (not a full cavity/system), the same fast diagnostic-level approximation already used for the System Builder's per-fiber thresholds."
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
              onClick={runRamp}
              disabled={submitting || sock.status === "running"}
            >
              {submitting || sock.status === "running" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
              {sock.status === "running" ? "Sweeping..." : "Run sweep"}
              <kbd className="ml-1.5 rounded bg-black/20 px-1.5 py-0.5 text-[10px] font-mono">⌘↵</kbd>
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-4">
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Fiber</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5 max-w-[200px]">
                <Label className="text-xs">Active ion</Label>
                <Select value={req.fiber.ion} onValueChange={(v) => setFiber("ion", v as PowerRampRequest["fiber"]["ion"])}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="yb">Yb³⁺ (1030-1100 nm)</SelectItem>
                    <SelectItem value="er">Er³⁺ (1530-1610 nm)</SelectItem>
                    <SelectItem value="tm">Tm³⁺ (1850-2050 nm)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <NumberField label="Core radius" unit="µm" step={0.5} min={0.1} value={req.fiber.core_radius_um} onChange={(v) => setFiber("core_radius_um", v)} />
                <NumberField label="Clad radius" unit="µm" step={0.5} min={1} value={req.fiber.clad_radius_um} onChange={(v) => setFiber("clad_radius_um", v)} />
                <NumberField label="Inner clad (double-clad)" unit="µm" step={1} min={0}
                  value={req.fiber.inner_cladding_radius_um ?? 0}
                  onChange={(v) => setFiber("inner_cladding_radius_um", v > 0 ? v : null)} />
                <NumberField label="Length" unit="m" step={0.1} min={0.01} value={req.fiber.length_m} onChange={(v) => setFiber("length_m", v)} />
                <NumberField label="Core index" step={0.0001} value={req.fiber.n_core} onChange={(v) => setFiber("n_core", v)} />
                <NumberField label="Clad index" step={0.0001} value={req.fiber.n_clad} onChange={(v) => setFiber("n_clad", v)} />
                <NumberField label="Dopant density" unit="ions/m³" step={1e24} value={req.fiber.N_total} onChange={(v) => setFiber("N_total", v)} />
                <NumberField label="Upper-state lifetime" unit="ms" step={0.01} min={0.001} value={req.fiber.tau_ms} onChange={(v) => setFiber("tau_ms", v)} />
                <NumberField label="Background loss" unit="dB/m" step={0.001} min={0} value={req.fiber.background_loss_db_m} onChange={(v) => setFiber("background_loss_db_m", v)} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Pump &amp; seed</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <NumberField label="Pump wavelength" unit="nm" step={1} value={req.pump_wavelength_nm} onChange={(v) => set("pump_wavelength_nm", v)} />
              <NumberField label="Seed wavelength" unit="nm" step={1} value={req.seed_wavelength_nm} onChange={(v) => set("seed_wavelength_nm", v)} />
              <NumberField label="Seed power" unit="W" step={0.001} min={0.0001} value={req.seed_power_w} onChange={(v) => set("seed_power_w", v)} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Power sweep</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <NumberField label="Pump power min" unit="W" step={1} min={0.001} value={req.pump_power_min_w} onChange={(v) => set("pump_power_min_w", v)} />
              <NumberField label="Pump power max" unit="W" step={1} min={0.001} value={req.pump_power_max_w} onChange={(v) => set("pump_power_max_w", v)} />
              <NumberField label="Steps" step={1} min={5} max={60} value={req.num_steps} onChange={(v) => set("num_steps", Math.round(v))} />
            </CardContent>
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
                Set the fiber and power range and press{" "}
                <kbd className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[11px]">⌘ Enter</kbd>.
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {result && (
        <div className="mt-6 space-y-4 animate-fade-in">
          <Card>
            <CardContent className="pt-6 space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Pump power (drives every panel below)</span>
                <span className="font-mono">{currentPower?.toFixed(2)} W</span>
              </div>
              <Slider
                min={0}
                max={result.pump_power_w.length - 1}
                step={1}
                value={[powerIndex]}
                onValueChange={(v) => setPowerIndex(v[0])}
              />
            </CardContent>
          </Card>

          {(() => {
            const srs = findEffect(result, "srs");
            const sbs = findEffect(result, "sbs");
            if (!srs?.applicable) {
              return <NotApplicableCard title="SRS / SBS" reason={srs?.reason ?? null} />;
            }
            const srsVal = srs.values[powerIndex];
            const sbsVal = sbs?.values[powerIndex] ?? null;
            return (
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-sm">SRS / SBS — peak signal power vs. thresholds</CardTitle>
                      <CardDescription className="text-xs">
                        Stimulated Raman/Brillouin scattering: peak signal power compared against each effect's own Watts threshold
                      </CardDescription>
                    </div>
                    <div className="flex gap-1.5">
                      {sbsVal !== null && statusBadge(sbsVal * (result.sbs_threshold_w ?? 1), result.sbs_threshold_w)}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <PlotlyChart
                    height={260}
                    exportFilename="power_ramp_srs_sbs"
                    data={[
                      {
                        x: result.pump_power_w, y: result.peak_signal_power_w,
                        type: "scatter", mode: "lines", name: "peak signal power",
                        line: { color: "#34d399", width: 2.5 },
                      },
                      ...(result.sbs_threshold_w ? [{
                        x: result.pump_power_w, y: result.pump_power_w.map(() => result.sbs_threshold_w as number),
                        type: "scatter" as const, mode: "lines" as const, name: "SBS threshold",
                        line: { color: "#D946EF", width: 1.5, dash: "dash" as const },
                      }] : []),
                      ...(result.srs_threshold_w ? [{
                        x: result.pump_power_w, y: result.pump_power_w.map(() => result.srs_threshold_w as number),
                        type: "scatter" as const, mode: "lines" as const, name: "SRS threshold",
                        line: { color: "#22D3EE", width: 1.5, dash: "dash" as const },
                      }] : []),
                      {
                        x: [currentPower ?? 0], y: [srsVal !== null ? result.peak_signal_power_w[powerIndex] : 0],
                        type: "scatter", mode: "markers", name: "current power", showlegend: false,
                        marker: { color: "#FBBF24", size: 9, symbol: "diamond" },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Pump power (W)" } },
                      yaxis: { title: { text: "Power (W) — log scale" }, type: "log" },
                      legend: { orientation: "h", y: -0.25 },
                      margin: { t: 8, r: 8, b: 44, l: 56 },
                    }}
                  />
                  <p className="text-xs font-mono mt-2 text-center">
                    Signal = {result.peak_signal_power_w[powerIndex]?.toFixed(3)} W
                    {result.srs_threshold_w !== null && <> · SRS threshold = {result.srs_threshold_w.toFixed(1)} W</>}
                    {result.sbs_threshold_w !== null && <> · SBS threshold = {result.sbs_threshold_w.toFixed(2)} W</>}
                    {" "}at {currentPower?.toFixed(1)} W pump
                  </p>
                </CardContent>
              </Card>
            );
          })()}

          {(() => {
            const pd = findEffect(result, "photodarkening");
            if (!pd?.applicable) return <NotApplicableCard title="Photodarkening" reason={pd?.reason ?? null} />;
            const val = pd.values[powerIndex];
            return (
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-sm">Photodarkening — extra saturated loss vs. pump power</CardTitle>
                      <CardDescription className="text-xs">Yb-specific induced loss at full time-saturation (not a real-time kinetic model — see solvers/photodarkening.py)</CardDescription>
                    </div>
                    {val !== null && statusBadge(val, pd.threshold)}
                  </div>
                </CardHeader>
                <CardContent>
                  <PlotlyChart
                    height={220}
                    exportFilename="power_ramp_photodarkening"
                    data={[
                      {
                        x: result.pump_power_w, y: pd.values,
                        type: "scatter", mode: "lines", name: "extra loss",
                        line: { color: "#FB923C", width: 2.5 },
                        fill: "tozeroy", fillcolor: "rgba(251, 146, 60, 0.12)",
                      },
                      {
                        x: result.pump_power_w, y: result.pump_power_w.map(() => pd.threshold ?? 1),
                        type: "scatter", mode: "lines", name: "significant (1 dB)",
                        line: { color: "rgba(240, 80, 80, 0.6)", width: 1.5, dash: "dash" },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Pump power (W)" } },
                      yaxis: { title: { text: "Extra loss (dB)" } },
                      legend: { orientation: "h", y: -0.3 },
                      margin: { t: 8, r: 8, b: 44, l: 56 },
                    }}
                  />
                  <p className="text-xs font-mono mt-2 text-center">
                    Extra loss = {val?.toFixed(3)} dB at {currentPower?.toFixed(1)} W pump (significant above {pd.threshold} dB)
                  </p>
                </CardContent>
              </Card>
            );
          })()}

          {(() => {
            const tmi = findEffect(result, "tmi");
            if (!tmi?.applicable || !result.tmi_lp01_image) {
              return <NotApplicableCard title="TMI (transverse mode instability)" reason={tmi?.reason ?? null} />;
            }
            const m2x = result.tmi_m2x[powerIndex];
            const m2y = result.tmi_m2y[powerIndex];
            const coupling = result.tmi_coupling_fraction[powerIndex];
            const riskFraction = tmi.values[powerIndex];
            return (
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-sm">TMI — beam quality degradation vs. pump power</CardTitle>
                      <CardDescription className="text-xs">
                        Real ISO 11146 M² of an LP01/LP11 mode mixture, blended by a coupling fraction derived from the TMI risk fraction — a documented heuristic, not a validated coupled-mode dynamics simulation
                      </CardDescription>
                    </div>
                    <Badge variant="outline" className={coupling > 0.15 ? "text-amber-400 border-amber-500/50" : ""}>
                      {(coupling * 100).toFixed(0)}% LP11 admixture
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">M² vs pump power</p>
                      <PlotlyChart
                        height={220}
                        exportFilename="power_ramp_tmi_m2"
                        data={[
                          {
                            x: result.pump_power_w, y: result.tmi_m2x,
                            type: "scatter", mode: "lines", name: "M²x",
                            line: { color: "#A78BFA", width: 2.5 },
                          },
                          {
                            x: result.pump_power_w, y: result.tmi_m2y,
                            type: "scatter", mode: "lines", name: "M²y",
                            line: { color: "#22D3EE", width: 2.5 },
                          },
                          {
                            x: [currentPower ?? 0], y: [m2x ?? 0],
                            type: "scatter", mode: "markers", showlegend: false,
                            marker: { color: "#FBBF24", size: 9, symbol: "diamond" },
                          },
                        ]}
                        layout={{
                          xaxis: { title: { text: "Pump power (W)" } },
                          yaxis: { title: { text: "M²" } },
                          legend: { orientation: "h", y: -0.3 },
                          margin: { t: 8, r: 8, b: 44, l: 56 },
                        }}
                      />
                      <p className="text-xs font-mono mt-2 text-center">
                        M²x = {m2x?.toFixed(2)} · M²y = {m2y?.toFixed(2)} · risk fraction = {riskFraction?.toFixed(3)} at {currentPower?.toFixed(1)} W
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                        Fiber facet cross-section at this power
                      </p>
                      <TmiCrossSection
                        lp01Image={result.tmi_lp01_image}
                        lp11Image={result.tmi_lp11_image}
                        xUm={result.tmi_image_x_um}
                        yUm={result.tmi_image_y_um}
                        couplingFraction={coupling}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })()}

          {(() => {
            const esa = findEffect(result, "esa_upconversion");
            if (!esa?.applicable) return <NotApplicableCard title="ESA / upconversion" reason={esa?.reason ?? null} />;
            if (req.fiber.ion === "tm") {
              return (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Tm³⁺ cross-relaxation</CardTitle>
                    <CardDescription className="text-xs">
                      "2-for-1" upconversion pumping — each absorbed 790 nm pump photon excites this many ions on average (constant, doesn't vary with pump power)
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Badge variant="outline" className="text-primary border-primary/50 text-sm">
                      cross-relaxation yield: {esa.values[0]?.toFixed(2)}×
                    </Badge>
                  </CardContent>
                </Card>
              );
            }
            return (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Er³⁺ upconversion activity vs. pump power</CardTitle>
                  <CardDescription className="text-xs">
                    Peak excited-state (N2) population fraction — the quantity driving cooperative-upconversion quenching (∝ N2²), not a Watts threshold
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <PlotlyChart
                    height={220}
                    exportFilename="power_ramp_er_upconversion"
                    data={[
                      {
                        x: result.pump_power_w, y: esa.values,
                        type: "scatter", mode: "lines",
                        line: { color: "#2dd4bf", width: 2.5 },
                        fill: "tozeroy", fillcolor: "rgba(45, 212, 191, 0.12)",
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Pump power (W)" } },
                      yaxis: { title: { text: "Peak N2 fraction" }, range: [0, 1] },
                      margin: { t: 8, r: 8, b: 44, l: 56 },
                      showlegend: false,
                    }}
                  />
                  <p className="text-xs font-mono mt-2 text-center">
                    Peak N2 fraction = {esa.values[powerIndex]?.toFixed(4)} at {currentPower?.toFixed(1)} W pump
                  </p>
                </CardContent>
              </Card>
            );
          })()}
        </div>
      )}

      <PresetsDialog<PowerRampRequest>
        kind="power_ramp"
        open={showPresets}
        onClose={() => setShowPresets(false)}
        onLoad={(config) => setReq(config)}
      />
    </div>
  );
}
