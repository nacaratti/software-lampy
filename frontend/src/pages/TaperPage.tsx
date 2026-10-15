import { useState } from "react";
import { toast } from "sonner";
import { Play, Loader2, Info, Triangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { NumberField } from "@/components/common/NumberField";
import { PageHeader } from "@/components/layout/PageHeader";
import { PlotlyChart } from "@/components/plots/PlotlyChart";
import { api } from "@/lib/api";
import { useSyncJob } from "@/lib/syncJob";
import type { TaperCalculationResponse } from "@/types/taper";

type TaperShape = "cosine" | "linear" | "exponential";

export function TaperPage() {
  // Fiber
  const [coreRadius, setCoreRadius] = useState(4.0);
  const [cladRadius, setCladRadius] = useState(62.5);
  const [nCore, setNCore] = useState(1.4681);
  const [nClad, setNClad] = useState(1.4629);

  // Taper geometry
  const [taperRatio, setTaperRatio] = useState(0.1);
  const [Ltaper, setLtaper] = useState(30.0);
  const [Lwaist, setLwaist] = useState(5.0);
  const [shape, setShape] = useState<TaperShape>("cosine");

  // Optical
  const [lambda, setLambda] = useState(1550.0);

  // Grid
  const [numZ, setNumZ] = useState(800);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TaperCalculationResponse | null>(null);
  const runSync = useSyncJob();

  const NA = Math.sqrt(Math.max(nCore ** 2 - nClad ** 2, 0));
  const V_in = (2 * Math.PI / (lambda * 1e-9)) * (coreRadius * 1e-6) * NA;
  const V_waist_est = V_in * taperRatio;

  async function runSimulation() {
    if (nCore <= nClad) { toast.error("n_core must be greater than n_clad"); return; }
    if (cladRadius <= coreRadius) { toast.error("Cladding radius must exceed core radius"); return; }

    setLoading(true);
    const req = {
      core_radius_um: coreRadius,
      clad_radius_um: cladRadius,
      n_core: nCore,
      n_clad: nClad,
      taper_ratio: taperRatio,
      L_taper_mm: Ltaper,
      L_waist_mm: Lwaist,
      taper_shape: shape,
      lambda_nm: lambda,
      num_z: numZ,
    };
    try {
      const res = await runSync(
        "taper",
        `Taper ${shape} ${Ltaper}mm`,
        req,
        () => api.calculateTaper(req)
      );
      setResult(res);
      toast.success("Taper analysis complete");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container mx-auto py-8 max-w-7xl">
      <PageHeader
        eyebrow="Solver"
        title="Tapered Fiber"
        description="Biconical taper profile with adiabaticity analysis (Love & Henry criterion). Tracks LP₀₁ mode field diameter evolution using three definitions (second-moment, effective area, HWHM) plus V-parameter, beat length, and estimated transmission."
        actions={
          <Button variant="glow" size="sm" onClick={runSimulation} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {loading ? "Analyzing..." : "Run Analysis"}
          </Button>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* ── Inputs ── */}
        <div className="xl:col-span-4 space-y-4">

          {/* Fiber */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Fiber Parameters</CardTitle>
              <CardDescription className="text-xs">Step-index single-mode fiber</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              <NumberField
                label="Core Radius"
                unit="μm"
                step={0.5}
                min={0.1}
                max={100.0}
                value={coreRadius}
                onChange={setCoreRadius}
              />
              <NumberField
                label="Clad Radius"
                unit="μm"
                step={5.0}
                min={5.0}
                max={2000.0}
                value={cladRadius}
                onChange={setCladRadius}
                hint={`Ratio: ${(cladRadius / coreRadius).toFixed(1)}×`}
              />
              <NumberField
                label="n_core"
                step={0.0001}
                min={1.001}
                max={3.0}
                value={nCore}
                onChange={setNCore}
                hint="SMF-28: 1.4681"
              />
              <NumberField
                label="n_clad"
                step={0.0001}
                min={1.0}
                max={3.0}
                value={nClad}
                onChange={setNClad}
                hint="SMF-28: 1.4629"
              />
              <div className="col-span-2">
                <NumberField
                  label="Wavelength"
                  unit="nm"
                  step={10.0}
                  min={200.0}
                  max={5000.0}
                  value={lambda}
                  onChange={setLambda}
                  hint={`NA = ${NA.toFixed(4)} · V_input ≈ ${V_in.toFixed(2)} · V_waist ≈ ${V_waist_est.toFixed(2)}`}
                />
              </div>
            </CardContent>
          </Card>

          {/* Taper Geometry */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Taper Geometry</CardTitle>
              <CardDescription className="text-xs">
                Biconical: down-taper → flat waist → up-taper. Total length = 2 × L_taper + L_waist.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1.5">
                <Label>Taper Profile Shape</Label>
                <Select value={shape} onValueChange={(v) => setShape(v as TaperShape)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cosine">Cosine (smooth, RP Fiber Power default)</SelectItem>
                    <SelectItem value="linear">Linear (straight-sided)</SelectItem>
                    <SelectItem value="exponential">Exponential (constant dB/length)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <NumberField
                  label="Taper Arm Length"
                  unit="mm"
                  step={5.0}
                  min={0.01}
                  max={2000.0}
                  value={Ltaper}
                  onChange={setLtaper}
                />
                <NumberField
                  label="Waist Length"
                  unit="mm"
                  step={1.0}
                  min={0.0}
                  max={500.0}
                  value={Lwaist}
                  onChange={setLwaist}
                />
              </div>

              <NumberField
                label="Taper Ratio (r_waist / r₀)"
                step={0.05}
                min={0.01}
                max={1.0}
                value={taperRatio}
                onChange={setTaperRatio}
                hint={`Waist core: ${(coreRadius * taperRatio).toFixed(2)} μm · clad: ${(cladRadius * taperRatio).toFixed(1)} μm`}
              />
            </CardContent>
          </Card>

          {/* Grid */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Grid Resolution</CardTitle>
            </CardHeader>
            <CardContent>
              <NumberField
                label="Z points"
                step={200}
                min={100}
                max={3000}
                value={numZ}
                onChange={setNumZ}
              />
            </CardContent>
          </Card>
        </div>

        {/* ── Results ── */}
        <div className="xl:col-span-8 space-y-4">
          {result && (
            <>
              {/* Summary badges */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">V input / waist</div>
                    <div className="text-lg font-bold mt-1 text-primary">
                      {result.V_input.toFixed(2)} / {result.V_waist.toFixed(3)}
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      {result.V_input < 2.405 ? "SM" : "MM"} → {result.V_waist < 2.405 ? "SM" : "MM"}
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">MFD input / waist</div>
                    <div className="text-lg font-bold mt-1 text-cyan-400">
                      {result.mfd_input_um.toFixed(1)} / {result.mfd_waist_um.toFixed(1)} μm
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Adiabaticity η_max</div>
                    <div className={`text-lg font-bold mt-1 ${result.is_adiabatic ? "text-emerald-400" : "text-rose-400"}`}>
                      {result.max_eta > 999 ? `${(result.max_eta / 1000).toFixed(1)}k` : result.max_eta.toFixed(2)}
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      {result.is_adiabatic ? "adiabatic" : "non-adiabatic"}
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Est. Transmission</div>
                    <div className="text-lg font-bold mt-1 text-amber-400">
                      {(result.transmission * 100).toFixed(1)}%
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      {result.lp11_filtered ? "LP₁₁ filtered" : "LP₀₁ only"}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Fiber profile */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Fiber Profile r(z)</CardTitle>
                </CardHeader>
                <CardContent className="p-2">
                  <PlotlyChart
                    data={[
                      {
                        x: result.z_mm,
                        y: result.r_clad_um,
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "Cladding radius",
                        line: { color: "#6366F1", width: 1.5 },
                        fill: "tozeroy" as any,
                        fillcolor: "rgba(99,102,241,0.08)",
                      },
                      {
                        x: result.z_mm,
                        y: result.r_clad_um.map(v => -v),
                        type: "scatter" as any,
                        mode: "lines" as any,
                        showlegend: false,
                        line: { color: "#6366F1", width: 1.5 },
                        fill: "tozeroy" as any,
                        fillcolor: "rgba(99,102,241,0.08)",
                      },
                      {
                        x: result.z_mm,
                        y: result.r_core_um,
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "Core radius",
                        line: { color: "#F59E0B", width: 2.5 },
                        fill: "tozeroy" as any,
                        fillcolor: "rgba(245,158,11,0.15)",
                      },
                      {
                        x: result.z_mm,
                        y: result.r_core_um.map(v => -v),
                        type: "scatter" as any,
                        mode: "lines" as any,
                        showlegend: false,
                        line: { color: "#F59E0B", width: 2.5 },
                        fill: "tozeroy" as any,
                        fillcolor: "rgba(245,158,11,0.15)",
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Position z (mm)" }, zeroline: false },
                      yaxis: { title: { text: "Radius (μm)" } },
                      margin: { t: 10, r: 20, b: 40, l: 60 },
                    }}
                    height={220}
                  />
                </CardContent>
              </Card>

              {/* MFD evolution — three definitions (RP Fiber Power style) */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Mode Field Diameter Evolution — Three Definitions</CardTitle>
                  <CardDescription className="text-xs">
                    w₂: second moment (Petermann I) · w_eff: effective area (Petermann II) · w_HWHM: half-width at half maximum
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-2">
                  <PlotlyChart
                    data={[
                      {
                        x: result.z_mm,
                        y: result.mfd_w2_um,
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "w₂ (2nd moment)",
                        line: { color: "#EF4444", width: 2.5 },
                      },
                      {
                        x: result.z_mm,
                        y: result.mfd_weff_um,
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "w_eff (A_eff/π)",
                        line: { color: "#10B981", width: 2, dash: "dash" as any },
                      },
                      {
                        x: result.z_mm,
                        y: result.mfd_hwhm_um,
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "w_HWHM",
                        line: { color: "#F59E0B", width: 2, dash: "dot" as any },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Position z (mm)" }, zeroline: false },
                      yaxis: { title: { text: "MFD (μm)" }, rangemode: "nonnegative" },
                      margin: { t: 10, r: 20, b: 40, l: 60 },
                    }}
                    height={280}
                  />
                </CardContent>
              </Card>

              {/* V parameter */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Normalized Frequency V(z)</CardTitle>
                </CardHeader>
                <CardContent className="p-2">
                  <PlotlyChart
                    data={[
                      {
                        x: result.z_mm,
                        y: result.V_core,
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "V_core (core/clad)",
                        line: { color: "#F59E0B", width: 2.5 },
                      },
                      {
                        x: result.z_mm,
                        y: result.V_clad,
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "V_clad (clad/air)",
                        line: { color: "#6366F1", width: 2, dash: "dash" as any },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Position z (mm)" }, zeroline: false },
                      yaxis: { title: { text: "V parameter" }, rangemode: "nonnegative" },
                      shapes: [
                        {
                          type: "line",
                          x0: 0, x1: 1, xref: "paper" as any,
                          y0: 2.405, y1: 2.405,
                          line: { color: "#EF4444", width: 1.5, dash: "dot" },
                        },
                      ],
                      annotations: [
                        {
                          x: 0.02, xref: "paper" as any,
                          y: 2.405,
                          text: "LP₁₁ cutoff V = 2.405",
                          showarrow: false,
                          font: { size: 10, color: "#EF4444" },
                          yanchor: "bottom" as any,
                        },
                      ],
                      margin: { t: 10, r: 20, b: 40, l: 60 },
                    }}
                    height={230}
                  />
                </CardContent>
              </Card>

              {/* Adiabaticity parameter */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Adiabaticity Parameter η(z) = Ω / Ω_c</CardTitle>
                  <CardDescription className="text-xs">
                    η ≪ 1: adiabatic (negligible mode coupling) · η ≫ 1: non-adiabatic (mode coupling / loss)
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-2">
                  <PlotlyChart
                    data={[
                      {
                        x: result.z_mm,
                        y: result.eta.map(v => Math.min(v, 50)),   // clip display to 50
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "η(z)",
                        line: { color: "#EC4899", width: 2.5 },
                        fill: "tozeroy" as any,
                        fillcolor: "rgba(236,72,153,0.08)",
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Position z (mm)" }, zeroline: false },
                      yaxis: { title: { text: "η = Ω / Ω_c  (clipped to 50)" }, rangemode: "nonnegative" },
                      shapes: [
                        {
                          type: "line",
                          x0: 0, x1: 1, xref: "paper" as any,
                          y0: 1, y1: 1,
                          line: { color: "#EF4444", width: 1.5, dash: "dot" },
                        },
                      ],
                      annotations: [
                        {
                          x: 0.02, xref: "paper" as any,
                          y: 1,
                          text: "η = 1  (adiabatic limit)",
                          showarrow: false,
                          font: { size: 10, color: "#EF4444" },
                          yanchor: "bottom" as any,
                        },
                      ],
                      margin: { t: 10, r: 20, b: 40, l: 60 },
                    }}
                    height={220}
                  />
                </CardContent>
              </Card>
            </>
          )}

          {!result && !loading && (
            <div className="h-[550px] flex flex-col items-center justify-center border border-dashed border-border bg-card/10 rounded-2xl text-center p-8 text-muted-foreground">
              <Triangle className="h-8 w-8 text-muted-foreground/50 mb-3" />
              <h3 className="text-sm font-medium text-foreground mb-1">No Taper Data</h3>
              <p className="text-xs max-w-sm mb-4">
                Configure fiber geometry, taper ratio and length, then click "Run Analysis" to compute the local-mode evolution through the biconical taper.
              </p>
              <div className="text-[11px] text-muted-foreground/70 max-w-xs leading-relaxed">
                Outputs: taper profile · MFD evolution (3 definitions) · V parameter · adiabaticity η(z)
              </div>
            </div>
          )}

          {loading && (
            <div className="h-[550px] flex flex-col items-center justify-center border border-dashed border-border bg-card/10 rounded-2xl text-center p-8 text-muted-foreground">
              <Loader2 className="h-8 w-8 text-primary animate-spin mb-3" />
              <h3 className="text-sm font-medium text-foreground mb-1">Computing Local Mode Analysis...</h3>
              <p className="text-xs">Solving LP₀₁ mode field at each z position (Bessel functions + quadrature). This may take a few seconds for high z-resolution.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
