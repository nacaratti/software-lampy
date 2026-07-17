export interface CouplerCalculationRequest {
  core_radius_um: number;
  n_core: number;
  n_clad: number;
  fiber_separation_um: number;
  coupling_length_mm: number;
  lambda_center_nm: number;
  P1_in_w: number;
  P2_in_w: number;
  delta_rad_per_m: number;
  lambda_min_nm: number;
  lambda_max_nm: number;
  num_z: number;
  num_lambda: number;
}

export interface CouplerCalculationResponse {
  z_mm: number[];
  P1_z: number[];
  P2_z: number[];
  lambda_nm: number[];
  P1_lambda: number[];
  P2_lambda: number[];
  kappa_lambda: number[];
  splitting_ratio_lambda: number[];
  kappa_c: number;
  coupling_length_mm: number;
  splitting_ratio: number;
  throughput_db: number;
  cross_db: number;
  P1_out: number;
  P2_out: number;
}
