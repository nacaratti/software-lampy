import { Waves, Zap, Aperture, Home, Grid3X3, Link, Thermometer, Library, Cpu, GitFork, Triangle, Sparkles, FlaskConical } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  desc: string;
  /** "g x" chord shortcut suffix, if any (matches AppShell's useHotkeys calls). */
  chord?: string;
}

export const navItems: NavItem[] = [
  { to: "/", label: "Home", icon: Home, desc: "Overview & quick starts", chord: "h" },
  { to: "/modes", label: "Fiber Modes Solver", icon: Aperture, desc: "LP modes, fields", chord: "m" },
  { to: "/power", label: "Power & ASE", icon: Zap, desc: "Pumps, signals, ASE", chord: "p" },
  { to: "/bpm", label: "BPM", icon: Waves, desc: "Beam propagation", chord: "b" },
  { to: "/gnlse", label: "Ultrafast Pulse (GNLSE)", icon: Sparkles, desc: "SPM, Raman, gain-coupled propagation" },
  { to: "/power-ramp", label: "Power Ramp Explorer", icon: FlaskConical, desc: "SRS/SBS/TMI/ESA vs. pump power" },
  { to: "/fbg", label: "FBG Solver", icon: Grid3X3, desc: "Bragg gratings, phase mask" },
  { to: "/splicing", label: "Splicing Loss", icon: Link, desc: "Fiber splicing overlap" },
  { to: "/thermal", label: "Thermal Simulator", icon: Thermometer, desc: "Cavity heating & pumps" },
  { to: "/coupler", label: "Fiber Coupler", icon: GitFork, desc: "CMT evanescent coupling" },
  { to: "/taper", label: "Tapered Fiber", icon: Triangle, desc: "Adiabatic taper analysis" },
  { to: "/devices", label: "Device Library", icon: Library, desc: "Fibers, FBGs, couplers" },
  { to: "/system", label: "Laser System", icon: Cpu, desc: "Drag-and-drop canvas" },
];
