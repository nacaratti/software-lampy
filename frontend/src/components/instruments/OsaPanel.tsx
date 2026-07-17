import { PlotlyChart } from "@/components/plots/PlotlyChart";
import { Badge } from "@/components/ui/badge";
import type { OsaTraceData } from "@/types/system";

interface OsaPanelProps {
  trace: OsaTraceData;
  height?: number;
}

/** Bench-style optical spectrum analyzer trace (dBm vs nm), RBW-broadened. */
export function OsaPanel({ trace, height = 220 }: OsaPanelProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant="outline">RBW {trace.rbw_nm.toFixed(2)} nm</Badge>
        <Badge variant="outline">
          Peak {trace.peak_wavelength_nm.toFixed(2)} nm @ {trace.peak_power_dbm.toFixed(1)} dBm
        </Badge>
        {trace.osnr_db != null && (
          <Badge variant="outline" className="text-emerald-400 border-emerald-500/50">
            OSNR {trace.osnr_db.toFixed(1)} dB
          </Badge>
        )}
      </div>
      <PlotlyChart
        height={height}
        exportFilename="osa_trace"
        data={[
          {
            x: trace.wavelengths_nm,
            y: trace.power_dbm,
            type: "scatter",
            mode: "lines",
            fill: "tozeroy",
            line: { color: "#22D3EE", width: 1.5 },
            fillcolor: "rgba(34, 211, 238, 0.15)",
            hovertemplate: "%{x:.2f} nm<br>%{y:.1f} dBm<extra></extra>",
          },
          {
            x: [trace.peak_wavelength_nm],
            y: [trace.peak_power_dbm],
            type: "scatter",
            mode: "markers",
            marker: { color: "#FBBF24", size: 8, symbol: "diamond" },
            showlegend: false,
            hovertemplate: "peak: %{x:.2f} nm<extra></extra>",
          },
        ]}
        layout={{
          xaxis: { title: { text: "Wavelength (nm)" } },
          yaxis: { title: { text: "Power (dBm)" } },
          margin: { t: 8, r: 8, b: 40, l: 50 },
          showlegend: false,
        }}
      />
    </div>
  );
}
