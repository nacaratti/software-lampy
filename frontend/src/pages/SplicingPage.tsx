import { useState } from "react";
import { toast } from "sonner";
import { Play, Loader2, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { NumberField } from "@/components/common/NumberField";
import { PageHeader } from "@/components/layout/PageHeader";
import { PlotlyChart } from "@/components/plots/PlotlyChart";
import { api } from "@/lib/api";
import { decodeArray, reshape2D } from "@/lib/encoding";
import { useSyncJob } from "@/lib/syncJob";
import type { SplicingCalculationResponse } from "@/types/splicing";

export function SplicingPage() {
  // Fiber 1 (Source)
  const [coreN1, setCoreN1] = useState(1.45);
  const [cladN1, setCladN1] = useState(1.444);
  const [radius1, setRadius1] = useState(4.1);

  // Fiber 2 (Destination)
  const [coreN2, setCoreN2] = useState(1.45);
  const [cladN2, setCladN2] = useState(1.444);
  const [radius2, setRadius2] = useState(4.1);

  // Offsets and Tilts
  const [offsetX, setOffsetX] = useState(0.0);
  const [offsetY, setOffsetY] = useState(0.0);
  const [tiltX, setTiltX] = useState(0.0);
  const [tiltY, setTiltY] = useState(0.0);

  // Simulation Parameters
  const [wavelength, setWavelength] = useState(1550.0);
  const [gridSize, setGridSize] = useState(128);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SplicingCalculationResponse | null>(null);
  const runSync = useSyncJob();

  async function runSimulation() {
    if (cladN1 >= coreN1) {
      toast.error("Fiber 1: Cladding refractive index must be less than core refractive index");
      return;
    }
    if (cladN2 >= coreN2) {
      toast.error("Fiber 2: Cladding refractive index must be less than core refractive index");
      return;
    }

    setLoading(true);
    const req = {
      core_n1: coreN1,
      cladding_n1: cladN1,
      radius_um1: radius1,
      core_n2: coreN2,
      cladding_n2: cladN2,
      radius_um2: radius2,
      wavelength_nm: wavelength,
      offset_x_um: offsetX,
      offset_y_um: offsetY,
      tilt_x_mrad: tiltX,
      tilt_y_mrad: tiltY,
      grid_size: gridSize,
    };
    try {
      const res = await runSync(
        "splicing",
        `Splicing ${wavelength}nm`,
        req,
        () => api.calculateSplicing(req)
      );
      setResult(res);
      toast.success("Splicing calculation completed");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setLoading(false);
    }
  }

  // Pre-process plot data if result is available
  let field1Data: number[][] = [];
  let field2Data: number[][] = [];
  let extent = 0;
  let xs: number[] = [];
  let ys: number[] = [];
  let crossSectionX: number[] = [];
  let intensity1X: number[] = [];
  let intensity2X: number[] = [];

  if (result) {
    extent = result.extent_um;
    const dec1 = decodeArray(result.field_1);
    const dec2 = decodeArray(result.field_2);

    if (dec1.kind === "real" && dec2.kind === "real") {
      const [rows, cols] = dec1.shape;
      field1Data = reshape2D(dec1.data, rows, cols);
      field2Data = reshape2D(dec2.data, rows, cols);

      // Coordinate grids
      xs = Array.from({ length: cols }, (_, i) => -extent + (2 * extent * i) / (cols - 1));
      ys = Array.from({ length: rows }, (_, i) => -extent + (2 * extent * i) / (rows - 1));

      // Extract 1D cross-section at y = 0 (center row of grid)
      const centerYIdx = Math.floor(rows / 2);
      crossSectionX = xs;
      intensity1X = field1Data[centerYIdx] || [];
      intensity2X = field2Data[centerYIdx] || [];
    }
  }

  // Plot colorscale
  const heatMapColorscale = [
    [0, "rgba(15, 12, 30, 1)"],
    [0.25, "#3B1F73"],
    [0.5, "#7C3AED"],
    [0.75, "#D946EF"],
    [1, "#FBBF24"],
  ];

  return (
    <div className="container mx-auto py-8 max-w-6xl">
      <PageHeader
        eyebrow="Solver"
        title="Splicing Loss"
        description="Compute mode-coupling overlap integrals and coupling efficiency between step-index optical fibers. Analyze sensitivity to transverse misalignment and angular tilts."
        actions={
          <Button variant="glow" size="sm" onClick={runSimulation} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {loading ? "Calculating..." : "Run Solver"}
          </Button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Input Parameters Panel */}
        <div className="lg:col-span-5 space-y-4">
          
          {/* Fiber 1 Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Source Fiber (Fiber 1)</CardTitle>
              <CardDescription className="text-xs">Physical configuration of the input fiber</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-3 gap-3">
              <div className="col-span-1">
                <NumberField
                  label="Core Radius"
                  unit="μm"
                  step={0.1}
                  min={0.5}
                  max={50.0}
                  value={radius1}
                  onChange={setRadius1}
                />
              </div>
              <div className="col-span-1">
                <NumberField
                  label="Core Index"
                  step={0.001}
                  min={1.0}
                  max={3.0}
                  value={coreN1}
                  onChange={setCoreN1}
                />
              </div>
              <div className="col-span-1">
                <NumberField
                  label="Cladding Index"
                  step={0.001}
                  min={1.0}
                  max={3.0}
                  value={cladN1}
                  onChange={setCladN1}
                />
              </div>
            </CardContent>
          </Card>

          {/* Fiber 2 Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Destination Fiber (Fiber 2)</CardTitle>
              <CardDescription className="text-xs">Physical configuration of the output fiber</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-3 gap-3">
              <div className="col-span-1">
                <NumberField
                  label="Core Radius"
                  unit="μm"
                  step={0.1}
                  min={0.5}
                  max={50.0}
                  value={radius2}
                  onChange={setRadius2}
                />
              </div>
              <div className="col-span-1">
                <NumberField
                  label="Core Index"
                  step={0.001}
                  min={1.0}
                  max={3.0}
                  value={coreN2}
                  onChange={setCoreN2}
                />
              </div>
              <div className="col-span-1">
                <NumberField
                  label="Cladding Index"
                  step={0.001}
                  min={1.0}
                  max={3.0}
                  value={cladN2}
                  onChange={setCladN2}
                />
              </div>
            </CardContent>
          </Card>

          {/* Alignment & Misalignment Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Splicing Misalignment</CardTitle>
              <CardDescription className="text-xs">
                Offsets and tilt between core axes
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Offset X */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <Label>Lateral Offset X (Δx)</Label>
                  <span className="font-semibold text-primary">{offsetX.toFixed(1)} μm</span>
                </div>
                <Slider
                  value={[offsetX]}
                  onValueChange={([val]) => setOffsetX(val)}
                  min={-10}
                  max={10}
                  step={0.1}
                />
              </div>

              {/* Offset Y */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <Label>Lateral Offset Y (Δy)</Label>
                  <span className="font-semibold text-primary">{offsetY.toFixed(1)} μm</span>
                </div>
                <Slider
                  value={[offsetY]}
                  onValueChange={([val]) => setOffsetY(val)}
                  min={-10}
                  max={10}
                  step={0.1}
                />
              </div>

              {/* Tilt X */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <Label>Angular Tilt X (θx)</Label>
                  <span className="font-semibold text-cyan-400">{tiltX.toFixed(1)} mrad</span>
                </div>
                <Slider
                  value={[tiltX]}
                  onValueChange={([val]) => setTiltX(val)}
                  min={-20}
                  max={20}
                  step={0.5}
                />
              </div>

              {/* Tilt Y */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <Label>Angular Tilt Y (θy)</Label>
                  <span className="font-semibold text-cyan-400">{tiltY.toFixed(1)} mrad</span>
                </div>
                <Slider
                  value={[tiltY]}
                  onValueChange={([val]) => setTiltY(val)}
                  min={-20}
                  max={20}
                  step={0.5}
                />
              </div>
            </CardContent>
          </Card>

          {/* Grid Settings Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Solver & Source Settings</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <NumberField
                label="Wavelength"
                unit="nm"
                step={10.0}
                min={300.0}
                max={2500.0}
                value={wavelength}
                onChange={setWavelength}
              />
              <NumberField
                label="Grid Resolution"
                unit="px²"
                step={16}
                min={32}
                max={256}
                value={gridSize}
                onChange={setGridSize}
              />
            </CardContent>
          </Card>
        </div>

        {/* Results Panel */}
        <div className="lg:col-span-7 space-y-4">
          {result && (
            <>
              {/* Coupling Stats Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">LP01 Coupling</div>
                    <div className="text-xl font-bold mt-1 text-primary">
                      {(result.coupling_coefficient * 100).toFixed(2)}%
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">LP01 Splicing Loss</div>
                    <div className="text-xl font-bold mt-1 text-rose-400">
                      {result.loss_db === Infinity || isNaN(result.loss_db) ? "∞" : `${result.loss_db.toFixed(3)} dB`}
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Total Guided Coupling</div>
                    <div className="text-xl font-bold mt-1 text-emerald-400">
                      {(result.total_coupling * 100).toFixed(2)}%
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-card/50 backdrop-blur-sm">
                  <CardContent className="p-4 text-center">
                    <div className="text-[10px] text-muted-foreground uppercase font-medium">Total Splicing Loss</div>
                    <div className="text-xl font-bold mt-1 text-yellow-400">
                      {result.total_loss_db === Infinity || isNaN(result.total_loss_db)
                        ? "∞"
                        : `${result.total_loss_db.toFixed(3)} dB`}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Overlapping Fields visualization */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Source Fiber LP01 Mode Intensity
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-2">
                    <PlotlyChart
                      data={[
                        {
                          x: xs,
                          y: ys,
                          z: field1Data,
                          type: "heatmap",
                          colorscale: heatMapColorscale as any,
                          showscale: false,
                          hovertemplate: "x=%{x:.2f} µm<br>y=%{y:.2f} µm<br>I=%{z:.4f}<extra></extra>",
                        },
                      ]}
                      layout={{
                        xaxis: { title: { text: "x (µm)" }, scaleanchor: "y", scaleratio: 1, zeroline: false },
                        yaxis: { title: { text: "y (µm)" }, zeroline: false },
                        margin: { t: 8, r: 8, b: 35, l: 45 },
                      }}
                      height={260}
                    />
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Dest Fiber LP01 Mode Intensity
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-2">
                    <PlotlyChart
                      data={[
                        {
                          x: xs,
                          y: ys,
                          z: field2Data,
                          type: "heatmap",
                          colorscale: heatMapColorscale as any,
                          showscale: false,
                          hovertemplate: "x=%{x:.2f} µm<br>y=%{y:.2f} µm<br>I=%{z:.4f}<extra></extra>",
                        },
                      ]}
                      layout={{
                        xaxis: { title: { text: "x (µm)" }, scaleanchor: "y", scaleratio: 1, zeroline: false },
                        yaxis: { title: { text: "y (µm)" }, zeroline: false },
                        margin: { t: 8, r: 8, b: 35, l: 45 },
                      }}
                      height={260}
                    />
                  </CardContent>
                </Card>
              </div>

              {/* 1D Cross section Plot */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">1D Mode Field Overlay (x-axis cut at y=0)</CardTitle>
                </CardHeader>
                <CardContent className="p-2">
                  <PlotlyChart
                    data={[
                      {
                        x: crossSectionX,
                        y: intensity1X,
                        type: "scatter",
                        mode: "lines",
                        name: "Fiber 1 (Source)",
                        line: { color: "#A78BFA", width: 2.5 },
                      },
                      {
                        x: crossSectionX,
                        y: intensity2X,
                        type: "scatter",
                        mode: "lines",
                        name: "Fiber 2 (Dest, shifted/tilted)",
                        line: { color: "#FBBF24", width: 2.5, dash: "dash" },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Position x (μm)" }, zeroline: false },
                      yaxis: { title: { text: "Normalized Field Intensity" }, range: [-0.05, 1.05] },
                      margin: { t: 10, r: 20, b: 40, l: 50 },
                    }}
                    height={280}
                  />
                </CardContent>
              </Card>
            </>
          )}

          {!result && !loading && (
            <div className="h-[450px] flex flex-col items-center justify-center border border-dashed border-border bg-card/10 rounded-2xl text-center p-8 text-muted-foreground">
              <Info className="h-8 w-8 text-muted-foreground/50 mb-3" />
              <h3 className="text-sm font-medium text-foreground mb-1">No Simulation Results</h3>
              <p className="text-xs max-w-sm mb-4 text-muted-foreground">
                Set physical and alignment parameters for both fibers and click "Run Solver" to evaluate splicing loss.
              </p>
            </div>
          )}

          {loading && (
            <div className="h-[450px] flex flex-col items-center justify-center border border-dashed border-border bg-card/10 rounded-2xl text-center p-8 text-muted-foreground">
              <Loader2 className="h-8 w-8 text-primary animate-spin mb-3" />
              <h3 className="text-sm font-medium text-foreground mb-1">Evaluating Coupling Integrals...</h3>
              <p className="text-xs">Computing LP01 mode fields and projecting overlapping coordinate structures.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
