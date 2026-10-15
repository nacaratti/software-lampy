import { useState } from "react";
import { toast } from "sonner";
import { Play, Loader2, Info, GitFork } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { NumberField } from "@/components/common/NumberField";
import { PageHeader } from "@/components/layout/PageHeader";
import { PlotlyChart } from "@/components/plots/PlotlyChart";
import { api } from "@/lib/api";
import { useSyncJob } from "@/lib/syncJob";
import type { CouplerCalculationResponse } from "@/types/coupler";

export function CouplerPage() {
  // Fiber
  const [coreRadius, setCoreRadius] = useState(4.0);
  const [nCore, setNCore] = useState(1.4508);
  const [nClad, setNClad] = useState(1.45);

  // Coupling geometry
  const [fiberSep, setFiberSep] = useState(10.0);
  const [couplingLength, setCouplingLength] = useState(10.0);

  // Optical
  const [lambdaCenter, setLambdaCenter] = useState(1550.0);
  const [P1in, setP1in] = useState(1.0);
  const [P2in, setP2in] = useState(0.0);
  const [delta, setDelta] = useState(0.0);

  // Spectral sweep
  const [lambdaMin, setLambdaMin] = useState(1450.0);
  const [lambdaMax, setLambdaMax] = useState(1650.0);

  // Grid
  const [numZ, setNumZ] = useState(500);
  const [numLambda, setNumLambda] = useState(200);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CouplerCalculationResponse | null>(null);
  const runSync = useSyncJob();

  const NA = Math.sqrt(Math.max(nCore ** 2 - nClad ** 2, 0));

  async function runSimulation() {
    if (nCore <= nClad) {
      toast.error("Core index must be greater than cladding index");
      return;
    }
    if (lambdaMin >= lambdaMax) {
      toast.error("λ_min must be less than λ_max");
      return;
    }
    if (P1in <= 0 && P2in <= 0) {
      toast.error("At least one input port must have power > 0");
      return;
    }

    setLoading(true);
    const req = {
      core_radius_um: coreRadius,
      n_core: nCore,
      n_clad: nClad,
      fiber_separation_um: fiberSep,
      coupling_length_mm: couplingLength,
      lambda_center_nm: lambdaCenter,
      P1_in_w: P1in,
      P2_in_w: P2in,
      delta_rad_per_m: delta,
      lambda_min_nm: lambdaMin,
      lambda_max_nm: lambdaMax,
      num_z: numZ,
      num_lambda: numLambda,
    };
    try {
      const res = await runSync(
        "coupler",
        `Coupler ${couplingLength}mm ${lambdaCenter}nm`,
        req,
        () => api.calculateCoupler(req)
      );
      setResult(res);
      toast.success("Coupler simulation completed");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setLoading(false);
    }
  }

  const splitPct = result ? (result.splitting_ratio * 100).toFixed(1) : null;

  return (
    <div className="container mx-auto py-8 max-w-7xl">
      <PageHeader
        eyebrow="Solver"
        title="Fiber Coupler"
        description="Coupled-mode theory (CMT) solver for evanescent wave coupling between two single-mode fibers. Computes longitudinal power exchange and wavelength-dependent splitting ratio."
        actions={
          <Button variant="glow" size="sm" onClick={runSimulation} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {loading ? "Simulating..." : "Run Simulation"}
          </Button>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* ── Input Column ── */}
        <div className="xl:col-span-4 space-y-4">

          {/* Fiber Parameters */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Fiber Parameters</CardTitle>
              <CardDescription className="text-xs">
                Single-mode step-index fiber (same for both arms in symmetric coupler)
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <NumberField
                  label="Core Radius"
                  unit="μm"
                  step={0.5}
                  min={0.5}
                  max={50.0}
                  value={coreRadius}
                  onChange={setCoreRadius}
                  hint={`NA = ${NA.toFixed(4)}`}
                />
              </div>
              <NumberField
                label="n_core"
                step={0.0001}
                min={1.0}
                max={3.0}
                value={nCore}
                onChange={setNCore}
                hint="e.g. Silica: 1.4508"
              />
              <NumberField
                label="n_clad"
                step={0.0001}
                min={1.0}
                max={3.0}
                value={nClad}
                onChange={setNClad}
                hint="e.g. Silica: 1.4500"
              />
            </CardContent>
          </Card>

          {/* Coupling Geometry */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Coupling Geometry</CardTitle>
              <CardDescription className="text-xs">
                Evanescent field overlap region. Smaller gap → stronger coupling → shorter L_c.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              <NumberField
                label="Fiber Gap"
                unit="μm"
                step={1.0}
                min={0.1}
                max={200.0}
                value={fiberSep}
                onChange={setFiberSep}
                hint={`d_cc = ${(2 * coreRadius + fiberSep).toFixed(1)} μm`}
              />
              <NumberField
                label="Coupling Length"
                unit="mm"
                step={1.0}
                min={0.01}
                max={500.0}
                value={couplingLength}
                onChange={setCouplingLength}
              />
            </CardContent>
          </Card>

          {/* Optical Input */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Optical Input</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <NumberField
                  label="Center Wavelength"
                  unit="nm"
                  step={10.0}
                  min={600.0}
                  max={3000.0}
                  value={lambdaCenter}
                  onChange={setLambdaCenter}
                />
              </div>
              <NumberField
                label="Port 1 Input"
                unit="W"
                step={0.1}
                min={0.0}
                value={P1in}
                onChange={setP1in}
              />
              <NumberField
                label="Port 2 Input"
                unit="W"
                step={0.1}
                min={0.0}
                value={P2in}
                onChange={setP2in}
              />
              <div className="col-span-2">
                <NumberField
                  label="Phase Mismatch δ = Δβ/2"
                  unit="rad/m"
                  step={10}
                  min={0.0}
                  value={delta}
                  onChange={setDelta}
                  hint="0 = symmetric coupler (identical fibers). Increase for wavelength-selective WDM coupler."
                />
              </div>
            </CardContent>
          </Card>

          {/* Spectral Sweep */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Spectral Sweep</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              <NumberField
                label="λ_min"
                unit="nm"
                step={10.0}
                min={600.0}
                max={3000.0}
                value={lambdaMin}
                onChange={setLambdaMin}
              />
              <NumberField
                label="λ_max"
                unit="nm"
                step={10.0}
                min={600.0}
                max={3000.0}
                value={lambdaMax}
                onChange={setLambdaMax}
              />
              <NumberField
                label="Z points"
                step={100}
                min={50}
                max={2000}
                value={numZ}
                onChange={setNumZ}
              />
              <NumberField
                label="λ points"
                step={50}
                min={20}
                max={1000}
                value={numLambda}
                onChange={setNumLambda}
              />
            </CardContent>
          </Card>
        </div>

        {/* ── Results Column ── */}
        <div className="xl:col-span-8 space-y-4">
          {result && (
            <>
              {/* Summary Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Coupling Coeff κ</div>
                    <div className="text-xl font-bold mt-1 text-primary">
                      {result.kappa_c.toFixed(0)} m⁻¹
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Coupling Length L_c</div>
                    <div className="text-xl font-bold mt-1 text-cyan-400">
                      {result.coupling_length_mm.toFixed(2)} mm
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Splitting Ratio</div>
                    <div className="text-xl font-bold mt-1 text-emerald-400">
                      {splitPct}%
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      {(100 - parseFloat(splitPct ?? "0")).toFixed(1)}% / {splitPct}%
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Port Powers Out</div>
                    <div className="text-base font-bold mt-1 text-amber-400 leading-tight">
                      P1: {result.P1_out.toFixed(3)} W
                    </div>
                    <div className="text-base font-bold text-rose-400 leading-tight">
                      P2: {result.P2_out.toFixed(3)} W
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Throughput / Cross dB */}
              <div className="grid grid-cols-2 gap-3">
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-3 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Through Port</div>
                    <div className="text-lg font-semibold mt-0.5 text-amber-400">
                      {result.throughput_db > -999 ? `${result.throughput_db.toFixed(2)} dB` : "—"}
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-3 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Cross Port</div>
                    <div className="text-lg font-semibold mt-0.5 text-rose-400">
                      {result.cross_db > -999 ? `${result.cross_db.toFixed(2)} dB` : "—"}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Power evolution along z */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Power Exchange along Coupling Length</CardTitle>
                </CardHeader>
                <CardContent className="p-2">
                  <PlotlyChart
                    data={[
                      {
                        x: result.z_mm,
                        y: result.P1_z,
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "Port 1 (Through)",
                        line: { color: "#F59E0B", width: 2.5 },
                      },
                      {
                        x: result.z_mm,
                        y: result.P2_z,
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "Port 2 (Cross)",
                        line: { color: "#EF4444", width: 2.5 },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Position z (mm)" }, zeroline: false },
                      yaxis: { title: { text: "Power (W)" }, rangemode: "nonnegative" },
                      margin: { t: 10, r: 20, b: 40, l: 55 },
                    }}
                    height={280}
                  />
                </CardContent>
              </Card>

              {/* Spectral response */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Spectral Splitting Ratio P₂/(P₁+P₂) vs Wavelength</CardTitle>
                </CardHeader>
                <CardContent className="p-2">
                  <PlotlyChart
                    data={[
                      {
                        x: result.lambda_nm,
                        y: result.splitting_ratio_lambda.map(v => v * 100),
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "Cross port %",
                        line: { color: "#EF4444", width: 2.5 },
                        fill: "tozeroy" as any,
                        fillcolor: "rgba(239,68,68,0.08)",
                      },
                      {
                        x: result.lambda_nm,
                        y: result.splitting_ratio_lambda.map(v => (1 - v) * 100),
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "Through port %",
                        line: { color: "#F59E0B", width: 2, dash: "dash" as any },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Wavelength (nm)" }, zeroline: false },
                      yaxis: {
                        title: { text: "Splitting ratio (%)" },
                        range: [0, 100],
                      },
                      shapes: [
                        {
                          type: "line",
                          x0: lambdaCenter,
                          x1: lambdaCenter,
                          y0: 0,
                          y1: 100,
                          line: { color: "#6366F1", width: 1.5, dash: "dot" },
                        },
                        {
                          type: "line",
                          y0: 50,
                          y1: 50,
                          x0: lambdaMin,
                          x1: lambdaMax,
                          xref: "paper" as any,
                          line: { color: "#888", width: 1, dash: "dot" },
                        },
                      ],
                      annotations: [
                        {
                          x: lambdaCenter,
                          y: 95,
                          text: `λ_c = ${lambdaCenter} nm`,
                          showarrow: false,
                          font: { size: 10, color: "#6366F1" },
                          xanchor: "left" as any,
                        },
                      ],
                      margin: { t: 10, r: 20, b: 40, l: 55 },
                    }}
                    height={280}
                  />
                </CardContent>
              </Card>

              {/* Coupling coefficient vs wavelength */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Coupling Coefficient κ(λ)</CardTitle>
                </CardHeader>
                <CardContent className="p-2">
                  <PlotlyChart
                    data={[
                      {
                        x: result.lambda_nm,
                        y: result.kappa_lambda,
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "κ(λ)",
                        line: { color: "#6366F1", width: 2.5 },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Wavelength (nm)" }, zeroline: false },
                      yaxis: { title: { text: "κ (m⁻¹)" }, rangemode: "nonnegative" },
                      shapes: [
                        {
                          type: "line",
                          x0: lambdaCenter,
                          x1: lambdaCenter,
                          y0: 0,
                          y1: 1,
                          yref: "paper" as any,
                          line: { color: "#6366F1", width: 1.5, dash: "dot" },
                        },
                      ],
                      margin: { t: 10, r: 20, b: 40, l: 65 },
                    }}
                    height={220}
                  />
                </CardContent>
              </Card>
            </>
          )}

          {!result && !loading && (
            <div className="h-[550px] flex flex-col items-center justify-center border border-dashed border-border bg-card/10 rounded-2xl text-center p-8 text-muted-foreground">
              <GitFork className="h-8 w-8 text-muted-foreground/50 mb-3" />
              <h3 className="text-sm font-medium text-foreground mb-1">No Coupler Data</h3>
              <p className="text-xs max-w-sm mb-4">
                Set fiber geometry, coupling gap and length, then click "Run Simulation" to solve the
                coupled-mode equations and compute the power exchange and spectral response.
              </p>
            </div>
          )}

          {loading && (
            <div className="h-[550px] flex flex-col items-center justify-center border border-dashed border-border bg-card/10 rounded-2xl text-center p-8 text-muted-foreground">
              <Loader2 className="h-8 w-8 text-primary animate-spin mb-3" />
              <h3 className="text-sm font-medium text-foreground mb-1">Solving Coupled-Mode Equations...</h3>
              <p className="text-xs">Computing LP₀₁ mode parameters, κ(λ), and power evolution.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
