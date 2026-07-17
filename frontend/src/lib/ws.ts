import { useEffect, useRef, useState } from "react";
import type { JobStatus, WsMessage } from "@/types/jobs";
import { API_BASE } from "@/lib/api";

export interface JobSocketState<T = unknown> {
  status: JobStatus;
  progress: number;
  result: T | null;
  error: string | null;
}

const TERMINAL_STATUSES: JobStatus[] = ["completed", "error", "cancelled", "expired"];
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY_MS = 1000;

function wsUrl(jobId: string): string {
  if (API_BASE) {
    const base = new URL(API_BASE, location.href);
    const proto = base.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${base.host}/ws/jobs/${jobId}`;
  }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws/jobs/${jobId}`;
}

export function useJobSocket<T = unknown>(jobId: string | null): JobSocketState<T> {
  const [state, setState] = useState<JobSocketState<T>>({
    status: "queued",
    progress: 0,
    result: null,
    error: null,
  });
  const statusRef = useRef<JobStatus>("queued");

  useEffect(() => {
    if (!jobId) return;
    setState({ status: "queued", progress: 0, result: null, error: null });
    statusRef.current = "queued";

    let ws: WebSocket | null = null;
    let attempts = 0;
    let disposed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const update = (updater: (s: JobSocketState<T>) => JobSocketState<T>) => {
      setState((s) => {
        const next = updater(s);
        statusRef.current = next.status;
        return next;
      });
    };

    const connect = () => {
      if (disposed) return;
      ws = new WebSocket(wsUrl(jobId));

      ws.onopen = () => {
        attempts = 0;
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as WsMessage;
          update((s) => {
            switch (msg.type) {
              case "status":
                return { ...s, status: msg.status };
              case "progress":
                return { ...s, progress: msg.value };
              case "result":
                return { ...s, result: msg.data as T, progress: 1, status: "completed" };
              case "error":
                return { ...s, error: msg.message, status: "error" };
              case "cancelled":
                return { ...s, status: "cancelled" };
              case "expired":
                return {
                  ...s,
                  status: "expired",
                  error: s.result ? s.error : "Job result expired on the server",
                };
              default:
                return s;
            }
          });
        } catch {
          /* ignore malformed */
        }
      };

      ws.onclose = () => {
        if (disposed || TERMINAL_STATUSES.includes(statusRef.current)) return;
        // Unexpected drop mid-job: retry with backoff, then surface an error.
        if (attempts < MAX_RECONNECT_ATTEMPTS) {
          attempts += 1;
          retryTimer = setTimeout(connect, RECONNECT_DELAY_MS * attempts);
        } else {
          update((s) => ({
            ...s,
            status: "error",
            error: s.error ?? "Lost connection to the job stream",
          }));
        }
      };
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
    };
  }, [jobId]);

  return state;
}
