import { EncodedArray } from "./common";

export interface ThermalCalculationRequest {
  fiber_length_m: number;
  core_radius_um: number;
  clad_radius_um: number;
  coating_radius_um: number;
  N_total: number;
  tau_ms: number;
  lambda_pump_nm: number;
  lambda_signal_nm: number;
  gamma_pump: number;
  gamma_signal: number;
  P_pump_forward_w: number;
  P_pump_backward_w: number;
  P_signal_seed_w: number;
  pumping: "forward" | "backward" | "bidirectional";
  k_core: number;
  k_clad: number;
  k_coat: number;
  h_conv: number;
  T_ambient_celsius: number;
  num_z_points: number;
  num_r_points: number;
}

export interface ThermalCalculationResponse {
  z_m: number[];
  pumps_forward: number[];
  pumps_backward: number[];
  pumps_total: number[];
  signals_forward: number[];
  n2_fraction: number[];
  r_um: number[];
  T_center_celsius: number[];
  T_surface_celsius: number[];
  T_2d: EncodedArray;
  gain_db: number;
  efficiency: number;
  output_power_w: number;
  T_max_celsius: number;
}
