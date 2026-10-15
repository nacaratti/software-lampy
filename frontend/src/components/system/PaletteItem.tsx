import { GripVertical } from "lucide-react";
import { cn } from "@/lib/utils";
import { kindStyle } from "./nodeStyles";

/** One draggable entry in the System Builder palette — the same look for
 * generic blocks, instruments and catalogue devices (neutral card, colored
 * icon chip matching the node it drops). */
export function PaletteItem({
  kind,
  label,
  sublabel,
  onDragStart,
}: {
  kind: string;
  label: string;
  sublabel?: string;
  onDragStart: (e: React.DragEvent) => void;
}) {
  const style = kindStyle(kind);
  const Icon = style.icon;
  return (
    <div
      draggable
      onDragStart={onDragStart}
      title={sublabel ? `${label} — ${sublabel}` : label}
      className="group flex cursor-grab select-none items-center gap-2 rounded-lg border border-border bg-background/60 px-2 py-1.5 transition-colors hover:border-primary/40 hover:bg-accent/40 active:cursor-grabbing"
    >
      <div className={cn("flex h-6 w-6 shrink-0 items-center justify-center rounded-md", style.chip)}>
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-xs font-medium leading-tight">{label}</div>
        {sublabel && <div className="truncate text-[10px] text-muted-foreground">{sublabel}</div>}
      </div>
      <GripVertical className="h-3.5 w-3.5 shrink-0 text-muted-foreground/40 opacity-0 transition-opacity group-hover:opacity-100" />
    </div>
  );
}
