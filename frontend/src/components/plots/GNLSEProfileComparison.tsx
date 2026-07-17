import { PlotlyChart } from "./PlotlyChart";

interface GNLSEProfileComparisonProps {
  xAxis: number[];
  xLabel: string;
  yLabel: string;
  inputValues: number[];
  outputValues: number[];
  exportFilename?: string;
  height?: number;
}

/** Input (z=0) vs. output (z=L) profile overlay — reused for both the
 * temporal power and spectral power views of a GNLSE pulse run. */
export function GNLSEProfileComparison({
  xAxis, xLabel, yLabel, inputValues, outputValues, exportFilename, height = 260,
}: GNLSEProfileComparisonProps) {
  return (
    <PlotlyChart
      height={height}
      exportFilename={exportFilename}
      data={[
        {
          x: xAxis, y: inputValues, type: "scatter", mode: "lines", name: "Input (z=0)",
          line: { color: "#38bdf8", width: 2, dash: "dot" },
        },
        {
          x: xAxis, y: outputValues, type: "scatter", mode: "lines", name: "Output (z=L)",
          line: { color: "#FBBF24", width: 2.5 },
        },
      ]}
      layout={{
        xaxis: { title: { text: xLabel } },
        yaxis: { title: { text: yLabel } },
        legend: { orientation: "h", y: -0.25 },
        margin: { t: 8, r: 8, b: 44, l: 56 },
      }}
    />
  );
}
