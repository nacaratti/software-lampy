import { useEffect, useRef, useState } from "react";
import type { JobStatus, WsMessage } from "@/types/jobs";

export interface JobSocketState<T = unknown> {
  status: JobStatus;
  progress: number;
  result: T | null;
  error: string | null;
}

export function useJobSocket<T = unknown>(jobId: string | null): JobSocketState<T> {
  const [state, setState] = useState<JobSocketState<T>>({
    status: "queued",
    progress: 0,
    result: null,
    error: null,
  });
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!jobId) return;
    setState({ status: "queued", progress: 0, result: null, error: null });

    const proto = location.protocol === "https:" ? "wss" : "ws";
    const host = location.host;
    const ws = new WebSocket(`${proto}://${host}/ws/jobs/${jobId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WsMessage;
        setState((s) => {
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
            default:
              return s;
          }
        });
      } catch {
        /* ignore malformed */
      }
    };

    ws.onerror = () => {
      setState((s) => ({ ...s, error: s.error ?? "websocket error" }));
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [jobId]);

  return state;
}
