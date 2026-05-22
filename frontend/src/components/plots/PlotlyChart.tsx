import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";
import { useThemeStore } from "@/stores/useThemeStore";

interface PlotlyChartProps {
  data: Plotly.Data[];
  layout?: Partial<Plotly.Layout>;
  config?: Partial<Plotly.Config>;
  height?: number | string;
  className?: string;
}

function getThemeLayout(isDark: boolean): Partial<Plotly.Layout> {
  const fg = isDark ? "#E6E6F0" : "#1A1A2E";
  const muted = isDark ? "#7A7A9A" : "#5A5A75";
  const grid = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.08)";
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Inter, system-ui, sans-serif", color: fg, size: 12 },
    margin: { t: 32, r: 16, b: 48, l: 60 },
    xaxis: {
      gridcolor: grid,
      linecolor: grid,
      zerolinecolor: grid,
      tickfont: { color: muted },
      title: { font: { color: muted, size: 11 } },
    },
    yaxis: {
      gridcolor: grid,
      linecolor: grid,
      zerolinecolor: grid,
      tickfont: { color: muted },
      title: { font: { color: muted, size: 11 } },
    },
    legend: {
      bgcolor: "rgba(0,0,0,0)",
      bordercolor: grid,
      borderwidth: 1,
      font: { color: fg, size: 11 },
    },
    colorway: [
      "#A78BFA",
      "#22D3EE",
      "#F472B6",
      "#FBBF24",
      "#34D399",
      "#F87171",
      "#60A5FA",
      "#FB923C",
    ],
  };
}

export function PlotlyChart({
  data,
  layout = {},
  config = {},
  height = 360,
  className,
}: PlotlyChartProps) {
  const ref = useRef<HTMLDivElement>(null);
  const isDark = useThemeStore((s) => s.theme === "dark");

  useEffect(() => {
    if (!ref.current) return;
    const merged: Partial<Plotly.Layout> = {
      ...getThemeLayout(isDark),
      ...layout,
      // Preserve x/y axis settings if user provided
      xaxis: { ...getThemeLayout(isDark).xaxis, ...(layout.xaxis ?? {}) },
      yaxis: { ...getThemeLayout(isDark).yaxis, ...(layout.yaxis ?? {}) },
    };
    Plotly.react(ref.current, data, merged, {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
      ...config,
    });
  }, [data, layout, config, isDark]);

  useEffect(() => {
    const handle = () => {
      if (ref.current) Plotly.Plots.resize(ref.current);
    };
    window.addEventListener("resize", handle);
    return () => {
      window.removeEventListener("resize", handle);
      if (ref.current) Plotly.purge(ref.current);
    };
  }, []);

  return <div ref={ref} className={className} style={{ height, width: "100%" }} />;
}
