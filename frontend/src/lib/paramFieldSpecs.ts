import { z } from "zod";

export type FieldSpec =
  | {
      key: string;
      label: string;
      type: "number";
      unit?: string;
      min?: number;
      max?: number;
      step?: number;
      default: number;
    }
  | { key: string; label: string; type: "text"; default: string }
  | {
      key: string;
      label: string;
      type: "select";
      options: { value: string; label: string }[];
      default: string;
    };

/** Builds a Zod object schema from a field-spec list. Unknown extra keys
 * (legacy data, catalog metadata not yet modeled) pass through untouched. */
export function schemaFromSpecs(specs: FieldSpec[]) {
  const shape: Record<string, z.ZodTypeAny> = {};
  for (const s of specs) {
    if (s.type === "number") {
      let f = z.coerce.number({ invalid_type_error: `${s.label} must be a number` });
      if (s.min !== undefined) f = f.min(s.min, `${s.label} must be ≥ ${s.min}`);
      if (s.max !== undefined) f = f.max(s.max, `${s.label} must be ≤ ${s.max}`);
      shape[s.key] = f;
    } else if (s.type === "select") {
      const values = s.options.map((o) => o.value) as [string, ...string[]];
      shape[s.key] = z.enum(values);
    } else {
      shape[s.key] = z.string();
    }
  }
  return z.object(shape).passthrough();
}

/** Field specs, keyed by Device Library `device_type` / System Builder node `kind`.
 * The two contexts share the same physical vocabulary; System Builder adds a
 * couple of per-instance fields (e.g. `length_m`, `ion`) that don't belong in
 * a catalog entry but are still safe to expose everywhere for consistency. */
export const PARAM_FIELD_SPECS: Record<string, FieldSpec[]> = {
  fiber_active: [
    { key: "core_radius_um", label: "Core radius", type: "number", unit: "µm", min: 0.1, max: 500, step: 0.1, default: 2.5 },
    { key: "clad_radius_um", label: "Cladding radius", type: "number", unit: "µm", min: 1, max: 2000, step: 0.5, default: 62.5 },
    { key: "coating_radius_um", label: "Coating radius", type: "number", unit: "µm", min: 1, max: 2000, step: 0.5, default: 87.5 },
    { key: "NA", label: "Numerical aperture", type: "number", min: 0.01, max: 1, step: 0.01, default: 0.12 },
    { key: "n_core", label: "Core index", type: "number", min: 1, max: 3, step: 0.0001, default: 1.46 },
    { key: "n_clad", label: "Cladding index", type: "number", min: 1, max: 3, step: 0.0001, default: 1.454 },
    { key: "cutoff_wavelength_nm", label: "Cutoff wavelength", type: "number", unit: "nm", min: 100, max: 5000, step: 1, default: 900 },
    { key: "background_loss_db_m", label: "Background loss", type: "number", unit: "dB/m", min: 0, max: 10, step: 0.001, default: 0.005 },
    { key: "peak_absorption_dB_m_976nm", label: "Peak absorption @976nm", type: "number", unit: "dB/m", min: 0, max: 5000, step: 0.1, default: 200 },
    { key: "tau_ms", label: "Upper-state lifetime", type: "number", unit: "ms", min: 0.001, max: 100, step: 0.01, default: 0.84 },
    // Pump/signal overlap Γ is now computed automatically from the guided-mode
    // and dopant-profile overlap (see fibersim.system.overlap) — no manual
    // scalar to guess. The backend still accepts explicit gamma_pump/
    // gamma_signal overrides for advanced use, just not exposed here.
    { key: "N_total", label: "Dopant density", type: "number", unit: "ions/m³", min: 1e22, max: 1e28, step: 1e24, default: 3e25 },
    {
      key: "ion", label: "Active ion", type: "select", default: "yb",
      options: [
        { value: "yb", label: "Yb³⁺ (1030–1100 nm)" },
        { value: "er", label: "Er³⁺ (1530–1610 nm)" },
        { value: "tm", label: "Tm³⁺ (1850–2050 nm)" },
      ],
    },
    { key: "length_m", label: "Length (this segment)", type: "number", unit: "m", min: 0.001, max: 1000, step: 0.01, default: 2.0 },
  ],
  fiber_passive: [
    { key: "core_radius_um", label: "Core radius", type: "number", unit: "µm", min: 0.1, max: 500, step: 0.1, default: 4.1 },
    { key: "clad_radius_um", label: "Cladding radius", type: "number", unit: "µm", min: 1, max: 2000, step: 0.5, default: 62.5 },
    { key: "coating_radius_um", label: "Coating radius", type: "number", unit: "µm", min: 1, max: 2000, step: 0.5, default: 87.5 },
    { key: "NA", label: "Numerical aperture", type: "number", min: 0.01, max: 1, step: 0.01, default: 0.14 },
    { key: "n_core", label: "Core index", type: "number", min: 1, max: 3, step: 0.0001, default: 1.468 },
    { key: "n_clad", label: "Cladding index", type: "number", min: 1, max: 3, step: 0.0001, default: 1.463 },
    { key: "MFD_um", label: "Mode field diameter", type: "number", unit: "µm", min: 0.5, max: 200, step: 0.1, default: 9.2 },
    { key: "cutoff_wavelength_nm", label: "Cutoff wavelength", type: "number", unit: "nm", min: 100, max: 5000, step: 1, default: 1260 },
    { key: "attenuation_db_km", label: "Attenuation", type: "number", unit: "dB/km", min: 0, max: 10000, step: 0.01, default: 0.35 },
    { key: "length_m", label: "Length (this segment)", type: "number", unit: "m", min: 0.001, max: 100000, step: 0.1, default: 1.0 },
  ],
  fbg: [
    {
      key: "grating_type", label: "Grating type", type: "select", default: "uniform",
      options: [
        { value: "uniform", label: "Uniform" },
        { value: "chirped", label: "Chirped" },
        { value: "apodized", label: "Apodized" },
        { value: "tilted", label: "Tilted" },
        { value: "lpg", label: "Long-period (LPG)" },
      ],
    },
    { key: "central_wavelength_nm", label: "Central wavelength", type: "number", unit: "nm", min: 200, max: 20000, step: 0.01, default: 1064.0 },
    { key: "reflectivity", label: "Peak reflectivity", type: "number", min: 0, max: 1, step: 0.001, default: 0.99 },
    { key: "bandwidth_nm", label: "Bandwidth (FWHM)", type: "number", unit: "nm", min: 0.001, max: 100, step: 0.01, default: 0.3 },
    { key: "period_nm", label: "Grating period", type: "number", unit: "nm", min: 100, max: 2000, step: 0.01, default: 366.0 },
    { key: "length_mm", label: "Length", type: "number", unit: "mm", min: 0.01, max: 1000, step: 0.1, default: 10.0 },
    { key: "dn", label: "Index modulation δn", type: "number", min: 1e-6, max: 0.01, step: 1e-5, default: 5e-4 },
    { key: "n_eff", label: "Effective index", type: "number", min: 1, max: 3, step: 0.0001, default: 1.453 },
  ],
  coupler_wdm: [
    { key: "port_count", label: "Port count", type: "number", min: 2, max: 8, step: 1, default: 3 },
    { key: "wavelength_1_nm", label: "Wavelength 1 (pump)", type: "number", unit: "nm", min: 200, max: 20000, step: 0.1, default: 976.0 },
    { key: "wavelength_2_nm", label: "Wavelength 2 (signal)", type: "number", unit: "nm", min: 200, max: 20000, step: 0.1, default: 1064.0 },
    { key: "insertion_loss_port1_db", label: "Insertion loss (port 1)", type: "number", unit: "dB", min: 0, max: 30, step: 0.01, default: 0.3 },
    { key: "insertion_loss_port2_db", label: "Insertion loss (port 2)", type: "number", unit: "dB", min: 0, max: 30, step: 0.01, default: 0.4 },
    { key: "isolation_db", label: "Isolation", type: "number", unit: "dB", min: 0, max: 100, step: 0.1, default: 20.0 },
    { key: "fiber_type", label: "Fiber type", type: "text", default: "HI1060" },
  ],
  pump_source: [
    { key: "wavelength_nm", label: "Wavelength", type: "number", unit: "nm", min: 200, max: 20000, step: 0.1, default: 976.0 },
    { key: "power_w", label: "Power", type: "number", unit: "W", min: 0, max: 100000, step: 0.01, default: 0.5 },
    { key: "linewidth_nm", label: "Linewidth", type: "number", unit: "nm", min: 0, max: 100, step: 0.01, default: 0.5 },
    { key: "fiber_type", label: "Fiber type", type: "text", default: "HI1060" },
    { key: "connector_type", label: "Connector type", type: "text", default: "FC/APC" },
    {
      key: "polarization", label: "Polarization", type: "select", default: "unpolarized",
      options: [
        { value: "unpolarized", label: "Unpolarized" },
        { value: "linear", label: "Linear" },
        { value: "pm", label: "Polarization-maintaining" },
      ],
    },
  ],
  seed: [
    { key: "wavelength_nm", label: "Wavelength", type: "number", unit: "nm", min: 200, max: 20000, step: 0.1, default: 1064.0 },
    { key: "power_w", label: "Power", type: "number", unit: "W", min: 0, max: 100000, step: 1e-6, default: 0.01 },
    { key: "linewidth_nm", label: "Linewidth", type: "number", unit: "nm", min: 0, max: 100, step: 0.001, default: 0.1 },
  ],
  splice: [
    { key: "loss_db", label: "Splice loss", type: "number", unit: "dB", min: 0, max: 30, step: 0.001, default: 0.05 },
  ],
  power_combiner: [
    { key: "insertion_loss_db", label: "Insertion loss", type: "number", unit: "dB", min: 0, max: 30, step: 0.01, default: 0.5 },
  ],
  osa: [
    { key: "rbw_nm", label: "Resolution bandwidth", type: "number", unit: "nm", min: 0.001, max: 50, step: 0.001, default: 0.1 },
  ],
  power_meter: [],
  beam_profiler: [
    { key: "grid_n", label: "Grid resolution", type: "number", min: 32, max: 512, step: 1, default: 128 },
    { key: "num_z", label: "Camera sweep planes", type: "number", min: 5, max: 101, step: 1, default: 21 },
    { key: "z_span_factor", label: "Sweep range (× Rayleigh length)", type: "number", min: 0.5, max: 50, step: 0.5, default: 6.0 },
  ],
};

export function fieldSpecsFor(kind: string): FieldSpec[] | undefined {
  return PARAM_FIELD_SPECS[kind];
}
