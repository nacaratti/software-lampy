import { useMemo, useState } from "react";
import { PlotlyChart } from "./PlotlyChart";
import { decodeArray, slice2DFrom3D } from "@/lib/encoding";
import { Slider } from "@/components/ui/slider";
import type { BPMResponse } from "@/types/bpm";

interface BPMZSliceProps {
  response: BPMResponse;
  height?: number;
}

export function BPMZSlice({ response, height = 480 }: BPMZSliceProps) {
  const dec = useMemo(() => decodeArray(response.intensity_slices), [response]);
  const [Nz, Nx, Ny] = dec.shape;
  const [idx, setIdx] = useState(0);

  if (dec.kind !== "real") {
    return <div className="text-sm text-destructive">Unexpected complex array</div>;
  }

  const slice = slice2DFrom3D(dec.data, dec.shape, idx);
  const zIndex = response.z_step_indices[idx];
  const z_mm = response.z_mm[zIndex];

  return (
    <div className="space-y-3">
      <PlotlyChart
        height={height}
        data={[
          {
            x: response.x_um,
            y: response.y_um,
            z: slice,
            type: "heatmap",
            colorscale: [
              [0, "rgba(15, 12, 30, 1)"],
              [0.25, "#3B1F73"],
              [0.5, "#7C3AED"],
              [0.75, "#D946EF"],
              [1, "#FBBF24"],
            ] as any,
            showscale: true,
            colorbar: {
              tickfont: { color: "rgba(230,230,240,0.6)", size: 10 },
              outlinewidth: 0,
              len: 0.7,
              thickness: 12,
            },
            hovertemplate: "x=%{x:.2f} µm<br>y=%{y:.2f} µm<br>I=%{z:.3e}<extra></extra>",
          },
        ]}
        layout={{
          xaxis: { title: { text: "x (µm)" }, scaleanchor: "y", scaleratio: 1, zeroline: false },
          yaxis: { title: { text: "y (µm)" }, zeroline: false },
          margin: { t: 8, r: 8, b: 44, l: 56 },
        }}
      />

      <div className="flex items-center gap-4 px-1">
        <div className="text-[11px] text-muted-foreground font-mono shrink-0 w-28">
          z = {z_mm.toFixed(3)} mm
        </div>
        <Slider
          min={0}
          max={Nz - 1}
          step={1}
          value={[idx]}
          onValueChange={(v) => setIdx(v[0])}
          className="flex-1"
        />
        <div className="text-[11px] text-muted-foreground font-mono shrink-0 w-20 text-right">
          {idx + 1} / {Nz}
        </div>
      </div>
    </div>
  );
}
