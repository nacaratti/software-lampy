import type { ActiveFiberConfig } from "./fiber";
import type { EncodedArray } from "./common";

export interface PumpConfig {
  name: string;
  wavelength_nm: number;
  power_forward_w: number;
  power_backward_w: number;
  overlap: number;
  loss_db_per_m: number;
}

export interface SignalConfig {
  name: string;
  wavelength_nm: number;
  power_forward_w: number;
  power_backward_w: number;
  overlap: number;
  loss_db_per_m: number;
  reflectivity_input: number;
  reflectivity_output: number;
}

export interface ASEConfig {
  enabled: boolean;
  wavelength_min_nm: number;
  wavelength_max_nm: number;
  num_channels: number;
  overlap: number;
  loss_db_per_m: number;
}

export interface PowerASERequest {
  active_fiber: ActiveFiberConfig;
  length_m: number;
  pumps: PumpConfig[];
  signals: SignalConfig[];
  ase: ASEConfig;
  num_z_points: number;
  max_iterations: number;
  tolerance: number;
  relaxation_factor: number;
}

export interface PowerASEResponse {
  z_m: number[];
  pump_wavelengths_nm: number[];
  signal_wavelengths_nm: number[];
  ase_wavelengths_nm: number[];
  pumps_forward: EncodedArray;
  pumps_backward: EncodedArray;
  signals_forward: EncodedArray;
  signals_backward: EncodedArray;
  ase_forward: EncodedArray;
  ase_backward: EncodedArray;
  n2_fraction: EncodedArray;
  summary: Record<string, number>;
}
