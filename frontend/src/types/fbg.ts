export interface PhaseMaskRequest {
  grating_type: "uniform" | "chirped" | "apodized" | "tilted" | "lpg";
  n_eff: number;
  length_mm: number;
  dn: number;
  period_nm: number;
  period_end_nm: number;
  chirp_type: "linear" | "quadratic";
  apodization_profile: "gaussian" | "raised_cosine" | "tanh" | "hamming";
  profile_strength: number;
  lambda_uv_nm: number;
  num_sections: number;
}

export interface PhaseMaskResponse {
  z_mm: number[];
  period_pm_nm: number[];
  dn_profile: number[];
  kappa_profile: number[];
  phase_rad: number[];
  params: {
    grating_type: string;
    bragg_wavelength_nm: number;
    period_pm_center_nm: number;
    period_pm_min_nm: number;
    period_pm_max_nm: number;
    length_mm: number;
    dn_peak: number;
    dn_min: number;
    kappa_peak: number;
    kappa_L_product: number;
    phase_total_rad: number;
    phase_total_cycles: number;
    lambda_uv_nm: number;
    diffraction_angle_deg: number | null;
    viable: boolean;
    viability_message: string;
    recommended_technique: string;
    required_precision_nm: number;
    typical_fluence: string;
  };
}

export interface FBGCalculationRequest {
  grating_type: "uniform" | "chirped" | "apodized" | "tilted" | "lpg";
  n_eff: number;
  length_mm: number;
  dn: number;
  period_nm: number;
  period_um: number;
  period_end_nm: number;
  chirp_type: "linear" | "quadratic";
  apodization_profile: "gaussian" | "raised_cosine" | "tanh" | "hamming";
  profile_strength: number;
  n_eff_cladding_base: number;
  tilt_angle_deg: number;
  num_cladding_modes: number;
  n_eff_cladding: number;
  target_mode_order: number;
  wl_start_nm: number | null;
  wl_end_nm: number | null;
  num_points: number;
  num_sections: number;
}

export interface FBGCalculationResponse {
  wavelengths_nm: number[];
  spectrum: number[];
  metadata: {
    bragg_wavelength_nm?: number;
    fwhm_nm?: number | null;
    peak_reflectivity?: number;
    bandwidth_3db_nm?: number | null;
    kappa?: number;
    grating_type: string;
    bragg_start_nm?: number;
    bragg_end_nm?: number;
    chirp_type?: string;
    apodization_profile?: string;
    profile_strength?: number;
    tilt_angle_deg?: number;
    num_cladding_modes?: number;
    resonance_wavelengths_nm?: number[];
    min_transmission?: number;
    target_mode_order?: number;
    dip_depth_db?: number;
    period_um?: number;
  };
}
