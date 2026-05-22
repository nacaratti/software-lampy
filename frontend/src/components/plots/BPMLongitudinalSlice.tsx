import { useMemo } from "react";
import { PlotlyChart } from "./PlotlyChart";
import { decodeArray } from "@/lib/encoding";
import type { BPMResponse } from "@/types/bpm";

interface BPMLongitudinalSliceProps {
  response: BPMResponse;
  height?: number;
}

export function BPMLongitudinalSlice({ response, height = 300 }: BPMLongitudinalSliceProps) {
  const dec = useMemo(() => decodeArray(response.intensity_slices), [response]);

  if (dec.kind !== "real") {
    return <div className="text-sm text-destructive">Unexpected complex array</div>;
  }

  const [Nz, Nx, Ny] = dec.shape;
  const data3d = dec.data;

  // Extract the YZ plane at the central X slice (x_idx = Nx / 2)
  const x_idx = Math.floor(Nx / 2);
  const z_coords = useMemo(() => {
    return response.z_step_indices.map((idx) => response.z_mm[idx]);
  }, [response.z_step_indices, response.z_mm]);

  const yzMatrix = useMemo(() => {
    const matrix: number[][] = [];
    for (let y = 0; y < Ny; y++) {
      const row: number[] = [];
      for (let z = 0; z < Nz; z++) {
        // Index mapping: z * Nx * Ny + x * Ny + y
        const val = data3d[z * Nx * Ny + x_idx * Ny + y];
        row.push(val);
      }
      matrix.push(row);
    }
    return matrix;
  }, [data3d, Nz, Nx, Ny, x_idx]);

  return (
    <PlotlyChart
      height={height}
      data={[
        {
          x: z_coords,
          y: response.y_um,
          z: yzMatrix,
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
            len: 0.8,
            thickness: 12,
          },
          hovertemplate: "z=%{x:.3f} mm<br>y=%{y:.2f} µm<br>I=%{z:.3e}<extra></extra>",
        },
      ]}
      layout={{
        xaxis: { title: { text: "z (mm)" }, zeroline: false },
        yaxis: { title: { text: "y (µm)" }, zeroline: false },
        margin: { t: 8, r: 8, b: 44, l: 56 },
      }}
    />
  );
}
