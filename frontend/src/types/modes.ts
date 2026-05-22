import type { FiberConfig } from "./fiber";
import type { EncodedArray } from "./common";

export interface ModeAnalyticalRequest {
  fiber: FiberConfig;
  wavelength_nm: number;
  grid_size: number;
  max_plot_radius_factor: number;
}

export interface ModeFDRequest {
  fiber: FiberConfig;
  wavelength_nm: number;
  l: number;
  grid_points: number;
  plot_grid_size: number;
  max_plot_radius_factor: number;
}

export interface Mode2DRequest {
  fiber: FiberConfig;
  wavelength_nm: number;
  grid_size: number;
  grid_width_factor: number;
  num_modes: number;
}

export interface ModeResult {
  l: number;
  m: number;
  n_eff: number;
  beta: number;
  u: number | null;
  w: number | null;
  a_eff_um2?: number;
  power_core_pct?: number;
  intensity_2d: EncodedArray;
  extent_um: number;
}

export interface ModesResponse {
  method: "analytical" | "fd" | "2d";
  wavelength_nm: number;
  n_core: number;
  n_cladding: number;
  v_number: number | null;
  num_modes: number;
  modes: ModeResult[];
}
