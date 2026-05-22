import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PlotlyChart } from "@/components/plots/PlotlyChart";
import type { FiberConfig, IndexProfilePreviewResponse } from "@/types/fiber";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatNumber } from "@/lib/utils";

interface IndexProfilePreviewProps {
  fiber: FiberConfig;
  wavelength_nm: number;
}

export function IndexProfilePreview({ fiber, wavelength_nm }: IndexProfilePreviewProps) {
  const [data, setData] = useState<IndexProfilePreviewResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const t = setTimeout(() => {
      api
        .previewIndex({ fiber, wavelength_nm, num_points: 400 })
        .then((r) => {
          if (!cancelled) {
            setData(r);
            setErr(null);
          }
        })
        .catch((e) => {
          if (!cancelled) setErr(String(e));
        });
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [fiber, wavelength_nm]);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm">Refractive index profile</CardTitle>
            <CardDescription className="text-xs">
              Live preview of n(r) at {wavelength_nm.toFixed(1)} nm
            </CardDescription>
          </div>
          {data && (
            <div className="flex gap-1.5">
              <Badge variant="accent">n_core: {formatNumber(data.n_core, 4)}</Badge>
              <Badge variant="secondary">n_clad: {formatNumber(data.n_cladding, 4)}</Badge>
              {data.v_number !== null && (
                <Badge variant={data.v_number < 2.405 ? "success" : "warning"}>
                  V: {formatNumber(data.v_number, 3)}
                </Badge>
              )}
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {err && <div className="text-xs text-destructive py-3">{err}</div>}
        {data && (
          <PlotlyChart
            height={220}
            data={[
              {
                x: data.r_um,
                y: data.n,
                type: "scatter",
                mode: "lines",
                line: { color: "#A78BFA", width: 2.5, shape: "hv" as any },
                fill: "tozeroy",
                fillcolor: "rgba(167, 139, 250, 0.15)",
                hovertemplate: "r=%{x:.2f} µm<br>n=%{y:.5f}<extra></extra>",
              },
            ]}
            layout={{
              xaxis: { title: { text: "r (µm)" } },
              yaxis: { title: { text: "n" }, range: [Math.min(...data.n) - 0.002, Math.max(...data.n) + 0.002] },
              showlegend: false,
              margin: { t: 8, r: 8, b: 44, l: 56 },
            }}
          />
        )}
      </CardContent>
    </Card>
  );
}
