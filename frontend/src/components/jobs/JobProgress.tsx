import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { X, Loader2, CheckCircle2, AlertCircle, Circle } from "lucide-react";
import { api } from "@/lib/api";
import type { JobStatus } from "@/types/jobs";

interface JobProgressProps {
  jobId: string;
  status: JobStatus;
  progress: number;
  error?: string | null;
}

export function JobProgress({ jobId, status, progress, error }: JobProgressProps) {
  const canCancel = status === "running" || status === "queued";
  const pct = Math.round(progress * 100);

  return (
    <Card>
      <CardContent className="pt-5 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <StatusIcon status={status} />
            <span className="text-sm font-medium capitalize">{status}</span>
            <Badge variant="outline" className="font-mono text-[10px]">
              {jobId.slice(0, 8)}
            </Badge>
          </div>
          {canCancel && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => api.cancelJob(jobId)}
              className="text-destructive hover:text-destructive"
            >
              <X className="h-3.5 w-3.5" />
              Cancel
            </Button>
          )}
        </div>

        {(status === "running" || status === "queued") && (
          <div className="space-y-1">
            <Progress value={progress} />
            <div className="text-xs text-muted-foreground font-mono text-right">{pct}%</div>
          </div>
        )}

        {error && (
          <div className="text-xs text-destructive bg-destructive/10 rounded p-3 font-mono">
            {error}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function StatusIcon({ status }: { status: JobStatus }) {
  switch (status) {
    case "running":
      return <Loader2 className="h-4 w-4 text-primary animate-spin" />;
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
    case "error":
      return <AlertCircle className="h-4 w-4 text-destructive" />;
    case "cancelled":
      return <X className="h-4 w-4 text-amber-400" />;
    default:
      return <Circle className="h-4 w-4 text-muted-foreground" />;
  }
}
