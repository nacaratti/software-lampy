import type { FiberConfig } from "./fiber";
import type { EncodedArray } from "./common";

export interface InitialFieldConfig {
  kind: "gaussian" | "fundamental_mode";
  waist_um: number;
  x_offset_um: number;
  y_offset_um: number;
  tilt_x_mrad: number;
  tilt_y_mrad: number;
}

export interface BPMRequest {
  fiber: FiberConfig;
  wavelength_nm: number;
  length_mm: number;
  initial_field: InitialFieldConfig;
  grid_size: number;
  z_steps: number;
  grid_width_factor: number;
  save_z_slices: number;
}

export interface BPMResponse {
  z_mm: number[];
  x_um: number[];
  y_um: number[];
  intensity_slices: EncodedArray;
  power_vs_z: number[];
  z_step_indices: number[];
}
