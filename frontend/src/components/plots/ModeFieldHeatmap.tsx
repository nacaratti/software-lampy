import { PlotlyChart } from "./PlotlyChart";
import { decodeArray, reshape2D } from "@/lib/encoding";
import type { ModeResult } from "@/types/modes";

interface ModeFieldHeatmapProps {
  mode: ModeResult;
  height?: number;
}

export function ModeFieldHeatmap({ mode, height = 360 }: ModeFieldHeatmapProps) {
  const dec = decodeArray(mode.intensity_2d);
  if (dec.kind !== "real") {
    return <div className="text-sm text-destructive">Unexpected complex array</div>;
  }
  const [rows, cols] = dec.shape;
  const z = reshape2D(dec.data, rows, cols);
  const extent = mode.extent_um;
  const xs = Array.from({ length: cols }, (_, i) =>
    -extent + (2 * extent * i) / (cols - 1)
  );
  const ys = Array.from({ length: rows }, (_, i) =>
    -extent + (2 * extent * i) / (rows - 1)
  );

  return (
    <PlotlyChart
      height={height}
      data={[
        {
          x: xs,
          y: ys,
          z,
          type: "heatmap",
          colorscale: [
            [0, "rgba(15, 12, 30, 1)"],
            [0.25, "#3B1F73"],
            [0.5, "#7C3AED"],
            [0.75, "#D946EF"],
            [1, "#FBBF24"],
          ] as any,
          showscale: false,
          hovertemplate: "x=%{x:.2f} µm<br>y=%{y:.2f} µm<br>I=%{z:.3e}<extra></extra>",
        },
      ]}
      layout={{
        xaxis: { title: { text: "x (µm)" }, scaleanchor: "y", scaleratio: 1, zeroline: false },
        yaxis: { title: { text: "y (µm)" }, zeroline: false },
        margin: { t: 8, r: 8, b: 44, l: 56 },
      }}
    />
  );
}
