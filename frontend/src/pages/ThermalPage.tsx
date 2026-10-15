import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Play, Loader2, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { NumberField } from "@/components/common/NumberField";
import { PageHeader } from "@/components/layout/PageHeader";
import { PlotlyChart } from "@/components/plots/PlotlyChart";
import { ThermalCrossSection } from "@/components/plots/ThermalCrossSection";
import { api } from "@/lib/api";
import { decodeArray, reshape2D } from "@/lib/encoding";
import { useSyncJob } from "@/lib/syncJob";
import type { ThermalCalculationResponse } from "@/types/thermal";

// A fully-absorbed pump can decay across many orders of magnitude (e.g. a
// long, strongly-doped fiber with a high overlap can drive it to ~1e-160 W —
// mathematically correct exponential decay, but physically meaningless and,
// on a log-scale axis, stretches the whole chart to an unreadable range).
// Clip anything below a sub-femtowatt floor so the axis stays sane.
const LOG_PLOT_FLOOR_W = 1e-12;
function clipForLogPlot(values: number[]): number[] {
  return values.map((v) => Math.max(v, LOG_PLOT_FLOOR_W));
}

export function ThermalPage() {
  // Fiber Geometry
  const [fiberLength, setFiberLength] = useState(5.0);
  const [coreRadius, setCoreRadius] = useState(3.0);
  const [cladRadius, setCladRadius] = useState(62.5);
  const [coatingRadius, setCoatingRadius] = useState(125.0);

  // Active Ion Dynamics
  const [nTotal, setNTotal] = useState(4.0e25);
  const [tauMs, setTauMs] = useState(1.0);

  // Optical Parameters
  const [lambdaPump, setLambdaPump] = useState(976.0);
  const [lambdaSignal, setLambdaSignal] = useState(1018.0);
  // 0.02 (~2%) models a cladding-pumped overlap (Γ_pump ≈ A_core/A_clad for a
  // double-clad fiber) — needed to keep the default 5 m length physically
  // sane with the real Yb absorption cross-section: a core-level overlap
  // (~0.8) would fully absorb the pump within a few cm at these cross-sections
  // and the pump trace would underflow toward numerical zero over the rest
  // of the fiber, blowing out the log-scale power chart's axis range.
  const [gammaPump, setGammaPump] = useState(0.02);
  const [gammaSignal, setGammaSignal] = useState(0.9);

  // Cross-sections (m²) — initial values match the real Yb³⁺ ion model (McCumber-derived)
  // at 976 nm pump / 1018 nm signal, fetched from /api/fibers/ion-cross-sections below.
  const [sigmaAbsPump, setSigmaAbsPump] = useState(2.368e-24);
  const [sigmaEmPump, setSigmaEmPump] = useState(2.431e-24);
  const [sigmaAbsSignal, setSigmaAbsSignal] = useState(1.02e-25);
  const [sigmaEmSignal, setSigmaEmSignal] = useState(7.864e-25);
  const [epsilon, setEpsilon] = useState(0.9);

  // Pumps & Seed
  const [pumping, setPumping] = useState<"forward" | "backward" | "bidirectional">("forward");
  const [method, setMethod] = useState<"analytical" | "rk4">("analytical");
  const [pumpFwd, setPumpFwd] = useState(10.0);
  const [pumpBwd, setPumpBwd] = useState(0.0);
  const [seedPower, setSeedPower] = useState(1.0e-6);

  // Thermal conductivities & convection
  const [kCore, setKCore] = useState(1.38);
  const [kClad, setKClad] = useState(1.38);
  const [kCoat, setKCoat] = useState(0.2);
  const [hConv, setHConv] = useState(10.0);
  const [tAmbient, setTAmbient] = useState(25.0);

  // Solver Resolution
  const [numZ, setNumZ] = useState(200);
  const [numR, setNumR] = useState(50);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ThermalCalculationResponse | null>(null);
  const runSync = useSyncJob();

  // Recommended cross-sections at the current pump/signal wavelengths, fetched from
  // /api/fibers/ion-cross-sections — the same McCumber-derived Yb³⁺ model used by the
  // System Builder and Power & ASE solver (previously this page used its own independent,
  // hand-tuned table that disagreed with that model by up to ~10x at 976 nm).
  const [rec, setRec] = useState({
    sigmaAbsPump: 2.368e-24, sigmaEmPump: 2.431e-24,
    sigmaAbsSignal: 1.02e-25, sigmaEmSignal: 7.864e-25,
  });

  useEffect(() => {
    let cancelled = false;
    const handle = setTimeout(() => {
      api.ionCrossSections({ ion: "yb", wavelengths_nm: [lambdaPump, lambdaSignal] })
        .then((res) => {
          if (cancelled) return;
          setRec({
            sigmaAbsPump: res.sigma_abs_m2[0], sigmaEmPump: res.sigma_em_m2[0],
            sigmaAbsSignal: res.sigma_abs_m2[1], sigmaEmSignal: res.sigma_em_m2[1],
          });
        })
        .catch(() => { /* keep last known recommendation on transient errors */ });
    }, 250);
    return () => { cancelled = true; clearTimeout(handle); };
  }, [lambdaPump, lambdaSignal]);

  async function runSimulation() {
    if (cladRadius <= coreRadius) {
      toast.error("Cladding radius must be larger than core radius");
      return;
    }
    if (coatingRadius <= cladRadius) {
      toast.error("Coating radius must be larger than cladding radius");
      return;
    }
    if (pumping === "forward" && pumpFwd <= 0) {
      toast.error("Forward pump power must be greater than 0");
      return;
    }
    if (pumping === "backward" && pumpBwd <= 0) {
      toast.error("Backward pump power must be greater than 0");
      return;
    }
    if (pumping === "bidirectional" && pumpFwd <= 0 && pumpBwd <= 0) {
      toast.error("At least one pump power must be greater than 0");
      return;
    }

    setLoading(true);
    const req = {
      fiber_length_m: fiberLength,
      core_radius_um: coreRadius,
      clad_radius_um: cladRadius,
      coating_radius_um: coatingRadius,
      N_total: nTotal,
      tau_ms: tauMs,
      lambda_pump_nm: lambdaPump,
      lambda_signal_nm: lambdaSignal,
      gamma_pump: gammaPump,
      gamma_signal: gammaSignal,
      P_pump_forward_w: pumpFwd,
      P_pump_backward_w: pumpBwd,
      P_signal_seed_w: seedPower,
      pumping: pumping,
      method: method,
      sigma_abs_pump: sigmaAbsPump,
      sigma_em_pump: sigmaEmPump,
      sigma_abs_signal: sigmaAbsSignal,
      sigma_em_signal: sigmaEmSignal,
      k_core: kCore,
      k_clad: kClad,
      k_coat: kCoat,
      h_conv: hConv,
      epsilon: epsilon,
      T_ambient_celsius: tAmbient,
      num_z_points: numZ,
      num_r_points: numR,
    };
    try {
      const res = await runSync(
        "thermal",
        `Thermal ${fiberLength}m ${pumpFwd + pumpBwd}W`,
        req,
        () => api.calculateThermal(req)
      );
      setResult(res);
      toast.success("Active fiber thermal simulation completed");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setLoading(false);
    }
  }

  // Pre-process 2D temperature profile if result is available
  let t2dData: number[][] = [];
  if (result) {
    const dec = decodeArray(result.T_2d);
    if (dec.kind === "real") {
      const [rows, cols] = dec.shape;
      t2dData = reshape2D(dec.data, rows, cols);
    }
  }

  const thermalColorscale = [
    [0, "#1E3B8A"],      // Dark Blue (Ambient/Cool)
    [0.2, "#3B82F6"],    // Blue
    [0.5, "#F59E0B"],    // Orange/Warm
    [0.8, "#EF4444"],    // Red
    [1.0, "#FDE047"],    // Light Yellow (Center/Hot)
  ];

  return (
    <div className="container mx-auto py-8 max-w-7xl">
      <PageHeader
        eyebrow="Solver · Yb³⁺ only"
        title="Thermal Simulator"
        description="Simulate pump and signal power evolution in Ytterbium-doped active optical fibers. Evaluates steady-state population inversions and calculates the 2D radial/longitudinal heat profile."
        actions={
          <Button variant="glow" size="sm" onClick={runSimulation} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {loading ? "Simulating..." : "Run Simulation"}
          </Button>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Input Parameters Column */}
        <div className="xl:col-span-4 space-y-4">
          
          {/* Pump Scheme & Input Power */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Pumping Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label>Pumping Direction</Label>
                <Select
                  value={pumping}
                  onValueChange={(v) => setPumping(v as any)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="forward">Forward Pump Only</SelectItem>
                    <SelectItem value="backward">Backward Pump Only</SelectItem>
                    <SelectItem value="bidirectional">Bidirectional Pump</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label>Solver Method</Label>
                <Select
                  value={method}
                  onValueChange={(v) => setMethod(v as any)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="analytical">Analytical (Forward-Euler)</SelectItem>
                    <SelectItem value="rk4">RK4 (scipy.solve_ivp)</SelectItem>
                  </SelectContent>
                </Select>
                {method === "rk4" && pumping !== "forward" && (
                  <p className="text-[10px] text-amber-500">
                    RK4 only supports forward pumping; falls back to analytical for {pumping}.
                  </p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <NumberField
                  label="Forward Pump"
                  unit="W"
                  step={1.0}
                  min={0.0}
                  disabled={pumping === "backward"}
                  value={pumpFwd}
                  onChange={setPumpFwd}
                />
                <NumberField
                  label="Backward Pump"
                  unit="W"
                  step={1.0}
                  min={0.0}
                  disabled={pumping === "forward"}
                  value={pumpBwd}
                  onChange={setPumpBwd}
                />
              </div>

              <NumberField
                label="Signal Seed Power"
                unit="W"
                step={1e-6}
                min={1e-9}
                value={seedPower}
                onChange={setSeedPower}
              />
            </CardContent>
          </Card>

          {/* Fiber Geometry */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Fiber Geometry</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <NumberField
                  label="Fiber Length"
                  unit="m"
                  step={0.5}
                  min={0.1}
                  max={50.0}
                  value={fiberLength}
                  onChange={setFiberLength}
                />
              </div>
              <NumberField
                label="Core Radius"
                unit="μm"
                step={0.1}
                min={1.0}
                max={50.0}
                value={coreRadius}
                onChange={setCoreRadius}
              />
              <NumberField
                label="Cladding Radius"
                unit="μm"
                step={1.0}
                min={10.0}
                max={500.0}
                value={cladRadius}
                onChange={setCladRadius}
              />
              <div className="col-span-2">
                <NumberField
                  label="Coating Radius"
                  unit="μm"
                  step={1.0}
                  min={20.0}
                  max={1000.0}
                  value={coatingRadius}
                  onChange={setCoatingRadius}
                />
              </div>
            </CardContent>
          </Card>

          {/* Active Medium & Radiative parameters */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Optical & Active Medium Params</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <NumberField
                  label="Dopant Ion Concentration (N_total)"
                  unit="m⁻³"
                  step={1e24}
                  min={1e23}
                  max={1e27}
                  value={nTotal}
                  onChange={setNTotal}
                />
              </div>
              <NumberField
                label="Pump Wavelength"
                unit="nm"
                step={1.0}
                min={800.0}
                max={1100.0}
                value={lambdaPump}
                onChange={setLambdaPump}
              />
              <NumberField
                label="Signal Wavelength"
                unit="nm"
                step={1.0}
                min={950.0}
                max={1200.0}
                value={lambdaSignal}
                onChange={setLambdaSignal}
              />
              <NumberField
                label="Pump Overlap (Γp)"
                step={0.01}
                min={0.01}
                max={1}
                value={gammaPump}
                onChange={setGammaPump}
              />
              <NumberField
                label="Signal Overlap (Γs)"
                step={0.05}
                min={0.01}
                max={1}
                value={gammaSignal}
                onChange={setGammaSignal}
              />
              <NumberField
                label="Yb Life time (τ)"
                unit="ms"
                step={0.1}
                min={0.1}
                max={10.0}
                value={tauMs}
                onChange={setTauMs}
              />
            </CardContent>
          </Card>

          {/* Stimulated Emission / Absorption Cross-Sections */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Stimulated Cross-Sections (Yb³⁺)</CardTitle>
              <CardDescription className="text-xs">
                Spectroscopic parameters for Yb³⁺. Hints show recommended values from the same ion cross-section
                model used by the System Builder and Power &amp; ASE solver, for the selected wavelengths.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(() => {
                const fmt = (v: number) => `${v.toExponential(3)} m²`;
                return (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <NumberField
                        label="σ_abs (pump)"
                        unit="m²"
                        step={1e-26}
                        min={1e-27}
                        value={sigmaAbsPump}
                        onChange={setSigmaAbsPump}
                        hint={`Rec @ ${lambdaPump} nm: ${fmt(rec.sigmaAbsPump)}`}
                      />
                      <NumberField
                        label="σ_em (pump)"
                        unit="m²"
                        step={1e-26}
                        min={1e-27}
                        value={sigmaEmPump}
                        onChange={setSigmaEmPump}
                        hint={`Rec @ ${lambdaPump} nm: ${fmt(rec.sigmaEmPump)}`}
                      />
                      <NumberField
                        label="σ_abs (signal)"
                        unit="m²"
                        step={1e-26}
                        min={1e-27}
                        value={sigmaAbsSignal}
                        onChange={setSigmaAbsSignal}
                        hint={`Rec @ ${lambdaSignal} nm: ${fmt(rec.sigmaAbsSignal)}`}
                      />
                      <NumberField
                        label="σ_em (signal)"
                        unit="m²"
                        step={1e-26}
                        min={1e-27}
                        value={sigmaEmSignal}
                        onChange={setSigmaEmSignal}
                        hint={`Rec @ ${lambdaSignal} nm: ${fmt(rec.sigmaEmSignal)}`}
                      />
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full text-xs"
                      onClick={() => {
                        setSigmaAbsPump(rec.sigmaAbsPump);
                        setSigmaEmPump(rec.sigmaEmPump);
                        setSigmaAbsSignal(rec.sigmaAbsSignal);
                        setSigmaEmSignal(rec.sigmaEmSignal);
                      }}
                    >
                      Apply recommended values for {lambdaPump}/{lambdaSignal} nm
                    </Button>
                  </>
                );
              })()}
            </CardContent>
          </Card>

          {/* Cooling & Thermal Constants */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Thermal Boundary & Conductivities</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              <NumberField
                label="Ambient Temp"
                unit="°C"
                step={1.0}
                min={-50.0}
                max={100.0}
                value={tAmbient}
                onChange={setTAmbient}
              />
              <NumberField
                label="Convection (h)"
                unit="W/(m²K)"
                step={1.0}
                min={1.0}
                max={1000.0}
                value={hConv}
                onChange={setHConv}
              />
              <NumberField
                label="Emissivity (ε)"
                step={0.05}
                min={0.0}
                max={1.0}
                value={epsilon}
                onChange={setEpsilon}
                hint="Surface radiative emissivity (0=mirror, 1=blackbody)"
              />
              <NumberField
                label="Core Conductivity"
                unit="W/(mK)"
                step={0.05}
                min={0.1}
                max={20.0}
                value={kCore}
                onChange={setKCore}
              />
              <NumberField
                label="Clad Conductivity"
                unit="W/(mK)"
                step={0.05}
                min={0.1}
                max={20.0}
                value={kClad}
                onChange={setKClad}
              />
              <div className="col-span-2">
                <NumberField
                  label="Coating Conductivity"
                  unit="W/(mK)"
                  step={0.01}
                  min={0.01}
                  max={5.0}
                  value={kCoat}
                  onChange={setKCoat}
                />
              </div>
            </CardContent>
          </Card>

          {/* Solver Settings */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Grid Resolution</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              <NumberField
                label="Z steps"
                step={50}
                min={50}
                max={1000}
                value={numZ}
                onChange={setNumZ}
              />
              <NumberField
                label="Radial steps"
                step={10}
                min={10}
                max={200}
                value={numR}
                onChange={setNumR}
              />
            </CardContent>
          </Card>
        </div>

        {/* Results Column */}
        <div className="xl:col-span-8 space-y-4">
          {result && (
            <>
              {/* Output Stats Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Output Power</div>
                    <div className="text-xl font-bold mt-1 text-primary">
                      {result.output_power_w != null ? result.output_power_w.toFixed(2) : "—"} W
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Slope Efficiency</div>
                    <div className="text-xl font-bold mt-1 text-emerald-400">
                      {result.efficiency != null ? (result.efficiency * 100).toFixed(1) : "—"}%
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Amplifier Gain</div>
                    <div className="text-xl font-bold mt-1 text-cyan-400">
                      {result.gain_db != null ? result.gain_db.toFixed(1) : "—"} dB
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Peak Temperature</div>
                    <div className="text-xl font-bold mt-1 text-rose-500">
                      {result.T_max_celsius != null ? result.T_max_celsius.toFixed(1) : "—"} °C
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Power Distribution Plot — same curves as MATLAB reference */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">
                    Evolution of {pumping === "forward" ? "Forward" : pumping === "backward" ? "Backward" : "Two-end"} pump and laser powers along the fiber
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-2">
                  <PlotlyChart
                    data={[
                      ...(pumping === "forward" || pumping === "bidirectional"
                        ? [
                            {
                              x: result.z_m,
                              y: clipForLogPlot(result.pumps_forward),
                              type: "scatter" as any,
                              mode: "lines" as any,
                              name: "P+ pump",
                              line: { color: "#EF4444", width: 2 },
                            },
                          ]
                        : []),
                      ...(pumping === "backward" || pumping === "bidirectional"
                        ? [
                            {
                              x: result.z_m,
                              y: clipForLogPlot(result.pumps_backward),
                              type: "scatter" as any,
                              mode: "lines" as any,
                              name: "P- pump",
                              line: { color: "#3B82F6", width: 2, dash: "dash" as any },
                            },
                          ]
                        : []),
                      {
                        x: result.z_m,
                        y: clipForLogPlot(result.signals_forward),
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "P+ signal",
                        line: { color: "#06B6D4", width: 2.5 },
                      },
                      {
                        x: result.z_m,
                        y: clipForLogPlot(result.signals_backward),
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "P- signal",
                        line: { color: "#0F172A", width: 2, dash: "dashdot" as any },
                      },
                      {
                        x: result.z_m,
                        y: clipForLogPlot(result.pump_output_w),
                        type: "scatter" as any,
                        mode: "markers" as any,
                        name: "P_out",
                        marker: { color: "#22D3EE", symbol: "circle-open", size: 6 },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Length [m]" }, zeroline: false },
                      yaxis: { title: { text: "Power [W]" }, type: "log" as any },
                      margin: { t: 10, r: 20, b: 80, l: 50 },
                      legend: { orientation: "h" as any, y: -0.35 },
                    }}
                    height={340}
                  />
                </CardContent>
              </Card>

              {/* Longitudinal Center/Surface Temp Plot */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Temperature Profile along Fiber Length</CardTitle>
                </CardHeader>
                <CardContent className="p-2">
                  <PlotlyChart
                    data={[
                      {
                        x: result.z_m,
                        y: result.T_center_celsius,
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "Core Center T_center(z)",
                        line: { color: "#EF4444", width: 2.5 },
                      },
                      {
                        x: result.z_m,
                        y: result.T_surface_celsius,
                        type: "scatter" as any,
                        mode: "lines" as any,
                        name: "Coating Surface T_surface(z)",
                        line: { color: "#6366F1", width: 2 },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Position z (m)" }, zeroline: false },
                      yaxis: { title: { text: "Temperature (°C)" } },
                      margin: { t: 10, r: 20, b: 40, l: 50 },
                    }}
                    height={300}
                  />
                </CardContent>
              </Card>

              {/* Heatmap contour 2D T(r, z) */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">2D Temperature Profile Heatmap T(r, z)</CardTitle>
                </CardHeader>
                <CardContent className="p-2">
                  <PlotlyChart
                    data={[
                      {
                        x: result.z_m,
                        y: result.r_um,
                        z: t2dData,
                        type: "heatmap" as any,
                        colorscale: thermalColorscale as any,
                        colorbar: {
                          title: { text: "T (°C)" },
                          titleside: "right",
                        } as any,
                        hovertemplate: "z=%{x:.2f} m<br>r=%{y:.1f} µm<br>T=%{z:.1f} °C<extra></extra>",
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Position z (m)" }, zeroline: false },
                      yaxis: { title: { text: "Radius r (µm)" }, zeroline: false },
                      margin: { t: 10, r: 10, b: 40, l: 50 },
                    }}
                    height={320}
                  />
                </CardContent>
              </Card>

              {/* Circular fiber cross-section, revolved from T(r) at a chosen z */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Fiber Cross-Section — Temperature</CardTitle>
                  <CardDescription className="text-xs">
                    Radial profile revolved into the actual disc shape, like a thermal camera facing the fiber end.
                    Drag the slider to move along the fiber.
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-2">
                  <ThermalCrossSection
                    rUm={result.r_um}
                    t2d={t2dData}
                    zM={result.z_m}
                    colorscale={thermalColorscale}
                  />
                </CardContent>
              </Card>
            </>
          )}

          {!result && !loading && (
            <div className="h-[550px] flex flex-col items-center justify-center border border-dashed border-border bg-card/10 rounded-2xl text-center p-8 text-muted-foreground">
              <Info className="h-8 w-8 text-muted-foreground/50 mb-3" />
              <h3 className="text-sm font-medium text-foreground mb-1">No Thermal Data</h3>
              <p className="text-xs max-w-sm mb-4 text-muted-foreground">
                Set active medium properties, pump powers, cooling convection parameters, and click "Run Simulation" to solve rate equations and radial heat transfer.
              </p>
            </div>
          )}

          {loading && (
            <div className="h-[550px] flex flex-col items-center justify-center border border-dashed border-border bg-card/10 rounded-2xl text-center p-8 text-muted-foreground">
              <Loader2 className="h-8 w-8 text-primary animate-spin mb-3" />
              <h3 className="text-sm font-medium text-foreground mb-1">Solving Laser Steady-State Dynamics...</h3>
              <p className="text-xs">Propagating pump & signal equations using relaxation iteration methods, and evaluating cylindrical heat generation grids.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
