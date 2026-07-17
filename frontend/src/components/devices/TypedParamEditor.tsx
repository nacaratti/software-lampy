import { forwardRef, useImperativeHandle, useRef } from "react";
import { ParamForm, type ParamFormHandle } from "@/components/devices/ParamForm";
import { fieldSpecsFor } from "@/lib/paramFieldSpecs";

interface JsonFallbackEditorProps {
  value: Record<string, unknown>;
  onChange: (v: Record<string, unknown>) => void;
}

/** Raw JSON textarea — only shown for a `kind` with no typed field spec yet. */
function JsonFallbackEditor({ value, onChange }: JsonFallbackEditorProps) {
  const text = JSON.stringify(value, null, 2);
  return (
    <div className="flex flex-col gap-1">
      <textarea
        className="w-full h-52 rounded-md border border-border bg-background font-mono text-xs p-2 resize-y focus:outline-none focus:ring-1 focus:ring-ring"
        defaultValue={text}
        onChange={(e) => {
          try {
            onChange(JSON.parse(e.target.value));
          } catch {
            /* ignore until valid JSON */
          }
        }}
        spellCheck={false}
      />
    </div>
  );
}

interface TypedParamEditorProps {
  /** Device Library `device_type` or System Builder node `kind`. */
  kind: string;
  values: Record<string, unknown>;
  onJsonChange: (v: Record<string, unknown>) => void;
}

/** Typed field form when a spec exists for `kind` (covers every Device
 * Library type and System Builder node kind today); falls back to a raw
 * JSON editor otherwise so new kinds never lose the ability to be edited. */
export const TypedParamEditor = forwardRef<ParamFormHandle, TypedParamEditorProps>(
  function TypedParamEditor({ kind, values, onJsonChange }, ref) {
    const specs = fieldSpecsFor(kind);
    const typedRef = useRef<ParamFormHandle>(null);

    useImperativeHandle(
      ref,
      () => ({
        getValues: async () => (specs ? (typedRef.current?.getValues() ?? null) : values),
      }),
      [specs, values],
    );

    if (specs) {
      return <ParamForm key={kind} ref={typedRef} specs={specs} values={values} />;
    }
    return <JsonFallbackEditor value={values} onChange={onJsonChange} />;
  },
);
