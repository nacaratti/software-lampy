import type { EncodedArray } from "./common";

export interface PowerRampFiberConfig {
  ion: "yb" | "er" | "tm";
  core_radius_um: number;
  clad_radius_um: number;
  n_core: number;
  n_clad: number;
  N_total: number;
  tau_ms: number;
  background_loss_db_m: number;
  length_m: number;
  inner_cladding_radius_um?: number | null;
}

export interface PowerRampRequest {
  fiber: PowerRampFiberConfig;
  pump_wavelength_nm: number;
  seed_wavelength_nm: number;
  seed_power_w: number;
  pump_power_min_w: number;
  pump_power_max_w: number;
  num_steps: number;
}

export interface EffectSeries {
  key: string;
  label: string;
  applicable: boolean;
  reason: string | null;
  values: (number | null)[];
  threshold: number | null;
  unit: string;
}

export interface PowerRampResponse {
  pump_power_w: number[];
  peak_signal_power_w: number[];
  gain_db: (number | null)[];
  effects: EffectSeries[];
  warnings_by_step: string[][];

  srs_threshold_w: number | null;
  sbs_threshold_w: number | null;

  tmi_m2x: number[];
  tmi_m2y: number[];
  tmi_coupling_fraction: number[];
  tmi_lp01_image: EncodedArray | null;
  tmi_lp11_image: EncodedArray | null;
  tmi_image_x_um: number[];
  tmi_image_y_um: number[];
}
