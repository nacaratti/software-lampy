import type { ModeResult, ModesResponse } from "@/types/modes";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ModeFieldHeatmap } from "./ModeFieldHeatmap";
import { cn, formatNumber } from "@/lib/utils";
import { useState } from "react";

interface ModeListPanelProps {
  response: ModesResponse;
}

export function ModeListPanel({ response }: ModeListPanelProps) {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const selected = response.modes[selectedIdx];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
      <Card className="overflow-hidden">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">
            {response.num_modes} mode{response.num_modes === 1 ? "" : "s"} found
          </CardTitle>
          <CardDescription className="text-[11px] space-y-1">
            <div>
              {response.method.toUpperCase()} · λ = {response.wavelength_nm.toFixed(1)} nm
            </div>
            {response.v_number !== null && response.v_number !== undefined && (
              <div>
                V-number: <span className="font-mono font-medium text-foreground">{formatNumber(response.v_number, 3)}</span>
              </div>
            )}
          </CardDescription>
        </CardHeader>
        <ScrollArea className="h-[420px]">
          <CardContent className="space-y-1.5 pt-0 pb-3">
            {response.modes.map((m, i) => (
              <ModeRow
                key={i}
                mode={m}
                active={i === selectedIdx}
                onClick={() => setSelectedIdx(i)}
              />
            ))}
          </CardContent>
        </ScrollArea>
      </Card>
 
      <Card>
        <CardHeader className="pb-2">
          {selected && (
            <>
              <CardTitle className="text-sm flex items-center gap-2">
                <Badge variant="accent">LP{selected.l}{selected.m}</Badge>
                Mode field intensity
              </CardTitle>
              <CardDescription className="text-[11px] grid grid-cols-2 md:grid-cols-4 gap-4 mt-2 bg-secondary/30 p-2.5 rounded-lg border border-border/50">
                <div>
                  <div className="text-muted-foreground font-semibold text-[10px] uppercase">n_eff</div>
                  <div className="font-mono text-xs text-foreground font-medium mt-0.5">{formatNumber(selected.n_eff, 6)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground font-semibold text-[10px] uppercase">beta</div>
                  <div className="font-mono text-xs text-foreground font-medium mt-0.5">{formatNumber(selected.beta, 1)} rad/m</div>
                </div>
                {selected.a_eff_um2 !== undefined && selected.a_eff_um2 !== null && (
                  <div>
                    <div className="text-muted-foreground font-semibold text-[10px] uppercase">A_eff</div>
                    <div className="font-mono text-xs text-foreground font-medium mt-0.5">{formatNumber(selected.a_eff_um2, 1)} µm²</div>
                  </div>
                )}
                {selected.power_core_pct !== undefined && selected.power_core_pct !== null && (
                  <div>
                    <div className="text-muted-foreground font-semibold text-[10px] uppercase">Power in core</div>
                    <div className="font-mono text-xs text-foreground font-medium mt-0.5">{formatNumber(selected.power_core_pct, 1)}%</div>
                  </div>
                )}
              </CardDescription>
            </>
          )}
        </CardHeader>
        <CardContent>
          {selected && <ModeFieldHeatmap mode={selected} height={420} />}
        </CardContent>
      </Card>
    </div>
  );
}

function ModeRow({
  mode,
  active,
  onClick,
}: {
  mode: ModeResult;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full text-left rounded-md px-3 py-2 transition-colors",
        active
          ? "bg-primary/15 border border-primary/40"
          : "border border-transparent hover:bg-secondary"
      )}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm">
          LP<span className="text-accent">{mode.l}</span>
          <span className="text-primary">{mode.m}</span>
        </span>
        <span className="text-[10px] text-muted-foreground font-mono">
          n_eff {formatNumber(mode.n_eff, 5)}
        </span>
      </div>
    </button>
  );
}
