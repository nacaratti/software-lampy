import type Plotly from "plotly.js-dist-min";

function escapeCsvCell(v: unknown): string {
  const s = v === null || v === undefined ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function downloadCsv(filename: string, rows: unknown[][]): void {
  const csv = rows.map((row) => row.map(escapeCsvCell).join(",")).join("\r\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** Flattens Plotly x/y scatter- and bar-like traces into a CSV-ready table.
 * Heatmap/2D traces (no matching flat x/y pair) are skipped — export their
 * source arrays separately if needed. */
export function plotlyDataToRows(data: Plotly.Data[]): unknown[][] {
  const traces = data.filter((t) => {
    const x = (t as { x?: unknown }).x;
    const y = (t as { y?: unknown }).y;
    return Array.isArray(x) && Array.isArray(y) && (t as { type?: string }).type !== "heatmap";
  }) as Array<{ x: unknown[]; y: unknown[]; name?: string }>;

  if (traces.length === 0) return [];

  const header: string[] = [];
  traces.forEach((t, i) => {
    const name = t.name || `trace${i}`;
    header.push(`${name}_x`, `${name}_y`);
  });

  const maxLen = Math.max(...traces.map((t) => t.x.length));
  const rows: unknown[][] = [header];
  for (let r = 0; r < maxLen; r++) {
    const row: unknown[] = [];
    for (const t of traces) {
      row.push(t.x[r] ?? "", t.y[r] ?? "");
    }
    rows.push(row);
  }
  return rows;
}

export function exportPlotlyDataAsCsv(filename: string, data: Plotly.Data[]): boolean {
  const rows = plotlyDataToRows(data);
  if (rows.length === 0) return false;
  downloadCsv(filename, rows);
  return true;
}
