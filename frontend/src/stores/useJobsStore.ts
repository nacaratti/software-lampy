import { create } from "zustand";
import type { JobKind, JobStatus } from "@/types/jobs";

export interface JobEntry {
  jobId: string;
  kind: JobKind;
  label: string;
  startedAt: string;
  status: JobStatus;
  progress: number;
  config: unknown;
  result: unknown | null;
  error: string | null;
}

interface JobsState {
  history: JobEntry[];
  activeJobId: string | null;
  pushJob: (j: Omit<JobEntry, "startedAt" | "status" | "progress" | "result" | "error">) => void;
  updateJob: (jobId: string, patch: Partial<JobEntry>) => void;
  setActive: (jobId: string | null) => void;
  removeJob: (jobId: string) => void;
  clearAll: () => void;
}

const MAX_HISTORY = 20;

export const useJobsStore = create<JobsState>((set) => ({
  history: [],
  activeJobId: null,

  pushJob: (j) =>
    set((s) => {
      const entry: JobEntry = {
        ...j,
        startedAt: new Date().toISOString(),
        status: "queued",
        progress: 0,
        result: null,
        error: null,
      };
      const next = [entry, ...s.history.filter((x) => x.jobId !== j.jobId)].slice(
        0,
        MAX_HISTORY
      );
      return { history: next, activeJobId: j.jobId };
    }),

  updateJob: (jobId, patch) =>
    set((s) => ({
      history: s.history.map((j) => (j.jobId === jobId ? { ...j, ...patch } : j)),
    })),

  setActive: (jobId) => set({ activeJobId: jobId }),

  removeJob: (jobId) =>
    set((s) => ({ history: s.history.filter((j) => j.jobId !== jobId) })),

  clearAll: () => set({ history: [], activeJobId: null }),
}));
