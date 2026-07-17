import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { HomePage } from "@/pages/HomePage";
import { ModeSolverPage } from "@/pages/ModeSolverPage";
import { PowerSimPage } from "@/pages/PowerSimPage";
import { BPMPage } from "@/pages/BPMPage";
import { GNLSEPage } from "@/pages/GNLSEPage";
import { PowerRampPage } from "@/pages/PowerRampPage";
import { FBGPage } from "@/pages/FBGPage";
import { SplicingPage } from "@/pages/SplicingPage";
import { ThermalPage } from "@/pages/ThermalPage";
import { CouplerPage } from "@/pages/CouplerPage";
import { TaperPage } from "@/pages/TaperPage";
import { DeviceLibraryPage } from "@/pages/DeviceLibraryPage";
import { SystemBuilderPage } from "@/pages/SystemBuilderPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/modes" element={<ModeSolverPage />} />
        <Route path="/power" element={<PowerSimPage />} />
        <Route path="/bpm" element={<BPMPage />} />
        <Route path="/gnlse" element={<GNLSEPage />} />
        <Route path="/power-ramp" element={<PowerRampPage />} />
        <Route path="/fbg" element={<FBGPage />} />
        <Route path="/splicing" element={<SplicingPage />} />
        <Route path="/thermal" element={<ThermalPage />} />
        <Route path="/coupler" element={<CouplerPage />} />
        <Route path="/taper" element={<TaperPage />} />
        <Route path="/devices" element={<DeviceLibraryPage />} />
        <Route path="/system" element={<SystemBuilderPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
