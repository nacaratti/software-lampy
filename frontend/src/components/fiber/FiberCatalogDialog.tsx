import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api } from "@/lib/api";
import type { Device } from "@/types/device";
import type { FiberConfig, MaterialConfig } from "@/types/fiber";

interface FiberCatalogDialogProps {
  open: boolean;
  onClose: () => void;
  onLoad: (fiber: FiberConfig, wavelength_nm?: number) => void;
}

/** Converts a Device Library `fiber_active`/`fiber_passive` catalog entry
 * into a `FiberConfig` the Mode Solver can analyze directly. Fibers with
 * an inner cladding radius (cladding-pumped double-clad designs) map to
 * the double-clad geometry; everything else maps to step-index. */
function deviceToFiberConfig(device: Device): FiberConfig | null {
  const p = device.parameters;
  const coreR = Number(p.core_radius_um);
  const cladR = Number(p.clad_radius_um);
  const nCore = Number(p.n_core);
  const nClad = Number(p.n_clad);
  if (!Number.isFinite(coreR) || !Number.isFinite(cladR) || !Number.isFinite(nCore) || !Number.isFinite(nClad)) {
    return null;
  }
  const coreMat: MaterialConfig = { kind: "constant", index: nCore };
  const cladMat: MaterialConfig = { kind: "constant", index: nClad };

  const innerCladR = p.inner_cladding_radius_um;
  if (innerCladR !== undefined && innerCladR !== null && Number.isFinite(Number(innerCladR))) {
    return {
      kind: "double_clad",
      core_radius_um: coreR,
      inner_cladding_radius_um: Number(innerCladR),
      outer_cladding_radius_um: cladR,
      core_material: coreMat,
      inner_cladding_material: cladMat,
      outer_cladding_material: { kind: "constant", index: 1.375 },
    };
  }
  return {
    kind: "step",
    core_radius_um: coreR,
    cladding_radius_um: cladR,
    core_material: coreMat,
    cladding_material: cladMat,
  };
}

export function FiberCatalogDialog({ open, onClose, onLoad }: FiberCatalogDialogProps) {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    Promise.all([
      api.listDevices({ device_type: "fiber_active" }),
      api.listDevices({ device_type: "fiber_passive" }),
    ])
      .then(([active, passive]) => setDevices([...active, ...passive]))
      .catch((e) => toast.error(String(e)))
      .finally(() => setLoading(false));
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return devices;
    return devices.filter(
      (d) =>
        d.name.toLowerCase().includes(q) ||
        d.manufacturer.toLowerCase().includes(q) ||
        d.part_number.toLowerCase().includes(q),
    );
  }, [devices, query]);

  function handleSelect(device: Device) {
    const fiber = deviceToFiberConfig(device);
    if (!fiber) {
      toast.error(`"${device.name}" is missing core/cladding index data — can't load into the Mode Solver.`);
      return;
    }
    onLoad(fiber);
    toast.success(`Loaded ${device.name}`);
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Load fiber from catalog</DialogTitle>
          <DialogDescription>
            Pick a fiber from the Device Library to analyze its guided modes.
          </DialogDescription>
        </DialogHeader>
        <Input
          placeholder="Search by name, manufacturer, part number..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-8 text-xs"
        />
        <ScrollArea className="h-80">
          {loading ? (
            <p className="text-xs text-muted-foreground py-4 text-center">Loading catalog...</p>
          ) : filtered.length === 0 ? (
            <p className="text-xs text-muted-foreground py-4 text-center">No fibers match.</p>
          ) : (
            <div className="space-y-1.5 pr-2">
              {filtered.map((d) => (
                <button
                  key={d.id}
                  onClick={() => handleSelect(d)}
                  className="w-full text-left rounded-md border border-border bg-background/50 hover:bg-accent px-3 py-2 transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium">{d.name}</span>
                    <div className="flex gap-1 shrink-0">
                      <Badge variant="outline" className="text-[10px]">{d.manufacturer}</Badge>
                      <Badge variant={d.device_type === "fiber_active" ? "secondary" : "outline"} className="text-[10px]">
                        {d.device_type === "fiber_active" ? "active" : "passive"}
                      </Badge>
                    </div>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    core {Number(d.parameters.core_radius_um)}µm / clad {Number(d.parameters.clad_radius_um)}µm
                    {d.parameters.NA !== undefined ? ` · NA ${d.parameters.NA}` : ""}
                  </p>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
