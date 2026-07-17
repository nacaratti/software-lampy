import { forwardRef, useImperativeHandle } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { type FieldSpec, schemaFromSpecs } from "@/lib/paramFieldSpecs";

export interface ParamFormHandle {
  /** Validates the form and returns the typed values, or null (and shows
   * inline errors) if something is out of range. */
  getValues: () => Promise<Record<string, unknown> | null>;
}

interface ParamFormProps {
  specs: FieldSpec[];
  /** Current parameter values (from the device/node); missing keys fall back
   * to the spec's default so the form is always fully controlled. */
  values: Record<string, unknown>;
}

export const ParamForm = forwardRef<ParamFormHandle, ParamFormProps>(function ParamForm(
  { specs, values },
  ref,
) {
  const schema = schemaFromSpecs(specs);
  const defaultValues: Record<string, unknown> = {};
  for (const s of specs) {
    defaultValues[s.key] = values[s.key] ?? s.default;
  }
  // Extra keys already on the device/node that aren't modeled by a field spec
  // (legacy data, catalog-only metadata) are preserved untouched.
  for (const [k, v] of Object.entries(values)) {
    if (!(k in defaultValues)) defaultValues[k] = v;
  }

  const {
    register,
    control,
    trigger,
    getValues: rhfGetValues,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues,
    mode: "onBlur",
  });

  useImperativeHandle(ref, () => ({
    getValues: async () => {
      const valid = await trigger();
      if (!valid) return null;
      return schema.parse(rhfGetValues());
    },
  }));

  if (specs.length === 0) {
    return <p className="text-xs text-muted-foreground">This block has no configurable parameters.</p>;
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      {specs.map((s) => {
        const error = errors[s.key];
        return (
          <div key={s.key} className={s.type === "text" ? "col-span-2" : ""}>
            <Label className="text-xs flex items-center justify-between gap-2">
              <span className="truncate">{s.label}</span>
              {s.type === "number" && s.unit && (
                <span className="text-[10px] text-muted-foreground font-normal shrink-0">{s.unit}</span>
              )}
            </Label>
            {s.type === "select" ? (
              <Controller
                control={control}
                name={s.key}
                render={({ field }) => (
                  <Select value={String(field.value)} onValueChange={field.onChange}>
                    <SelectTrigger className="mt-1 h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {s.options.map((o) => (
                        <SelectItem key={o.value} value={o.value} className="text-xs">
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            ) : (
              <Input
                type={s.type === "number" ? "number" : "text"}
                step={s.type === "number" ? s.step ?? "any" : undefined}
                min={s.type === "number" ? s.min : undefined}
                max={s.type === "number" ? s.max : undefined}
                {...register(s.key, s.type === "number" ? { valueAsNumber: true } : {})}
                className="mt-1 h-8 text-xs font-mono"
              />
            )}
            {error && <p className="text-[10px] text-destructive mt-0.5">{String(error.message)}</p>}
          </div>
        );
      })}
    </div>
  );
});
