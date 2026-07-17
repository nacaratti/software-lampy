export type JobStatus = "queued" | "running" | "completed" | "cancelled" | "error" | "expired";
export type JobKind = "ase" | "bpm" | "system" | "fbg" | "splicing" | "thermal" | "coupler" | "taper" | "gnlse" | "power_ramp";

export interface JobInfo {
  job_id: string;
  kind: JobKind;
  status: JobStatus;
  progress: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  request: Record<string, unknown> | null;
}

export interface JobCreatedResponse {
  job_id: string;
  status: JobStatus;
}

export type WsMessage =
  | { type: "status"; status: JobStatus }
  | { type: "progress"; value: number }
  | { type: "result"; data: unknown }
  | { type: "error"; message: string }
  | { type: "cancelled" }
  | { type: "expired" };
