import { memo } from "react";
import {
  BaseEdge, EdgeLabelRenderer, getBezierPath, useReactFlow, type EdgeProps,
} from "@xyflow/react";
import { X } from "lucide-react";
import { PUMP_EDGE_COLOR } from "./nodeStyles";

/** Optical connection with a wide invisible hit area and a remove button at
 * its midpoint (shown once the edge is selected — click it). Pump lines into a WDM's
 * pump port are drawn rose so the pump path stands out from the signal path.
 * Registered as the `default` edge type, so saved systems pick it up as-is. */
function SignalEdgeImpl({
  id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition,
  targetHandleId, selected, markerEnd,
}: EdgeProps) {
  const { deleteElements } = useReactFlow();
  const [path, labelX, labelY] = getBezierPath({
    sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition,
  });
  const isPump = targetHandleId === "pump";
  const color = isPump ? PUMP_EDGE_COLOR : "hsl(var(--primary))";

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        interactionWidth={22}
        style={{
          stroke: color,
          strokeWidth: selected ? 2.75 : 1.75,
          strokeDasharray: isPump ? "6 4" : undefined,
          opacity: selected ? 1 : 0.85,
        }}
      />
      <EdgeLabelRenderer>
        <button
          type="button"
          aria-label="Remove connection"
          title="Remove connection"
          onClick={(e) => {
            e.stopPropagation();
            void deleteElements({ edges: [{ id }] });
          }}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          className={`nodrag nopan absolute flex h-6 w-6 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-md transition hover:border-destructive hover:bg-destructive hover:text-destructive-foreground ${
            selected ? "pointer-events-auto scale-100 opacity-100" : "pointer-events-none scale-75 opacity-0"
          }`}
        >
          <X className="h-3 w-3" />
        </button>
      </EdgeLabelRenderer>
    </>
  );
}

export const SignalEdge = memo(SignalEdgeImpl);
