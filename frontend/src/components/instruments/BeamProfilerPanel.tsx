import { useMemo, useState } from "react";
import { PlotlyChart } from "@/components/plots/PlotlyChart";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { decodeArray, slice2DFrom3D } from "@/lib/encoding";
import type { BeamProfilerData } from "@/types/system";

interface BeamProfilerPanelProps {
  beam: BeamProfilerData;
}

const CCD_COLORSCALE: [number, string][] = [
  [0, "#000000"],
  [0.25, "#1a0a3c"],
  [0.5, "#7c2d8f"],
  [0.75, "#e0447a"],
  [0.9, "#ffb454"],
  [1, "#ffffff"],
];

/** Virtual CCD camera: intensity image at a chosen z, cross-section cuts, and
 * the M^2 caustic (ISO 11146). The z-plane index is decoupled from what plane
 * is actually shown as `slice`; the caustic marker follows the slider. */
export function BeamProfilerPanel({ beam }: BeamProfilerPanelProps) {
  const x_m = useMemo(() => Array.from(decodeArray(beam.x_m).data), [beam.x_m]);
  const y_m = useMemo(() => Array.from(decodeArray(beam.y_m).data), [beam.y_m]);
  const z_m = useMemo(() => Array.from(decodeArray(beam.z_m).data), [beam.z_m]);
  const wx_m = useMemo(() => Array.from(decodeArray(beam.wx_m).data), [beam.wx_m]);
  const wy_m = useMemo(() => Array.from(decodeArray(beam.wy_m).data), [beam.wy_m]);
  const imagesDec = useMemo(() => decodeArray(beam.images), [beam.images]);

  const [zIdx, setZIdx] = useState(beam.waist_index);

  if (imagesDec.kind !== "real") {
    return <div className="text-sm text-destructive">Unexpected complex beam image data</div>;
  }
  const [Nz, Nx, Ny] = imagesDec.shape;
  const slice = slice2DFrom3D(imagesDec.data, imagesDec.shape, zIdx);

  const xUm = x_m.map((v) => v * 1e6);
  const yUm = y_m.map((v) => v * 1e6);
  const zMm = z_m.map((v) => v * 1e3);
  const wxUm = wx_m.map((v) => v * 1e6);
  const wyUm = wy_m.map((v) => v * 1e6);

  // Transpose so Plotly's z[row=y][col=x] convention matches our (x,y)-indexed slice.
  const zGrid: number[][] = yUm.map((_, j) => xUm.map((_, i) => slice[i][j]));
  const rowIdx = Math.floor(Nx / 2);
  const colIdx = Math.floor(Ny / 2);
  const xCut = slice.map((row) => row[colIdx]); // intensity(x, y=0)
  const yCut = slice[rowIdx];                   // intensity(x=0, y)

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant="outline" className="text-primary border-primary/50">
          M²x {beam.m2x.toFixed(2)}
        </Badge>
        <Badge variant="outline" className="text-primary border-primary/50">
          M²y {beam.m2y.toFixed(2)}
        </Badge>
        <Badge variant="outline">w0 {(0.5 * (beam.w0x_m + beam.w0y_m) * 1e6).toFixed(2)} µm</Badge>
        <Badge variant="outline">
          θ {(0.5 * (beam.divergence_x_mrad + beam.divergence_y_mrad)).toFixed(2)} mrad
        </Badge>
        <Badge variant="outline">BPP {beam.bpp_mm_mrad.toFixed(3)} mm·mrad</Badge>
        <Badge variant={beam.is_single_mode ? "secondary" : "outline"}>
          V={beam.v_number.toFixed(2)} {beam.is_single_mode ? "single-mode" : "multimode"}
        </Badge>
        {beam.tmi_risk_fraction !== undefined && (
          <Badge
            variant="outline"
            className={beam.tmi_risk_fraction > 0.5 ? "text-amber-400 border-amber-500/50" : ""}
            title="Thermally-induced index perturbation vs. the fiber's intrinsic LP01-LP11 gap — a qualitative TMI risk indicator, not a validated power threshold."
          >
            TMI risk {beam.tmi_risk_fraction.toFixed(2)}
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
            CCD frame — z = {zMm[zIdx].toFixed(3)} mm
          </p>
          <PlotlyChart
            height={220}
            data={[
              {
                x: xUm,
                y: yUm,
                z: zGrid,
                type: "heatmap",
                colorscale: CCD_COLORSCALE as any,
                showscale: false,
                hovertemplate: "x=%{x:.2f} µm<br>y=%{y:.2f} µm<br>I=%{z:.3f}<extra></extra>",
              },
            ]}
            layout={{
              xaxis: { title: { text: "x (µm)" }, scaleanchor: "y", scaleratio: 1, zeroline: false },
              yaxis: { title: { text: "y (µm)" }, zeroline: false },
              margin: { t: 4, r: 4, b: 36, l: 44 },
            }}
          />
          <Slider
            className="mt-2"
            min={0}
            max={Nz - 1}
            step={1}
            value={[zIdx]}
            onValueChange={(v) => setZIdx(v[0])}
          />
        </div>

        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
            Cross-sections at this plane
          </p>
          <PlotlyChart
            height={220}
            exportFilename="beam_cross_sections"
            data={[
              { x: xUm, y: xCut, type: "scatter", mode: "lines", name: "X (y=0)", line: { color: "#34d399" } },
              { x: yUm, y: yCut, type: "scatter", mode: "lines", name: "Y (x=0)", line: { color: "#22D3EE" } },
            ]}
            layout={{
              xaxis: { title: { text: "Position (µm)" } },
              yaxis: { title: { text: "Norm. intensity" } },
              margin: { t: 4, r: 4, b: 36, l: 44 },
              legend: { orientation: "h", y: -0.25 },
            }}
          />
        </div>
      </div>

      <div>
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
          Caustic — beam radius vs. z (ISO 11146 hyperbolic fit)
        </p>
        <PlotlyChart
          height={220}
          exportFilename="beam_caustic_m2"
          data={[
            { x: zMm, y: wxUm, type: "scatter", mode: "lines", name: "wx(z)", line: { color: "#34d399" } },
            { x: zMm, y: wyUm, type: "scatter", mode: "lines", name: "wy(z)", line: { color: "#22D3EE" } },
            {
              x: [zMm[zIdx]],
              y: [wxUm[zIdx]],
              type: "scatter",
              mode: "markers",
              marker: { color: "#FBBF24", size: 9, symbol: "diamond" },
              showlegend: false,
              hovertemplate: "camera plane<extra></extra>",
            },
          ]}
          layout={{
            xaxis: { title: { text: "z (mm)" } },
            yaxis: { title: { text: "Beam radius (µm)" } },
            margin: { t: 4, r: 4, b: 36, l: 44 },
            legend: { orientation: "h", y: -0.25 },
          }}
        />
      </div>
    </div>
  );
}
