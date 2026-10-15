// Mirrors backend/app/schemas/fiber.py

export type MaterialKind = "silica" | "germanosilicate" | "phosphate" | "constant";
export type IonKind = "yb" | "er" | "tm";

export interface MaterialConfig {
  kind: MaterialKind;
  geo2_fraction?: number | null;
  index?: number | null;
}

export interface StepIndexConfig {
  kind: "step";
  core_radius_um: number;
  cladding_radius_um: number;
  core_material: MaterialConfig;
  cladding_material: MaterialConfig;
}

export interface GradedIndexConfig {
  kind: "graded";
  core_radius_um: number;
  cladding_radius_um: number;
  core_material: MaterialConfig;
  cladding_material: MaterialConfig;
  alpha: number;
}

export interface DoubleCladConfig {
  kind: "double_clad";
  core_radius_um: number;
  inner_cladding_radius_um: number;
  outer_cladding_radius_um: number;
  core_material: MaterialConfig;
  inner_cladding_material: MaterialConfig;
  outer_cladding_material: MaterialConfig;
}

export type FiberConfig = StepIndexConfig | GradedIndexConfig | DoubleCladConfig;

export interface ActiveFiberConfig {
  geometry: FiberConfig;
  ion: IonKind;
  dopant_density_per_m3: number;
  doping_profile: "uniform" | "gaussian";
}

export interface IndexProfilePreviewRequest {
  fiber: FiberConfig;
  wavelength_nm: number;
  num_points: number;
}

export interface IndexProfilePreviewResponse {
  r_um: number[];
  n: number[];
  n_core: number;
  n_cladding: number;
  v_number: number | null;
}

export interface IonCrossSectionRequest {
  ion: IonKind;
  wavelengths_nm: number[];
}

export interface IonCrossSectionResponse {
  sigma_abs_m2: number[];
  sigma_em_m2: number[];
}
