import { useState } from "react";
import { toast } from "sonner";
import { Play, Loader2, Info, ScanLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { NumberField } from "@/components/common/NumberField";
import { PageHeader } from "@/components/layout/PageHeader";
import { PlotlyChart } from "@/components/plots/PlotlyChart";
import { api } from "@/lib/api";
import { useSyncJob } from "@/lib/syncJob";
import type { FBGCalculationResponse, PhaseMaskResponse } from "@/types/fbg";

type GratingType = "uniform" | "chirped" | "apodized" | "tilted" | "lpg";

export function FBGPage() {
  const [gratingType, setGratingType] = useState<GratingType>("uniform");
  const [nEff, setNEff] = useState(1.45);
  const [lengthMm, setLengthMm] = useState(10.0);
  const [dn, setDn] = useState(1e-4);
  const [periodNm, setPeriodNm] = useState(535.0);
  const [periodUm, setPeriodUm] = useState(500.0);
  
  // Chirp
  const [periodEndNm, setPeriodEndNm] = useState(536.0);
  const [chirpType, setChirpType] = useState<"linear" | "quadratic">("linear");
  
  // Apodization
  const [apodizationProfile, setApodizationProfile] = useState<"gaussian" | "raised_cosine" | "tanh" | "hamming">("gaussian");
  const [profileStrength, setProfileStrength] = useState(1.0);
  
  // Tilted
  const [nEffCladdingBase, setNEffCladdingBase] = useState(1.44);
  const [tiltAngleDeg, setTiltAngleDeg] = useState(2.0);
  const [numCladdingModes, setNumCladdingModes] = useState(10);
  
  // LPG
  const [nEffCladding, setNEffCladding] = useState(1.44);
  const [targetModeOrder, setTargetModeOrder] = useState(2);

  // Wavelength limits (optional)
  const [wlStart, setWlStart] = useState<number | null>(null);
  const [wlEnd, setWlEnd] = useState<number | null>(null);
  const [numPoints, setNumPoints] = useState(1000);
  const [numSections, setNumSections] = useState(200);

  // UV writing laser
  const [lambdaUvNm, setLambdaUvNm] = useState(248.0);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FBGCalculationResponse | null>(null);
  const [phaseMaskLoading, setPhaseMaskLoading] = useState(false);
  const [phaseMask, setPhaseMask] = useState<PhaseMaskResponse | null>(null);
  const runSync = useSyncJob();

  async function runSimulation() {
    setLoading(true);
    setPhaseMask(null);
    const req = {
      grating_type: gratingType,
      n_eff: nEff,
      length_mm: lengthMm,
      dn: dn,
      period_nm: periodNm,
      period_um: periodUm,
      period_end_nm: periodEndNm,
      chirp_type: chirpType,
      apodization_profile: apodizationProfile,
      profile_strength: profileStrength,
      n_eff_cladding_base: nEffCladdingBase,
      tilt_angle_deg: tiltAngleDeg,
      num_cladding_modes: numCladdingModes,
      n_eff_cladding: nEffCladding,
      target_mode_order: targetModeOrder,
      wl_start_nm: wlStart,
      wl_end_nm: wlEnd,
      num_points: numPoints,
      num_sections: numSections,
    };
    try {
      const res = await runSync(
        "fbg",
        `FBG ${gratingType} ${lengthMm}mm`,
        req,
        () => api.calculateFBG(req)
      );
      setResult(res);
      toast.success("Simulation completed successfully");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function computePhaseMask() {
    setPhaseMaskLoading(true);
    try {
      const res = await api.calculatePhaseMask({
        grating_type: gratingType,
        n_eff: nEff,
        length_mm: lengthMm,
        dn: dn,
        period_nm: periodNm,
        period_end_nm: periodEndNm,
        chirp_type: chirpType,
        apodization_profile: apodizationProfile,
        profile_strength: profileStrength,
        lambda_uv_nm: lambdaUvNm,
        num_sections: numSections,
      });
      setPhaseMask(res);
      toast.success("Phase mask computed");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setPhaseMaskLoading(false);
    }
  }

  const isTransmission = gratingType === "tilted" || gratingType === "lpg";
  const spectrumName = isTransmission ? "Transmission" : "Reflectivity";

  const chartData: Plotly.Data[] = result
    ? [
        {
          x: result.wavelengths_nm,
          y: result.spectrum,
          type: "scatter",
          mode: "lines",
          name: spectrumName,
          line: { color: isTransmission ? "#22D3EE" : "#A78BFA", width: 2 },
        },
      ]
    : [];

  return (
    <div className="container mx-auto py-8 max-w-6xl">
      <PageHeader
        eyebrow="Solver"
        title="FBG Solver"
        description="Compute reflectivity and transmission spectra of uniform, chirped, apodized, tilted FBGs, and LPGs using coupled-mode theory and Transfer Matrix Methods. Calculate the phase mask for UV inscription."
        actions={
          <Button variant="glow" size="sm" onClick={runSimulation} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {loading ? "Simulating..." : "Run Simulation"}
          </Button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Input Parameters panel */}
        <div className="lg:col-span-5 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Grating Type Selection</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label>Device Type</Label>
                <Select
                  value={gratingType}
                  onValueChange={(v) => {
                    setGratingType(v as GratingType);
                    setWlStart(null);
                    setWlEnd(null);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="uniform">Uniform FBG</SelectItem>
                    <SelectItem value="chirped">Chirped FBG</SelectItem>
                    <SelectItem value="apodized">Apodized FBG</SelectItem>
                    <SelectItem value="tilted">Tilted FBG</SelectItem>
                    <SelectItem value="lpg">Long Period Grating (LPG)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Grating Geometry & Core Index</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <NumberField
                  label={gratingType === "lpg" || gratingType === "tilted" ? "Core Effective Index" : "Effective Index (n_eff)"}
                  step={0.001}
                  min={1.0}
                  max={3.0}
                  value={nEff}
                  onChange={setNEff}
                />
              </div>
              <NumberField
                label="Length (L)"
                unit="mm"
                step={0.1}
                min={0.1}
                max={100.0}
                value={lengthMm}
                onChange={setLengthMm}
              />
              <NumberField
                label="Index Modulation (δn)"
                step={1e-5}
                min={1e-6}
                max={0.01}
                value={dn}
                onChange={setDn}
              />
              {gratingType !== "lpg" ? (
                <div className="col-span-2">
                  <NumberField
                    label="Grating Period (Λ)"
                    unit="nm"
                    step={0.1}
                    min={100.0}
                    max={2000.0}
                    value={periodNm}
                    onChange={setPeriodNm}
                  />
                </div>
              ) : (
                <div className="col-span-2">
                  <NumberField
                    label="Grating Period (Λ)"
                    unit="μm"
                    step={1.0}
                    min={10.0}
                    max={2000.0}
                    value={periodUm}
                    onChange={setPeriodUm}
                  />
                </div>
              )}
            </CardContent>
          </Card>

          {/* Grating Specific Cards */}
          {gratingType === "chirped" && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold">Chirp Configuration</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <NumberField
                  label="End Grating Period (Λ_end)"
                  unit="nm"
                  step={0.1}
                  min={100.0}
                  max={2000.0}
                  value={periodEndNm}
                  onChange={setPeriodEndNm}
                />
                <div className="space-y-1.5">
                  <Label>Chirp Profile</Label>
                  <Select value={chirpType} onValueChange={(v) => setChirpType(v as "linear" | "quadratic")}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="linear">Linear Chirp</SelectItem>
                      <SelectItem value="quadratic">Quadratic Chirp</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <NumberField
                  label="TMM Grid Sections"
                  step={10}
                  min={10}
                  max={1000}
                  value={numSections}
                  onChange={setNumSections}
                />
              </CardContent>
            </Card>
          )}

          {gratingType === "apodized" && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold">Apodization Configuration</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5">
                  <Label>Apodization Profile</Label>
                  <Select
                    value={apodizationProfile}
                    onValueChange={(v) => setApodizationProfile(v as any)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="gaussian">Gaussian</SelectItem>
                      <SelectItem value="raised_cosine">Raised Cosine</SelectItem>
                      <SelectItem value="tanh">Hyperbolic Tangent (tanh)</SelectItem>
                      <SelectItem value="hamming">Hamming</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <NumberField
                  label="Profile Width/Strength"
                  step={0.05}
                  min={0.01}
                  max={1.0}
                  value={profileStrength}
                  onChange={setProfileStrength}
                />
                <NumberField
                  label="TMM Grid Sections"
                  step={10}
                  min={10}
                  max={1000}
                  value={numSections}
                  onChange={setNumSections}
                />
              </CardContent>
            </Card>
          )}

          {gratingType === "tilted" && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold">Tilted Grating Configuration</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <NumberField
                  label="Cladding Base Index"
                  step={0.001}
                  min={1.0}
                  max={2.0}
                  value={nEffCladdingBase}
                  onChange={setNEffCladdingBase}
                />
                <NumberField
                  label="Tilt Angle"
                  unit="deg"
                  step={0.5}
                  min={0.0}
                  max={45.0}
                  value={tiltAngleDeg}
                  onChange={setTiltAngleDeg}
                />
                <NumberField
                  label="Cladding Modes Count"
                  step={1}
                  min={1}
                  max={50}
                  value={numCladdingModes}
                  onChange={setNumCladdingModes}
                />
              </CardContent>
            </Card>
          )}

          {gratingType === "lpg" && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold">Long Period Grating Settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <NumberField
                  label="Cladding Mode index (n_clad)"
                  step={0.001}
                  min={1.0}
                  max={2.0}
                  value={nEffCladding}
                  onChange={setNEffCladding}
                />
                <NumberField
                  label="Target Cladding Mode Order (m)"
                  step={1}
                  min={1}
                  max={20}
                  value={targetModeOrder}
                  onChange={setTargetModeOrder}
                />
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Wavelength Simulation Range</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <NumberField
                label="Start (nm)"
                placeholder="Auto"
                step={0.5}
                min={200}
                max={3000}
                value={wlStart ?? NaN}
                onChange={(v) => setWlStart(Number.isFinite(v) ? v : null)}
              />
              <NumberField
                label="End (nm)"
                placeholder="Auto"
                step={0.5}
                min={200}
                max={3000}
                value={wlEnd ?? NaN}
                onChange={(v) => setWlEnd(Number.isFinite(v) ? v : null)}
              />
              <div className="col-span-2">
                <NumberField
                  label="Grid Points"
                  step={50}
                  min={100}
                  max={5000}
                  value={numPoints}
                  onChange={setNumPoints}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Results Panel */}
        <div className="lg:col-span-7 space-y-4">
          {result && (
            <>
              {/* Stats Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {result.metadata.bragg_wavelength_nm !== undefined && (
                  <Card className="bg-card/50 backdrop-blur-sm">
                    <CardContent className="p-4 text-center">
                      <div className="text-[10px] text-muted-foreground uppercase font-medium">Bragg Wavelength</div>
                      <div className="text-xl font-bold mt-1 text-primary">
                        {result.metadata.bragg_wavelength_nm.toFixed(2)} nm
                      </div>
                    </CardContent>
                  </Card>
                )}
                {result.metadata.peak_reflectivity !== undefined && (
                  <Card className="bg-card/50 backdrop-blur-sm">
                    <CardContent className="p-4 text-center">
                      <div className="text-[10px] text-muted-foreground uppercase font-medium">Peak Reflectivity</div>
                      <div className="text-xl font-bold mt-1 text-cyan-400">
                        {(result.metadata.peak_reflectivity * 100).toFixed(2)}%
                      </div>
                    </CardContent>
                  </Card>
                )}
                {result.metadata.fwhm_nm !== null && result.metadata.fwhm_nm !== undefined && (
                  <Card className="bg-card/50 backdrop-blur-sm">
                    <CardContent className="p-4 text-center">
                      <div className="text-[10px] text-muted-foreground uppercase font-medium">FWHM Bandwidth</div>
                      <div className="text-xl font-bold mt-1 text-purple-400">
                        {result.metadata.fwhm_nm.toFixed(3)} nm
                      </div>
                    </CardContent>
                  </Card>
                )}
                {result.metadata.min_transmission !== undefined && (
                  <Card className="bg-card/50 backdrop-blur-sm">
                    <CardContent className="p-4 text-center">
                      <div className="text-[10px] text-muted-foreground uppercase font-medium">Min Transmission</div>
                      <div className="text-xl font-bold mt-1 text-pink-400">
                        {(result.metadata.min_transmission * 100).toFixed(2)}%
                      </div>
                    </CardContent>
                  </Card>
                )}
                {result.metadata.dip_depth_db !== undefined && (
                  <Card className="bg-card/50 backdrop-blur-sm">
                    <CardContent className="p-4 text-center">
                      <div className="text-[10px] text-muted-foreground uppercase font-medium">Dip Depth</div>
                      <div className="text-xl font-bold mt-1 text-orange-400">
                        {result.metadata.dip_depth_db.toFixed(1)} dB
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>

              {/* Chart Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold">Spectral Response</CardTitle>
                </CardHeader>
                <CardContent className="p-2">
                  <PlotlyChart
                    data={chartData}
                    exportFilename="fbg_spectrum"
                    layout={{
                      xaxis: { title: { text: "Wavelength (nm)" } },
                      yaxis: {
                        title: { text: spectrumName },
                        range: isTransmission ? [0, 1.05] : [-0.05, 1.05],
                      },
                      margin: { t: 10, r: 20, b: 40, l: 50 },
                    }}
                    height={380}
                  />
                </CardContent>
              </Card>

              {/* Tilted FBG Resonances details */}
              {gratingType === "tilted" && result.metadata.resonance_wavelengths_nm && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Cladding Mode Resonance Wavelengths
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="max-h-[160px] overflow-y-auto">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                      {result.metadata.resonance_wavelengths_nm.map((wl, idx) => (
                        <div key={idx} className="flex justify-between border-b border-border py-1 px-2 bg-secondary/20 rounded">
                          <span className="text-muted-foreground">Mode {idx + 1}:</span>
                          <span className="font-semibold text-primary">{wl.toFixed(2)} nm</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Phase Mask Button + UV Laser selector */}
              {gratingType !== "lpg" && (
                <div className="flex items-center justify-end gap-3">
                  <div className="flex items-center gap-2">
                    <Label className="text-xs text-muted-foreground whitespace-nowrap">Laser UV:</Label>
                    <Select
                      value={String(lambdaUvNm)}
                      onValueChange={(v) => setLambdaUvNm(Number(v))}
                    >
                      <SelectTrigger className="h-8 w-[160px] text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="244">244 nm (Ar⁺ ×2)</SelectItem>
                        <SelectItem value="248">248 nm (KrF)</SelectItem>
                        <SelectItem value="266">266 nm (Nd:YAG ×4)</SelectItem>
                        <SelectItem value="193">193 nm (ArF)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={computePhaseMask}
                    disabled={phaseMaskLoading}
                    className="gap-2"
                  >
                    {phaseMaskLoading
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <ScanLine className="h-3.5 w-3.5" />}
                    {phaseMaskLoading ? "Computing..." : "Compute Phase Mask"}
                  </Button>
                </div>
              )}

              {/* Phase Mask Results */}
              {phaseMask && <PhaseMaskSection data={phaseMask} gratingType={gratingType} />}
            </>
          )}

          {!result && !loading && (
            <div className="h-[450px] flex flex-col items-center justify-center border border-dashed border-border bg-card/10 rounded-2xl text-center p-8 text-muted-foreground">
              <Info className="h-8 w-8 text-muted-foreground/50 mb-3" />
              <h3 className="text-sm font-medium text-foreground mb-1">No Simulation Data</h3>
              <p className="text-xs max-w-sm mb-4 text-muted-foreground">
                Select your Bragg grating parameters and click "Run Simulation" to compute spectral reflectivity or transmission coefficients.
              </p>
            </div>
          )}

          {loading && (
            <div className="h-[450px] flex flex-col items-center justify-center border border-dashed border-border bg-card/10 rounded-2xl text-center p-8 text-muted-foreground">
              <Loader2 className="h-8 w-8 text-primary animate-spin mb-3" />
              <h3 className="text-sm font-medium text-foreground mb-1">Simulating device...</h3>
              <p className="text-xs">This will take a fraction of a second. Solving coupled-mode differential equations.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PhaseMaskSection({
  data,
  gratingType,
}: {
  data: PhaseMaskResponse;
  gratingType: string;
}) {
  const { params, z_mm, period_pm_nm, dn_profile, kappa_profile, phase_rad } = data;

  const isChirped = gratingType === "chirped";
  const isApodized = gratingType === "apodized";

  const periodIsFlat =
    Math.abs(params.period_pm_max_nm - params.period_pm_min_nm) < 0.001;

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center gap-2 pt-1">
        <ScanLine className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold">Phase Mask — Inscription Parameters</span>
      </div>

      {/* Key parameters */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Card className="bg-card/50 backdrop-blur-sm">
          <CardContent className="p-4 text-center">
            <div className="text-[10px] text-muted-foreground uppercase font-medium">λ_Bragg</div>
            <div className="text-xl font-bold mt-1 text-primary">
              {params.bragg_wavelength_nm.toFixed(3)} nm
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm">
          <CardContent className="p-4 text-center">
            <div className="text-[10px] text-muted-foreground uppercase font-medium">
              {isChirped ? "Λ_pm (center)" : "Λ_pm (period)"}
            </div>
            <div className="text-xl font-bold mt-1 text-cyan-400">
              {params.period_pm_center_nm.toFixed(3)} nm
            </div>
          </CardContent>
        </Card>
        {isChirped && (
          <Card className="bg-card/50 backdrop-blur-sm">
            <CardContent className="p-4 text-center">
              <div className="text-[10px] text-muted-foreground uppercase font-medium">Λ_pm (min–max)</div>
              <div className="text-base font-bold mt-1 text-indigo-400">
                {params.period_pm_min_nm.toFixed(2)} – {params.period_pm_max_nm.toFixed(2)} nm
              </div>
            </CardContent>
          </Card>
        )}
        <Card className="bg-card/50 backdrop-blur-sm">
          <CardContent className="p-4 text-center">
            <div className="text-[10px] text-muted-foreground uppercase font-medium">δn peak</div>
            <div className="text-xl font-bold mt-1 text-emerald-400">
              {params.dn_peak.toExponential(2)}
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm">
          <CardContent className="p-4 text-center">
            <div className="text-[10px] text-muted-foreground uppercase font-medium">κ·L</div>
            <div className="text-xl font-bold mt-1 text-amber-400">
              {params.kappa_L_product.toFixed(3)}
            </div>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm">
          <CardContent className="p-4 text-center">
            <div className="text-[10px] text-muted-foreground uppercase font-medium">Total phase</div>
            <div className="text-xl font-bold mt-1 text-rose-400">
              {params.phase_total_cycles.toFixed(0)} cycles
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Period profile — only interesting for chirped */}
      {(isChirped || !periodIsFlat) && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">Mask Period Profile Λ_pm(z)</CardTitle>
          </CardHeader>
          <CardContent className="p-2">
            <PlotlyChart
              data={[
                {
                  x: z_mm,
                  y: period_pm_nm,
                  type: "scatter",
                  mode: "lines",
                  name: "Λ_pm(z)",
                  line: { color: "#818CF8", width: 2 },
                },
              ]}
              layout={{
                xaxis: { title: { text: "Position z (mm)" } },
                yaxis: { title: { text: "Λ_pm (nm)" } },
                margin: { t: 10, r: 20, b: 40, l: 55 },
              }}
              height={240}
            />
          </CardContent>
        </Card>
      )}

      {/* δn profile — relevant for apodized */}
      {isApodized && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">Index Modulation Profile δn(z)</CardTitle>
          </CardHeader>
          <CardContent className="p-2">
            <PlotlyChart
              data={[
                {
                  x: z_mm,
                  y: dn_profile,
                  type: "scatter",
                  mode: "lines",
                  name: "δn(z)",
                  line: { color: "#34D399", width: 2 },
                  fill: "tozeroy",
                  fillcolor: "rgba(52,211,153,0.12)",
                } as Plotly.Data,
              ]}
              layout={{
                xaxis: { title: { text: "Position z (mm)" } },
                yaxis: { title: { text: "δn" } },
                margin: { t: 10, r: 20, b: 40, l: 65 },
              }}
              height={240}
            />
          </CardContent>
        </Card>
      )}

      {/* κ(z) and accumulated phase */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">Coupling Coefficient κ(z)</CardTitle>
          </CardHeader>
          <CardContent className="p-2">
            <PlotlyChart
              data={[
                {
                  x: z_mm,
                  y: kappa_profile,
                  type: "scatter",
                  mode: "lines",
                  name: "κ(z)",
                  line: { color: "#F59E0B", width: 2 },
                },
              ]}
              layout={{
                xaxis: { title: { text: "z (mm)" } },
                yaxis: { title: { text: "κ (m⁻¹)" } },
                margin: { t: 10, r: 10, b: 40, l: 60 },
              }}
              height={220}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">Accumulated Phase φ(z)</CardTitle>
          </CardHeader>
          <CardContent className="p-2">
            <PlotlyChart
              data={[
                {
                  x: z_mm,
                  y: phase_rad.map((v) => v / (2 * Math.PI)),
                  type: "scatter",
                  mode: "lines",
                  name: "φ(z) (cycles)",
                  line: { color: "#EC4899", width: 2 },
                },
              ]}
              layout={{
                xaxis: { title: { text: "z (mm)" } },
                yaxis: { title: { text: "Phase (cycles)" } },
                margin: { t: 10, r: 10, b: 40, l: 60 },
              }}
              height={220}
            />
          </CardContent>
        </Card>
      </div>

      {/* Diffraction geometry + viability */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">UV Writing Geometry</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">UV laser (λ)</span>
              <span className="font-mono font-medium">{params.lambda_uv_nm} nm</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Λ_pm center</span>
              <span className="font-mono font-medium">{params.period_pm_center_nm.toFixed(3)} nm</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Diffraction angle (±1)</span>
              <span className="font-mono font-medium">
                {params.diffraction_angle_deg !== null
                  ? `${params.diffraction_angle_deg.toFixed(2)}°`
                  : "N/A (λ_UV > Λ_pm)"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">κ · L</span>
              <span className="font-mono font-medium">{params.kappa_L_product.toFixed(3)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Expected R_peak</span>
              <span className="font-mono font-medium text-emerald-400">
                {(Math.tanh(params.kappa_L_product) ** 2 * 100).toFixed(1)}%
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">Fabrication Data</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between items-start gap-2">
              <span className="text-muted-foreground shrink-0">Viability</span>
              <span className={`text-right text-xs font-medium ${params.viable ? "text-emerald-400" : "text-amber-400"}`}>
                {params.viable ? "✓" : "⚠"} {params.viability_message}
              </span>
            </div>
            <div className="flex justify-between items-start gap-2">
              <span className="text-muted-foreground shrink-0">Technique</span>
              <span className="text-right text-xs">{params.recommended_technique}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Required precision</span>
              <span className="font-mono font-medium">±{params.required_precision_nm.toFixed(1)} nm</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Typical fluence</span>
              <span className="font-mono text-xs">{params.typical_fluence}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Total phase</span>
              <span className="font-mono font-medium">{params.phase_total_cycles.toFixed(0)} cycles</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Physics note */}
      <Card className="border-dashed border-primary/30 bg-primary/5">
        <CardContent className="p-4 text-xs text-muted-foreground space-y-1">
          <p>
            <span className="font-medium text-foreground">Phase–FBG relation:</span>{" "}
            Λ_pm = 2 × Λ_FBG. The mask's ±1 diffraction orders interfere and create
            fringes with period Λ_FBG = Λ_pm/2, satisfying the Bragg condition λ_B = 2 n_eff Λ_FBG.
          </p>
          <p>
            <span className="font-medium text-foreground">Reverse mode (FBG → mask):</span>{" "}
            Λ_pm = λ_B / n_eff = {params.bragg_wavelength_nm.toFixed(3)} / n_eff ≈{" "}
            {params.period_pm_center_nm.toFixed(3)} nm.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
