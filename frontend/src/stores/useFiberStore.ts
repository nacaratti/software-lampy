import { create } from "zustand";
import type { FiberConfig } from "@/types/fiber";

const defaultFiber: FiberConfig = {
  kind: "step",
  core_radius_um: 4.0,
  cladding_radius_um: 62.5,
  core_material: { kind: "germanosilicate", geo2_fraction: 0.035, index: null },
  cladding_material: { kind: "silica", geo2_fraction: null, index: null },
};

interface FiberState {
  fiber: FiberConfig;
  wavelength_nm: number;
  setFiber: (f: FiberConfig) => void;
  setWavelength: (wl: number) => void;
}

export const useFiberStore = create<FiberState>((set) => ({
  fiber: defaultFiber,
  wavelength_nm: 1550,
  setFiber: (f) => set({ fiber: f }),
  setWavelength: (wl) => set({ wavelength_nm: wl }),
}));
