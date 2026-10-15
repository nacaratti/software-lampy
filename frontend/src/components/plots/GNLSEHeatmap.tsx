import { useMemo } from "react";
import { PlotlyChart } from "./PlotlyChart";
import { decodeArray, reshape2D } from "@/lib/encoding";
import type { EncodedArray } from "@/types/common";

interface GNLSEHeatmapProps {
  z_mm: number[];
  xAxis: number[];
  xLabel: string;
  slices: EncodedArray; // shape (Nz_saved, N)
  zLabel?: string;
  exportFilename?: string;
  height?: number;
}

const HEAT_COLORSCALE: [number, string][] = [
  [0, "rgba(15, 12, 30, 1)"],
  [0.25, "#3B1F73"],
  [0.5, "#7C3AED"],
  [0.75, "#D946EF"],
  [1, "#FBBF24"],
];

/** Power evolution heatmap: x-axis (time or wavelength) vs z, reused for both
 * the temporal and spectral views of a GNLSE pulse propagation run. */
export function GNLSEHeatmap({
  z_mm, xAxis, xLabel, slices, zLabel = "Power", exportFilename, height = 280,
}: GNLSEHeatmapProps) {
  const dec = useMemo(() => decodeArray(slices), [slices]);

  if (dec.kind !== "real") {
    return <div className="text-sm text-destructive">Unexpected complex array</div>;
  }
  const [rows, cols] = dec.shape;
  const matrix = reshape2D(dec.data, rows, cols);

  return (
    <PlotlyChart
      height={height}
      exportFilename={exportFilename}
      data={[
        {
          x: xAxis,
          y: z_mm,
          z: matrix,
          type: "heatmap",
          colorscale: HEAT_COLORSCALE as any,
          showscale: true,
          colorbar: {
            title: { text: zLabel, side: "right" },
            tickfont: { size: 10 },
            outlinewidth: 0,
            len: 0.8,
            thickness: 12,
          },
          hovertemplate: `${xLabel}=%{x:.3f}<br>z=%{y:.3f} mm<br>${zLabel}=%{z:.3e}<extra></extra>`,
        },
      ]}
      layout={{
        xaxis: { title: { text: xLabel }, zeroline: false },
        yaxis: { title: { text: "z (mm)" }, zeroline: false },
        margin: { t: 8, r: 8, b: 44, l: 56 },
      }}
    />
  );
}
