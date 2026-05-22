import { EncodedArray } from "./common";

export interface SplicingCalculationRequest {
  core_n1: number;
  cladding_n1: number;
  radius_um1: number;
  core_n2: number;
  cladding_n2: number;
  radius_um2: number;
  wavelength_nm: number;
  offset_x_um: number;
  offset_y_um: number;
  tilt_x_mrad: number;
  tilt_y_mrad: number;
  grid_size: number;
}

export interface SplicingCalculationResponse {
  coupling_coefficient: number;
  loss_db: number;
  total_coupling: number;
  total_loss_db: number;
  field_1: EncodedArray;
  field_2: EncodedArray;
  extent_um: number;
}
