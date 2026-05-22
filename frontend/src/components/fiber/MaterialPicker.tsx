import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { NumberField } from "@/components/common/NumberField";
import type { MaterialConfig, MaterialKind } from "@/types/fiber";

interface MaterialPickerProps {
  label: string;
  value: MaterialConfig;
  onChange: (m: MaterialConfig) => void;
}

const KIND_LABELS: Record<MaterialKind, string> = {
  silica: "Silica (SiO₂)",
  germanosilicate: "Germanosilicate (GeO₂–SiO₂)",
  phosphate: "Phosphate glass",
  constant: "Constant index",
};

export function MaterialPicker({ label, value, onChange }: MaterialPickerProps) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Select
        value={value.kind}
        onValueChange={(v) =>
          onChange({
            kind: v as MaterialKind,
            geo2_fraction: v === "germanosilicate" ? value.geo2_fraction ?? 0.035 : null,
            index: v === "constant" ? value.index ?? 1.45 : null,
          })
        }
      >
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(KIND_LABELS).map(([k, lbl]) => (
            <SelectItem key={k} value={k}>
              {lbl}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {value.kind === "germanosilicate" && (
        <NumberField
          label="GeO₂ molar fraction"
          unit="0 – 1"
          step={0.005}
          min={0}
          max={1}
          value={value.geo2_fraction ?? 0.035}
          onChange={(v) => onChange({ ...value, geo2_fraction: v })}
        />
      )}

      {value.kind === "constant" && (
        <NumberField
          label="Refractive index"
          step={0.001}
          min={1.0}
          max={3.0}
          value={value.index ?? 1.45}
          onChange={(v) => onChange({ ...value, index: v })}
        />
      )}
    </div>
  );
}
