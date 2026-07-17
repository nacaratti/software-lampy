import { useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { toast } from "sonner";
import { Play, Loader2, Save, FolderOpen, Library } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { NumberField } from "@/components/common/NumberField";
import { PageHeader } from "@/components/layout/PageHeader";
import { FiberConfigForm } from "@/components/fiber/FiberConfigForm";
import { FiberCatalogDialog } from "@/components/fiber/FiberCatalogDialog";
import { IndexProfilePreview } from "@/components/fiber/IndexProfilePreview";
import { ModeListPanel } from "@/components/plots/ModeListPanel";
import { api } from "@/lib/api";
import type { ModesResponse } from "@/types/modes";
import { useFiberStore } from "@/stores/useFiberStore";
import { savePreset } from "@/lib/presets";
import { PresetsDialog } from "@/components/common/PresetsDialog";
import type { FiberConfig } from "@/types/fiber";

type Method = "analytical" | "fd" | "2d";

interface ModeSolverPreset {
  fiber: FiberConfig;
  wavelength_nm: number;
  method: Method;
  l: number;
}

export function ModeSolverPage() {
  const { fiber, setFiber, wavelength_nm, setWavelength } = useFiberStore();
  const [method, setMethod] = useState<Method>("analytical");
  const [l, setL] = useState(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ModesResponse | null>(null);
  const [showPresets, setShowPresets] = useState(false);
  const [showCatalog, setShowCatalog] = useState(false);

  async function runSolve() {
    setLoading(true);
    setResult(null);
    try {
      let effectiveMethod = method;
      if (method === "analytical" && fiber.kind !== "step") {
        effectiveMethod = "fd";
        toast.info(
          "Analytical solver is step-index only. Using radial FD for this fiber geometry."
        );
      }

      let res: ModesResponse;
      if (effectiveMethod === "analytical") {
        res = await api.modesAnalytical({
          fiber,
          wavelength_nm,
          grid_size: 128,
          max_plot_radius_factor: 2.0,
        });
      } else if (effectiveMethod === "fd") {
        res = await api.modesFD({
          fiber,
          wavelength_nm,
          l,
          grid_points: 400,
          plot_grid_size: 128,
          max_plot_radius_factor: 2.0,
        });
      } else {
        res = await api.modes2D({
          fiber,
          wavelength_nm,
          grid_size: 80,
          grid_width_factor: 3.0,
          num_modes: 6,
        });
      }
      setResult(res);
      toast.success(`Found ${res.num_modes} guided mode${res.num_modes === 1 ? "" : "s"}`);
    } catch (e) {
      toast.error(String(e));
    } finally {
      setLoading(false);
    }
  }

  useHotkeys("mod+enter", (e) => {
    e.preventDefault();
    if (!loading) runSolve();
  }, [loading, fiber, wavelength_nm, method, l]);

  function handleSavePreset() {
    const name = prompt("Preset name?", `Modes ${new Date().toLocaleTimeString()}`);
    if (!name) return;
    savePreset<ModeSolverPreset>("mode-solver", name, { fiber, wavelength_nm, method, l });
    toast.success("Preset saved");
  }

  function handleLoadPreset(config: ModeSolverPreset) {
    setFiber(config.fiber);
    setWavelength(config.wavelength_nm);
    setMethod(config.method);
    setL(config.l);
  }

  return (
    <div className="container mx-auto py-8 max-w-6xl">
      <PageHeader
        eyebrow="Solver"
        title="Fiber Modes Solver"
        description="Compute guided LP modes and visualize field intensities. Three methods: analytical (step-index), radial finite differences, and full 2D."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => setShowCatalog(true)}>
              <Library className="h-3.5 w-3.5" />
              Load from catalog
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShowPresets(true)}>
              <FolderOpen className="h-3.5 w-3.5" />
              Load preset
            </Button>
            <Button variant="outline" size="sm" onClick={handleSavePreset}>
              <Save className="h-3.5 w-3.5" />
              Save preset
            </Button>
            <Button variant="glow" size="sm" onClick={runSolve} disabled={loading}>
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              {loading ? "Solving..." : "Solve modes"}
              <kbd className="ml-1.5 rounded bg-black/20 px-1.5 py-0.5 text-[10px] font-mono">⌘↵</kbd>
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <FiberConfigForm value={fiber} onChange={setFiber} />

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Solver settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <NumberField
              label="Wavelength"
              unit="nm"
              step={1}
              min={200}
              max={20000}
              value={wavelength_nm}
              onChange={setWavelength}
            />

            <div className="space-y-1.5">
              <Label>Method</Label>
              <Select value={method} onValueChange={(v) => setMethod(v as Method)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="analytical">Analytical (step-index only)</SelectItem>
                  <SelectItem value="fd">Radial FD (arbitrary radial profile)</SelectItem>
                  <SelectItem value="2d">Full 2D (any geometry)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {method === "fd" && (
              <NumberField
                label="Azimuthal order ℓ"
                value={l}
                step={1}
                min={0}
                max={10}
                onChange={setL}
                hint="0 = LP0m, 1 = LP1m, ..."
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-4">
        <IndexProfilePreview fiber={fiber} wavelength_nm={wavelength_nm} />
      </div>

      {result && (
        <div className="mt-6 animate-fade-in">
          <ModeListPanel response={result} />
        </div>
      )}

      {!result && !loading && (
        <div className="mt-8 rounded-xl border border-dashed border-border bg-card/40 p-10 text-center text-sm text-muted-foreground">
          Configure your fiber and press <kbd className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[11px]">⌘ Enter</kbd> to compute modes.
        </div>
      )}

      <PresetsDialog<ModeSolverPreset>
        kind="mode-solver"
        open={showPresets}
        onClose={() => setShowPresets(false)}
        onLoad={handleLoadPreset}
      />

      <FiberCatalogDialog
        open={showCatalog}
        onClose={() => setShowCatalog(false)}
        onLoad={(loadedFiber) => setFiber(loadedFiber)}
      />
    </div>
  );
}
