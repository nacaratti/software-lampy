import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface NumberFieldProps {
  label: string;
  value: number;
  onChange: (v: number) => void;
  unit?: string;
  hint?: string;
  step?: number;
  min?: number;
  max?: number;
  disabled?: boolean;
  placeholder?: string;
}

export function NumberField({
  label,
  value,
  onChange,
  unit,
  hint,
  step,
  min,
  max,
  disabled,
  placeholder,
}: NumberFieldProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <Label>{label}</Label>
        {unit && (
          <span className="text-[10px] font-mono text-muted-foreground">{unit}</span>
        )}
      </div>
      <Input
        type="number"
        value={Number.isFinite(value) ? value : ""}
        step={step}
        min={min}
        max={max}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => {
          const v = e.target.value;
          if (v === "" || v === "-") return;
          const n = Number(v);
          if (Number.isFinite(n)) onChange(n);
        }}
      />
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}
