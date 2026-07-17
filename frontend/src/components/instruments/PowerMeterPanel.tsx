import type { PowerMeterReadingData } from "@/types/system";

interface PowerMeterPanelProps {
  reading: PowerMeterReadingData;
}

const BAND_COLORS: Record<string, string> = {
  signal: "#34d399",
  pump: "#f87171",
  ase: "#a78bfa",
};

export function formatWatts(w: number): string {
  if (!Number.isFinite(w)) return "—";
  if (w >= 1) return `${w.toFixed(3)} W`;
  if (w >= 1e-3) return `${(w * 1e3).toFixed(2)} mW`;
  if (w >= 1e-6) return `${(w * 1e6).toFixed(2)} µW`;
  return `${(w * 1e9).toFixed(2)} nW`;
}

/** Digital-readout style thermal power meter with a per-band breakdown. */
export function PowerMeterPanel({ reading }: PowerMeterPanelProps) {
  const bands = Object.entries(reading.band_power_w);
  const max = Math.max(...bands.map(([, v]) => v), reading.total_power_w, 1e-12);

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-border bg-background/60 px-4 py-3">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Total power</p>
        <p className="text-3xl font-mono font-semibold text-primary">{formatWatts(reading.total_power_w)}</p>
        <p className="text-[11px] text-muted-foreground font-mono">
          {reading.total_power_dbm.toFixed(1)} dBm
        </p>
      </div>
      {bands.length > 0 && (
        <div className="space-y-1.5">
          {bands.map(([label, w]) => (
            <div key={label} className="space-y-0.5">
              <div className="flex justify-between text-[11px]">
                <span className="capitalize text-muted-foreground">{label}</span>
                <span className="font-mono">{formatWatts(w)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.max((w / max) * 100, 1)}%`,
                    backgroundColor: BAND_COLORS[label] ?? "#6b7280",
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
