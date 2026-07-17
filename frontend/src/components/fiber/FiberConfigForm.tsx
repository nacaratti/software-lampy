import { useState } from "react";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { NumberField } from "@/components/common/NumberField";
import { MaterialPicker } from "./MaterialPicker";
import { cn } from "@/lib/utils";
import type {
  FiberConfig,
  StepIndexConfig,
  GradedIndexConfig,
  DoubleCladConfig,
} from "@/types/fiber";

interface FiberConfigFormProps {
  value: FiberConfig;
  onChange: (f: FiberConfig) => void;
}

const DEFAULT_STEP: StepIndexConfig = {
  kind: "step",
  core_radius_um: 4.0,
  cladding_radius_um: 62.5,
  core_material: { kind: "germanosilicate", geo2_fraction: 0.035, index: null },
  cladding_material: { kind: "silica", geo2_fraction: null, index: null },
};

const DEFAULT_GRADED: GradedIndexConfig = {
  kind: "graded",
  core_radius_um: 25.0,
  cladding_radius_um: 62.5,
  core_material: { kind: "germanosilicate", geo2_fraction: 0.03, index: null },
  cladding_material: { kind: "silica", geo2_fraction: null, index: null },
  alpha: 2.0,
};

const DEFAULT_DOUBLE_CLAD: DoubleCladConfig = {
  kind: "double_clad",
  core_radius_um: 10.0,
  inner_cladding_radius_um: 125.0,
  outer_cladding_radius_um: 250.0,
  core_material: { kind: "germanosilicate", geo2_fraction: 0.02, index: null },
  inner_cladding_material: { kind: "silica", geo2_fraction: null, index: null },
  outer_cladding_material: { kind: "constant", geo2_fraction: null, index: 1.39 },
};

export function FiberConfigForm({ value, onChange }: FiberConfigFormProps) {
  return (
    <Card>
      <CardContent className="pt-5">
        <Tabs
          value={value.kind}
          onValueChange={(k) => {
            if (k === "step") onChange(DEFAULT_STEP);
            else if (k === "graded") onChange(DEFAULT_GRADED);
            else if (k === "double_clad") onChange(DEFAULT_DOUBLE_CLAD);
          }}
        >
          <TabsList className="mb-4 w-full">
            <TabsTrigger value="step" className="flex-1">Step-index</TabsTrigger>
            <TabsTrigger value="graded" className="flex-1">Graded</TabsTrigger>
            <TabsTrigger value="double_clad" className="flex-1">Double-clad</TabsTrigger>
          </TabsList>

          <TabsContent value="step">
            {value.kind === "step" && <StepForm value={value} onChange={onChange} />}
          </TabsContent>
          <TabsContent value="graded">
            {value.kind === "graded" && <GradedForm value={value} onChange={onChange} />}
          </TabsContent>
          <TabsContent value="double_clad">
            {value.kind === "double_clad" && (
              <DoubleCladForm value={value} onChange={onChange} />
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function StepForm({ value, onChange }: { value: StepIndexConfig; onChange: (v: FiberConfig) => void }) {
  const [inputMode, setInputMode] = useState<"material" | "na">("material");

  const getNCladFromMaterial = () =>
    value.cladding_material.kind === "constant" && value.cladding_material.index != null
      ? value.cladding_material.index
      : 1.444;

  const getNAFromMaterials = () => {
    if (
      value.core_material.kind === "constant" && value.core_material.index != null &&
      value.cladding_material.kind === "constant" && value.cladding_material.index != null
    ) {
      const diff = value.core_material.index ** 2 - value.cladding_material.index ** 2;
      return diff > 0 ? Math.sqrt(diff) : 0.12;
    }
    return 0.12;
  };

  const [nClad, setNClad] = useState(getNCladFromMaterial);
  const [na, setNa] = useState(getNAFromMaterials);
  const nCore = Math.sqrt(na ** 2 + nClad ** 2);

  function applyNA(newNA: number, newNClad: number) {
    const newNCore = Math.sqrt(newNA ** 2 + newNClad ** 2);
    onChange({
      ...value,
      core_material: { kind: "constant", index: newNCore },
      cladding_material: { kind: "constant", index: newNClad },
    });
  }

  function switchToNA() {
    const curNClad = getNCladFromMaterial();
    const curNA = getNAFromMaterials();
    setNClad(curNClad);
    setNa(curNA);
    setInputMode("na");
    applyNA(curNA, curNClad);
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <NumberField
          label="Core radius"
          unit="µm"
          step={0.1}
          min={0.1}
          max={500}
          value={value.core_radius_um}
          onChange={(v) => onChange({ ...value, core_radius_um: v })}
        />
        <NumberField
          label="Cladding radius"
          unit="µm"
          step={0.5}
          min={0.5}
          max={2000}
          value={value.cladding_radius_um}
          onChange={(v) => onChange({ ...value, cladding_radius_um: v })}
        />
      </div>

      {/* Input mode toggle */}
      <div className="flex items-center gap-3">
        <span className="text-[11px] text-muted-foreground uppercase tracking-wide font-medium shrink-0">
          Index input
        </span>
        <div className="flex rounded-md border border-border overflow-hidden text-[11px] font-medium">
          <button
            type="button"
            onClick={() => setInputMode("material")}
            className={cn(
              "px-2.5 py-1 transition-colors",
              inputMode === "material"
                ? "bg-primary text-primary-foreground"
                : "hover:bg-secondary text-muted-foreground"
            )}
          >
            Refractive index
          </button>
          <button
            type="button"
            onClick={switchToNA}
            className={cn(
              "px-2.5 py-1 transition-colors border-l border-border",
              inputMode === "na"
                ? "bg-primary text-primary-foreground"
                : "hover:bg-secondary text-muted-foreground"
            )}
          >
            Numerical Aperture
          </button>
        </div>
      </div>

      {inputMode === "material" ? (
        <div className="grid grid-cols-2 gap-4">
          <MaterialPicker
            label="Core"
            value={value.core_material}
            onChange={(m) => onChange({ ...value, core_material: m })}
          />
          <MaterialPicker
            label="Cladding"
            value={value.cladding_material}
            onChange={(m) => onChange({ ...value, cladding_material: m })}
          />
        </div>
      ) : (
        <div className="space-y-3">
          <div className="rounded-lg border border-border/60 bg-secondary/20 px-3 py-2 text-[11px] text-muted-foreground leading-relaxed">
            <span className="font-semibold text-foreground">Numerical Aperture (NA)</span> describes
            how strongly the fiber guides light. Fiber datasheets often specify NA instead of separate
            refractive indices.{" "}
            <span className="font-mono">NA = √(n_core² − n_clad²)</span>.
            Enter NA and the cladding index below — the core index is derived automatically.
          </div>
          <div className="grid grid-cols-2 gap-4">
            <NumberField
              label="Cladding index (n_clad)"
              step={0.0001}
              min={1.0}
              max={3.0}
              value={nClad}
              onChange={(v) => {
                setNClad(v);
                applyNA(na, v);
              }}
              hint="Silica: ~1.444 at 1550 nm"
            />
            <NumberField
              label="Numerical Aperture (NA)"
              step={0.001}
              min={0.001}
              max={0.99}
              value={na}
              onChange={(v) => {
                setNa(v);
                applyNA(v, nClad);
              }}
              hint="SMF-28: 0.14 · LMA: 0.06"
            />
          </div>
          <div className="rounded-md bg-secondary/30 border border-border/40 px-3 py-2 text-[11px] font-mono flex items-center gap-2">
            <span className="text-muted-foreground">n_core =</span>
            <span className="text-foreground font-semibold">{nCore.toFixed(6)}</span>
            <span className="text-muted-foreground ml-auto">
              Δn = {(nCore - nClad).toFixed(5)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function GradedForm({ value, onChange }: { value: GradedIndexConfig; onChange: (v: FiberConfig) => void }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <NumberField
          label="Core radius"
          unit="µm"
          step={0.1}
          value={value.core_radius_um}
          onChange={(v) => onChange({ ...value, core_radius_um: v })}
        />
        <NumberField
          label="Cladding radius"
          unit="µm"
          step={0.5}
          value={value.cladding_radius_um}
          onChange={(v) => onChange({ ...value, cladding_radius_um: v })}
        />
        <NumberField
          label="Alpha"
          unit="profile"
          step={0.1}
          min={0.1}
          max={20}
          value={value.alpha}
          onChange={(v) => onChange({ ...value, alpha: v })}
          hint="2 = parabolic"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <MaterialPicker
          label="Core peak"
          value={value.core_material}
          onChange={(m) => onChange({ ...value, core_material: m })}
        />
        <MaterialPicker
          label="Cladding"
          value={value.cladding_material}
          onChange={(m) => onChange({ ...value, cladding_material: m })}
        />
      </div>
    </div>
  );
}

function DoubleCladForm({
  value,
  onChange,
}: { value: DoubleCladConfig; onChange: (v: FiberConfig) => void }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <NumberField
          label="Core radius"
          unit="µm"
          step={0.1}
          value={value.core_radius_um}
          onChange={(v) => onChange({ ...value, core_radius_um: v })}
        />
        <NumberField
          label="Inner cladding"
          unit="µm"
          step={1}
          value={value.inner_cladding_radius_um}
          onChange={(v) => onChange({ ...value, inner_cladding_radius_um: v })}
        />
        <NumberField
          label="Outer cladding"
          unit="µm"
          step={1}
          value={value.outer_cladding_radius_um}
          onChange={(v) => onChange({ ...value, outer_cladding_radius_um: v })}
        />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <MaterialPicker
          label="Core"
          value={value.core_material}
          onChange={(m) => onChange({ ...value, core_material: m })}
        />
        <MaterialPicker
          label="Inner cladding"
          value={value.inner_cladding_material}
          onChange={(m) => onChange({ ...value, inner_cladding_material: m })}
        />
        <MaterialPicker
          label="Outer cladding"
          value={value.outer_cladding_material}
          onChange={(m) => onChange({ ...value, outer_cladding_material: m })}
        />
      </div>
    </div>
  );
}
