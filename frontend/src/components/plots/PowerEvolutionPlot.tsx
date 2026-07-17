import { PlotlyChart } from "./PlotlyChart";
import { decodeArray, reshape2D } from "@/lib/encoding";
import type { PowerASEResponse } from "@/types/power";

interface PowerEvolutionPlotProps {
  response: PowerASEResponse;
  showASE?: boolean;
  height?: number;
}

function decode2D(enc: PowerASEResponse["pumps_forward"]): number[][] {
  const dec = decodeArray(enc);
  const [rows, cols] = dec.shape;
  if (rows === 0 || cols === 0) return [];
  return reshape2D(dec.data, rows, cols);
}

export function PowerEvolutionPlot({ response, showASE = true, height = 420 }: PowerEvolutionPlotProps) {
  const traces: Plotly.Data[] = [];
  const pf = decode2D(response.pumps_forward);
  const pb = decode2D(response.pumps_backward);
  const sf = decode2D(response.signals_forward);
  const sb = decode2D(response.signals_backward);
  const af = decode2D(response.ase_forward);
  const ab = decode2D(response.ase_backward);
  const z = response.z_m;

  pf.forEach((y, i) => traces.push({
    x: z, y, name: `Pump f λ=${response.pump_wavelengths_nm[i].toFixed(0)} nm`,
    type: "scatter", mode: "lines",
    line: { color: "#F472B6", width: 2 },
  }));
  pb.forEach((y, i) => traces.push({
    x: z, y, name: `Pump b λ=${response.pump_wavelengths_nm[i].toFixed(0)} nm`,
    type: "scatter", mode: "lines",
    line: { color: "#F472B6", width: 2, dash: "dash" },
  }));
  sf.forEach((y, i) => traces.push({
    x: z, y, name: `Signal f λ=${response.signal_wavelengths_nm[i].toFixed(0)} nm`,
    type: "scatter", mode: "lines",
    line: { color: "#22D3EE", width: 2.5 },
  }));
  sb.forEach((y, i) => traces.push({
    x: z, y, name: `Signal b λ=${response.signal_wavelengths_nm[i].toFixed(0)} nm`,
    type: "scatter", mode: "lines",
    line: { color: "#22D3EE", width: 2.5, dash: "dash" },
  }));

  if (showASE && af.length > 0) {
    const totalASE_f = z.map((_, i) => af.reduce((s, ch) => s + ch[i], 0));
    const totalASE_b = z.map((_, i) => ab.reduce((s, ch) => s + ch[i], 0));
    traces.push({
      x: z, y: totalASE_f, name: "Total ASE (forward)",
      type: "scatter", mode: "lines",
      line: { color: "#A78BFA", width: 1.5 },
    });
    traces.push({
      x: z, y: totalASE_b, name: "Total ASE (backward)",
      type: "scatter", mode: "lines",
      line: { color: "#A78BFA", width: 1.5, dash: "dash" },
    });
  }

  return (
    <PlotlyChart
      height={height}
      exportFilename="power_evolution"
      data={traces}
      layout={{
        xaxis: { title: { text: "z (m)" } },
        yaxis: { title: { text: "Power (W)" }, type: "log" as any },
        legend: { orientation: "h", y: -0.2 },
      }}
    />
  );
}
