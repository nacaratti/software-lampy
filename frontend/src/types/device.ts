export type DeviceType = "fiber_active" | "fiber_passive" | "fbg" | "coupler_wdm" | "pump_source";
export type DeviceCategory = "custom" | "shelf";

export interface Device {
  id: string;
  name: string;
  description: string;
  device_type: DeviceType;
  category: DeviceCategory;
  manufacturer: string;
  part_number: string;
  parameters: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DeviceCreate {
  name: string;
  description: string;
  device_type: DeviceType;
  category: DeviceCategory;
  manufacturer: string;
  part_number: string;
  parameters: Record<string, unknown>;
}

export interface DeviceUpdate {
  name?: string;
  description?: string;
  manufacturer?: string;
  part_number?: string;
  parameters?: Record<string, unknown>;
}

// ---- default parameter templates per device type ----

export const defaultParams: Record<DeviceType, Record<string, unknown>> = {
  fiber_active: {
    core_radius_um: 2.5,
    clad_radius_um: 62.5,
    coating_radius_um: 87.5,
    NA: 0.12,
    n_core: 1.46,
    n_clad: 1.454,
    cutoff_wavelength_nm: 900,
    background_loss_db_m: 0.005,
    peak_absorption_dB_m: 200,
    absorption_wavelength_nm: 976,
    tau_ms: 0.84,
    N_total: 3e25,
  },
  fiber_passive: {
    core_radius_um: 4.1,
    clad_radius_um: 62.5,
    coating_radius_um: 87.5,
    NA: 0.14,
    n_core: 1.468,
    n_clad: 1.463,
    MFD_um: 9.2,
    cutoff_wavelength_nm: 1260,
    attenuation_db_km: 0.35,
  },
  fbg: {
    grating_type: "uniform",
    central_wavelength_nm: 1064.0,
    reflectivity: 0.99,
    bandwidth_nm: 0.3,
    period_nm: 366.0,
    length_mm: 10.0,
    dn: 5e-4,
    n_eff: 1.453,
  },
  coupler_wdm: {
    port_count: 3,
    wavelength_1_nm: 976.0,
    wavelength_2_nm: 1064.0,
    insertion_loss_port1_db: 0.3,
    insertion_loss_port2_db: 0.4,
    isolation_db: 20.0,
    fiber_type: "HI1060",
  },
  pump_source: {
    wavelength_nm: 976.0,
    power_w: 0.5,
    linewidth_nm: 0.5,
    fiber_type: "HI1060",
    connector_type: "FC/APC",
    polarization: "unpolarized",
  },
};

export const deviceTypeLabels: Record<DeviceType, string> = {
  fiber_active: "Active Fiber",
  fiber_passive: "Passive Fiber",
  fbg: "FBG / Mirror",
  coupler_wdm: "Coupler / WDM",
  pump_source: "Pump Source",
};
