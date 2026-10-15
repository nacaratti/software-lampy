import { PlotlyChart } from "./PlotlyChart";
import { decodeArray, reshape2D } from "@/lib/encoding";
import type { PowerASEResponse } from "@/types/power";

interface ASESpectrumPlotProps {
  response: PowerASEResponse;
  height?: number;
}

/** Total ASE output power per wavelength channel (forward at z=L + backward at z=0). */
export function ASESpectrumPlot({ response, height = 280 }: ASESpectrumPlotProps) {
  const wls = response.ase_wavelengths_nm;
  if (wls.length === 0) {
    return (
      <div className="text-xs text-muted-foreground text-center py-6">
        ASE was disabled for this run.
      </div>
    );
  }

  const aFDec = decodeArray(response.ase_forward);
  const aBDec = decodeArray(response.ase_backward);
  const [rowsF, colsF] = aFDec.shape;
  const [, colsB] = aBDec.shape;
  const aF = reshape2D(aFDec.data, rowsF, colsF);
  const aB = reshape2D(aBDec.data, rowsF, colsB);

  const outF = aF.map((row) => row[row.length - 1]); // forward output at z=L
  const outB = aB.map((row) => row[0]);              // backward output at z=0

  return (
    <PlotlyChart
      height={height}
      exportFilename="ase_spectrum"
      data={[
        {
          x: wls, y: outF, name: "ASE forward (z=L)",
          type: "bar",
          marker: { color: "rgba(167, 139, 250, 0.75)" },
        },
        {
          x: wls, y: outB, name: "ASE backward (z=0)",
          type: "bar",
          marker: { color: "rgba(34, 211, 238, 0.75)" },
        },
      ]}
      layout={{
        barmode: "group",
        xaxis: { title: { text: "Wavelength (nm)" } },
        yaxis: { title: { text: "Output power (W)" } },
        // Legend above the plot: below it, it collided with the x-axis title at this height.
        legend: { orientation: "h", x: 0, y: 1.02, yanchor: "bottom" },
        margin: { t: 40, r: 16, b: 48, l: 60 },
      }}
    />
  );
}
