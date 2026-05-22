import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { NumberField } from "@/components/common/NumberField";
import { MaterialPicker } from "./MaterialPicker";
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
