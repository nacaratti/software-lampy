export interface TaperCalculationRequest {
  core_radius_um: number;
  clad_radius_um: number;
  n_core: number;
  n_clad: number;
  taper_ratio: number;
  L_taper_mm: number;
  L_waist_mm: number;
  taper_shape: "cosine" | "linear" | "exponential";
  lambda_nm: number;
  num_z: number;
}

export interface TaperCalculationResponse {
  z_mm:              number[];
  r_core_um:         number[];
  r_clad_um:         number[];
  V_core:            number[];
  V_clad:            number[];
  mfd_w2_um:         number[];
  mfd_weff_um:       number[];
  mfd_hwhm_um:       number[];
  A_eff_um2:         number[];
  taper_angle_mrad:  number[];
  omega_c_mrad:      number[];
  eta:               number[];
  z_beat_mm:         number[];
  is_lp11:           boolean[];
  in_cladding_mode:  boolean[];
  V_input:           number;
  V_waist:           number;
  V_clad_input:      number;
  V_clad_waist:      number;
  mfd_input_um:      number;
  mfd_waist_um:      number;
  max_eta:           number;
  is_adiabatic:      boolean;
  transmission:      number;
  transmission_db:   number;
  L_total_mm:        number;
  lp11_filtered:     boolean;
}
