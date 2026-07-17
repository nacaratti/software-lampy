import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { listPresets, deletePreset, type Preset } from "@/lib/presets";

interface PresetsDialogProps<T> {
  kind: string;
  open: boolean;
  onClose: () => void;
  onLoad: (config: T) => void;
}

/** Browse/load/delete presets saved for a given solver `kind` (see lib/presets.ts). */
export function PresetsDialog<T>({ kind, open, onClose, onLoad }: PresetsDialogProps<T>) {
  const [presets, setPresets] = useState<Preset<T>[]>([]);

  useEffect(() => {
    if (open) setPresets(listPresets<T>(kind));
  }, [open, kind]);

  function handleDelete(id: string, name: string) {
    if (!window.confirm(`Delete preset "${name}"?`)) return;
    deletePreset(id);
    setPresets((prev) => prev.filter((p) => p.id !== id));
  }

  function handleLoad(preset: Preset<T>) {
    onLoad(preset.config);
    onClose();
    toast.success(`Loaded "${preset.name}"`);
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Saved presets</DialogTitle>
          <DialogDescription>Load a previously saved configuration for this solver.</DialogDescription>
        </DialogHeader>
        {presets.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4">No presets saved yet.</p>
        ) : (
          <div className="space-y-1.5 max-h-80 overflow-y-auto">
            {presets.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2 hover:bg-accent/30 transition-colors"
              >
                <button className="min-w-0 flex-1 text-left" onClick={() => handleLoad(p)}>
                  <p className="text-sm font-medium truncate">{p.name}</p>
                  <p className="text-[11px] text-muted-foreground">{new Date(p.createdAt).toLocaleString()}</p>
                </button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive shrink-0"
                  aria-label={`Delete preset ${p.name}`}
                  onClick={() => handleDelete(p.id, p.name)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
