import { useMemo, useState } from "react";
import { PlotlyChart } from "./PlotlyChart";
import { Slider } from "@/components/ui/slider";

interface ThermalCrossSectionProps {
  /** Radial coordinate grid (µm), same convention as ThermalCalculationResponse.r_um. */
  rUm: number[];
  /** T(r, z) in °C, shape [r_points][z_points] (as decoded by reshape2D). */
  t2d: number[][];
  /** Longitudinal coordinate (m), one entry per z_points column of t2d. */
  zM: number[];
  colorscale: (string | number)[][];
  height?: number;
  gridN?: number;
}

/** Linear interpolation of a 1D radial profile at radius r (µm). */
function interpRadial(r: number, rGrid: number[], values: number[]): number {
  if (r <= rGrid[0]) return values[0];
  const last = rGrid.length - 1;
  if (r >= rGrid[last]) return values[last];
  // rGrid is monotonically increasing (matches backend's np.linspace(0, c, num_r_points))
  let lo = 0;
  let hi = last;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (rGrid[mid] <= r) lo = mid;
    else hi = mid;
  }
  const t = (r - rGrid[lo]) / (rGrid[hi] - rGrid[lo]);
  return values[lo] + t * (values[hi] - values[lo]);
}

/** Revolves the radial temperature profile T(r) into a true circular fiber
 * cross-section (x, y), like a thermal camera pointed at the fiber end face,
 * at a z position selectable via the slider. Complements the T(r,z) "unrolled"
 * heatmap with the actual disc shape a physical cross-section would show. */
export function ThermalCrossSection({ rUm, t2d, zM, colorscale, height = 340, gridN = 96 }: ThermalCrossSectionProps) {
  const numZ = zM.length;
  const [zIdx, setZIdx] = useState(numZ - 1);

  const { xGrid, yGrid, grid } = useMemo(() => {
    const rMax = rUm[rUm.length - 1];
    const column = t2d.map((row) => row[zIdx]);
    const x = Array.from({ length: gridN }, (_, i) => -rMax + (2 * rMax * i) / (gridN - 1));
    const y = Array.from({ length: gridN }, (_, i) => -rMax + (2 * rMax * i) / (gridN - 1));
    const z: (number | null)[][] = [];
    for (let j = 0; j < gridN; j++) {
      const row: (number | null)[] = [];
      for (let i = 0; i < gridN; i++) {
        const r = Math.hypot(x[i], y[j]);
        row.push(r <= rMax ? interpRadial(r, rUm, column) : null);
      }
      z.push(row);
    }
    return { xGrid: x, yGrid: y, grid: z };
  }, [rUm, t2d, zIdx, gridN]);

  return (
    <div className="space-y-2">
      <PlotlyChart
        height={height}
        data={[
          {
            x: xGrid,
            y: yGrid,
            z: grid,
            type: "heatmap",
            colorscale: colorscale as any,
            zsmooth: "best" as any,
            colorbar: { title: { text: "T (°C)" }, titleside: "right" } as any,
            hovertemplate: "x=%{x:.1f} µm<br>y=%{y:.1f} µm<br>T=%{z:.1f} °C<extra></extra>",
          },
        ]}
        layout={{
          xaxis: { title: { text: "x (µm)" }, scaleanchor: "y", scaleratio: 1, zeroline: false },
          yaxis: { title: { text: "y (µm)" }, zeroline: false },
          margin: { t: 10, r: 10, b: 40, l: 50 },
        }}
      />
      <div className="flex items-center gap-4 px-1">
        <div className="text-[11px] text-muted-foreground font-mono shrink-0 w-28">
          z = {zM[zIdx].toFixed(3)} m
        </div>
        <Slider min={0} max={numZ - 1} step={1} value={[zIdx]} onValueChange={(v) => setZIdx(v[0])} className="flex-1" />
        <div className="text-[11px] text-muted-foreground font-mono shrink-0 w-20 text-right">
          {zIdx + 1} / {numZ}
        </div>
      </div>
    </div>
  );
}
