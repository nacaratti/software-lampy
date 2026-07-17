import type { EncodedArray } from "./common";

export interface GNLSERequest {
  pulse_shape: "gaussian" | "sech2";
  wavelength_nm: number;
  peak_power_w: number;
  duration_fs: number;
  time_window_ps: number;
  num_points: number;

  length_mm: number;
  gamma_per_w_per_km: number;
  beta2_ps2_per_km: number;
  beta3_ps3_per_km: number;
  loss_db_per_m: number;
  self_steepening: boolean;
  raman: boolean;

  enable_gain: boolean;
  small_signal_gain_db_per_m: number;
  saturation_energy_nj: number | null;
  gain_bandwidth_nm: number | null;

  z_steps: number;
  save_z_slices: number;
}

export interface GNLSEResponse {
  z_mm: number[];
  t_ps: number[];
  wavelength_nm: number[];
  temporal_power_slices: EncodedArray; // (Nz_saved, N), W
  spectral_power_slices: EncodedArray; // (Nz_saved, N), a.u.
  input_temporal_power_w: number[];
  output_temporal_power_w: number[];
  input_spectral_power: number[];
  output_spectral_power: number[];
  input_energy_nj: number;
  output_energy_nj: number;
  saturated_gain_db_per_m: number | null;
}
