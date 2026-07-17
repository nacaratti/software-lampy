import { PlotlyChart } from "./PlotlyChart";
import type { BPMResponse } from "@/types/bpm";

interface BPMPowerVsZProps {
  response: BPMResponse;
  height?: number;
}

export function BPMPowerVsZ({ response, height = 240 }: BPMPowerVsZProps) {
  return (
    <PlotlyChart
      height={height}
      exportFilename="bpm_power_vs_z"
      data={[
        {
          x: response.z_mm,
          y: response.power_vs_z,
          type: "scatter",
          mode: "lines",
          line: { color: "#22D3EE", width: 2.5 },
          fill: "tozeroy",
          fillcolor: "rgba(34, 211, 238, 0.12)",
          hovertemplate: "z=%{x:.2f} mm<br>P=%{y:.4f}<extra></extra>",
        },
      ]}
      layout={{
        xaxis: { title: { text: "z (mm)" } },
        yaxis: { title: { text: "Total power (a.u.)" } },
        showlegend: false,
        margin: { t: 8, r: 8, b: 44, l: 56 },
      }}
    />
  );
}
