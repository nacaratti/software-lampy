// Mirrors backend/app/schemas/system.py
import type { EncodedArray } from "@/types/common";

export type SystemNodeKind =
  | "pump_source"
  | "seed"
  | "fiber_active"
  | "fiber_passive"
  | "fbg"
  | "coupler_wdm"
  | "splice"
  | "power_combiner"
  | "osa"
  | "power_meter"
  | "beam_profiler";

export interface SystemNodeConfig {
  id: string;
  kind: SystemNodeKind;
  label?: string;
  params: Record<string, unknown>;
}

export interface SystemEdgeConfig {
  id: string;
  source: string;
  target: string;
  source_port?: string;
  target_port?: string;
  loss_db?: number;
}

export interface SystemSimulateRequest {
  nodes: SystemNodeConfig[];
  edges: SystemEdgeConfig[];
}

export interface SystemValidateResponse {
  valid: boolean;
  issues: string[];
}

export interface SpectrumPayload {
  wavelengths_nm: number[];
  powers_w: number[];
  kinds: ("pump" | "signal" | "ase")[];
  widths_nm: number[];
  total_power_w: number;
}

export interface OsaTraceData {
  wavelengths_nm: number[];
  power_dbm: number[];
  rbw_nm: number;
  peak_wavelength_nm: number;
  peak_power_dbm: number;
  osnr_db: number | null;
  total_power_w: number;
}

export interface PowerMeterReadingData {
  total_power_w: number;
  total_power_dbm: number;
  band_power_w: Record<string, number>;
  band_power_dbm: Record<string, number>;
}

export interface BeamProfilerData {
  z_m: EncodedArray;
  x_m: EncodedArray;
  y_m: EncodedArray;
  images: EncodedArray; // shape (num_z, Nx, Ny)
  wx_m: EncodedArray;
  wy_m: EncodedArray;
  w0x_m: number;
  w0y_m: number;
  z0x_m: number;
  z0y_m: number;
  m2x: number;
  m2y: number;
  divergence_x_mrad: number;
  divergence_y_mrad: number;
  bpp_mm_mrad: number;
  wavelength_m: number;
  v_number: number;
  is_single_mode: boolean;
  waist_index: number;
  tmi_risk_fraction?: number;
}

export interface SystemOutputSummary {
  kind: string;
  signal: SpectrumPayload;
  total_power_w: number;
  signal_power_w: number;
  pump_power_w: number;
  ase_power_w: number;
  source_fiber: { node_id: string; kind: string; params: Record<string, unknown> } | null;
  osa?: OsaTraceData;
  power_meter?: PowerMeterReadingData;
  beam?: BeamProfilerData;
}

export interface SystemSimulationResult {
  edges: Record<string, SpectrumPayload>;
  nodes: Record<string, Record<string, unknown>>;
  outputs: Record<string, SystemOutputSummary>;
  warnings: string[];
}

// ---- persisted projects ----

export interface SystemCreate {
  name: string;
  description: string;
  graph: Record<string, unknown>;
}

export interface SystemUpdate {
  name?: string;
  description?: string;
  graph?: Record<string, unknown>;
}

export interface SystemOut {
  id: string;
  name: string;
  description: string;
  graph: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SystemSummary {
  id: string;
  name: string;
  description: string;
  node_count: number;
  created_at: string;
  updated_at: string;
}
