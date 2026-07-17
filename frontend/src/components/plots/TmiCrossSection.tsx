import { useMemo } from "react";
import { PlotlyChart } from "./PlotlyChart";
import { decodeArray, reshape2D } from "@/lib/encoding";
import type { EncodedArray } from "@/types/common";

interface TmiCrossSectionProps {
  lp01Image: EncodedArray;
  lp11Image: EncodedArray | null;
  xUm: number[];
  yUm: number[];
  couplingFraction: number;
  height?: number;
}

const CCD_COLORSCALE: [number, string][] = [
  [0, "#000000"],
  [0.25, "#1a0a3c"],
  [0.5, "#7c2d8f"],
  [0.75, "#e0447a"],
  [0.9, "#ffb454"],
  [1, "#ffffff"],
];

/** Fiber-facet cross-section blending the pure LP01 and LP11 near-field
 * intensities by the coupling fraction at the currently-selected power step
 * — lets the user literally watch the LP11 lobes emerge as pump power (and
 * therefore TMI risk) increases. Blended client-side so the slider updates
 * instantly without re-querying the backend. */
export function TmiCrossSection({
  lp01Image, lp11Image, xUm, yUm, couplingFraction, height = 260,
}: TmiCrossSectionProps) {
  const dec01 = useMemo(() => decodeArray(lp01Image), [lp01Image]);
  const dec11 = useMemo(() => (lp11Image ? decodeArray(lp11Image) : null), [lp11Image]);

  if (dec01.kind !== "real" || (dec11 && dec11.kind !== "real")) {
    return <div className="text-sm text-destructive">Unexpected complex image data</div>;
  }

  const [Nx, Ny] = dec01.shape;
  const f = Math.max(0, Math.min(1, couplingFraction));

  const blended = new Float32Array(dec01.data.length);
  for (let i = 0; i < blended.length; i++) {
    const i01 = dec01.data[i] * (1 - f);
    const i11 = dec11 ? dec11.data[i] * f : 0;
    blended[i] = i01 + i11;
  }
  const peak = blended.reduce((m, v) => Math.max(m, v), 0) || 1;
  for (let i = 0; i < blended.length; i++) blended[i] /= peak;

  const matrix = reshape2D(blended, Nx, Ny);
  // Transpose so Plotly's z[row=y][col=x] convention matches the (x,y)-indexed grid.
  const zGrid: number[][] = yUm.map((_, j) => xUm.map((_, i) => matrix[i][j]));

  return (
    <PlotlyChart
      height={height}
      data={[
        {
          x: xUm, y: yUm, z: zGrid,
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
  );
}
