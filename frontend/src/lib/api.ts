import type {
  ModeAnalyticalRequest,
  ModeFDRequest,
  Mode2DRequest,
  ModesResponse,
} from "@/types/modes";
import type { PowerASERequest } from "@/types/power";
import type { BPMRequest } from "@/types/bpm";
import type { JobCreatedResponse, JobInfo } from "@/types/jobs";
import type {
  IndexProfilePreviewRequest,
  IndexProfilePreviewResponse,
} from "@/types/fiber";
import type { FBGCalculationRequest, FBGCalculationResponse, PhaseMaskRequest, PhaseMaskResponse } from "@/types/fbg";
import type { SplicingCalculationRequest, SplicingCalculationResponse } from "@/types/splicing";
import type { ThermalCalculationRequest, ThermalCalculationResponse } from "@/types/thermal";
import type { Device, DeviceCreate, DeviceUpdate } from "@/types/device";

class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`API error ${status}: ${detail}`);
  }
}

async function post<TReq, TRes>(path: string, body: TReq): Promise<TRes> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const json = await res.json();
      detail = json.detail ?? detail;
    } catch {
      /* noop */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<TRes>;
}

async function get<TRes>(path: string): Promise<TRes> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new ApiError(res.status, res.statusText);
  }
  return res.json() as Promise<TRes>;
}

async function put<TReq, TRes>(path: string, body: TReq): Promise<TRes> {
  const res = await fetch(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const json = await res.json();
      detail = json.detail ?? detail;
    } catch { /* noop */ }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<TRes>;
}

async function del(path: string): Promise<void> {
  const res = await fetch(path, { method: "DELETE" });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const json = await res.json();
      detail = json.detail ?? detail;
    } catch { /* noop */ }
    throw new ApiError(res.status, detail);
  }
}

export const api = {
  previewIndex: (req: IndexProfilePreviewRequest) =>
    post<IndexProfilePreviewRequest, IndexProfilePreviewResponse>(
      "/api/fibers/preview-index",
      req
    ),

  modesAnalytical: (req: ModeAnalyticalRequest) =>
    post<ModeAnalyticalRequest, ModesResponse>("/api/modes/analytical", req),
  modesFD: (req: ModeFDRequest) =>
    post<ModeFDRequest, ModesResponse>("/api/modes/fd", req),
  modes2D: (req: Mode2DRequest) =>
    post<Mode2DRequest, ModesResponse>("/api/modes/2d", req),

  startASE: (req: PowerASERequest) =>
    post<PowerASERequest, JobCreatedResponse>("/api/power/ase", req),
  startBPM: (req: BPMRequest) =>
    post<BPMRequest, JobCreatedResponse>("/api/bpm", req),

  calculateFBG: (req: FBGCalculationRequest) =>
    post<FBGCalculationRequest, FBGCalculationResponse>("/api/fbg/calculate", req),
  calculatePhaseMask: (req: PhaseMaskRequest) =>
    post<PhaseMaskRequest, PhaseMaskResponse>("/api/fbg/phase-mask", req),
  calculateSplicing: (req: SplicingCalculationRequest) =>
    post<SplicingCalculationRequest, SplicingCalculationResponse>("/api/splicing/calculate", req),
  calculateThermal: (req: ThermalCalculationRequest) =>
    post<ThermalCalculationRequest, ThermalCalculationResponse>("/api/thermal/calculate", req),

  getJob: (jobId: string) => get<JobInfo>(`/api/jobs/${jobId}`),
  getJobResult: <T = unknown>(jobId: string) => get<T>(`/api/jobs/${jobId}/result`),
  cancelJob: (jobId: string) =>
    fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" }),

  listDevices: (params?: { device_type?: string; category?: string }) => {
    const qs = new URLSearchParams();
    if (params?.device_type) qs.set("device_type", params.device_type);
    if (params?.category) qs.set("category", params.category);
    const query = qs.toString();
    return get<Device[]>(`/api/devices${query ? `?${query}` : ""}`);
  },
  createDevice: (body: DeviceCreate) => post<DeviceCreate, Device>("/api/devices", body),
  getDevice: (id: string) => get<Device>(`/api/devices/${id}`),
  updateDevice: (id: string, body: DeviceUpdate) => put<DeviceUpdate, Device>(`/api/devices/${id}`, body),
  deleteDevice: (id: string) => del(`/api/devices/${id}`),
};

export { ApiError };
