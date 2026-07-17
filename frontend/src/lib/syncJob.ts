import { useJobsStore } from "@/stores/useJobsStore";
import type { JobKind } from "@/types/jobs";

function newJobId(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  return `sync-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function useSyncJob() {
  const pushJob = useJobsStore((s) => s.pushJob);
  const updateJob = useJobsStore((s) => s.updateJob);

  return async function runSync<T>(
    kind: JobKind,
    label: string,
    config: unknown,
    fn: () => Promise<T>
  ): Promise<T> {
    const jobId = newJobId();
    pushJob({ jobId, kind, label, config });
    updateJob(jobId, { status: "running" });
    try {
      const res = await fn();
      updateJob(jobId, { status: "completed", progress: 1, result: res });
      return res;
    } catch (e) {
      updateJob(jobId, { status: "error", error: String(e) });
      throw e;
    }
  };
}
