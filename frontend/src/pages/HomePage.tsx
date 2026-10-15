import { Link } from "react-router-dom";
import {
  ArrowRight, Aperture, Zap, Waves, Grid3X3, Link as LinkIcon,
  Thermometer, Library, Cpu, BookOpen, Layers, Play, GitFork, Triangle, Sparkles, FlaskConical,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const solverCards = [
  {
    to: "/modes",
    title: "Mode Solver",
    icon: Aperture,
    description: "Guided LP modes via analytical (step-index), radial finite-difference, or full 2D eigenvalue methods. Field intensity, V-number, and effective indices.",
    color: "from-violet-500/40 via-violet-500/10 to-transparent",
    accent: "text-violet-300",
  },
  {
    to: "/power",
    title: "Power & ASE",
    icon: Zap,
    description: "Bidirectional steady-state rate equations for Yb, Er, and Tm doped fibers. Full ASE band, multiple pumps and signals, end mirrors for cavity simulation.",
    color: "from-cyan-500/40 via-cyan-500/10 to-transparent",
    accent: "text-cyan-300",
  },
  {
    to: "/fbg",
    title: "FBG Solver",
    icon: Grid3X3,
    description: "Reflection spectra for uniform, chirped, apodized, tilted, and LPG gratings. Phase mask calculation for UV inscription geometry.",
    color: "from-violet-500/30 via-indigo-500/10 to-transparent",
    accent: "text-indigo-300",
  },
  {
    to: "/bpm",
    title: "Beam Propagation (BPM)",
    icon: Waves,
    description: "Paraxial split-step Fourier BPM in 3D. Tilt and misalign the launch, watch coupling efficiency, beat patterns, and leakage along the axis.",
    color: "from-fuchsia-500/40 via-fuchsia-500/10 to-transparent",
    accent: "text-fuchsia-300",
  },
  {
    to: "/gnlse",
    title: "Ultrafast Pulse (GNLSE)",
    icon: Sparkles,
    description: "Split-step Fourier solver for the Generalized Nonlinear Schrödinger Equation — self-phase modulation, Raman scattering, self-steepening, and an optional saturable-gain pass for pulsed fiber amplifiers.",
    color: "from-indigo-500/40 via-indigo-500/10 to-transparent",
    accent: "text-indigo-300",
  },
  {
    to: "/thermal",
    title: "Thermal Simulator",
    icon: Thermometer,
    description: "Yb³⁺ laser cavity with 3-layer heat conduction (core / cladding / coating) coupled to the longitudinal power and gain profile.",
    color: "from-orange-500/30 via-orange-500/10 to-transparent",
    accent: "text-orange-300",
  },
  {
    to: "/splicing",
    title: "Splicing Loss",
    icon: LinkIcon,
    description: "Splice loss via field overlap integral between two fibers with lateral, angular, and waist misalignment.",
    color: "from-teal-500/30 via-teal-500/10 to-transparent",
    accent: "text-teal-300",
  },
  {
    to: "/coupler",
    title: "Fiber Coupler",
    icon: GitFork,
    description: "Directional coupler via coupled-mode theory: power exchange along z, spectral splitting ratio, and coupling coefficient vs. wavelength.",
    color: "from-amber-500/30 via-amber-500/10 to-transparent",
    accent: "text-amber-300",
  },
  {
    to: "/taper",
    title: "Tapered Fiber",
    icon: Triangle,
    description: "Biconical taper adiabaticity via the Love & Henry criterion. Mode-field evolution, V-number, and transmission along the taper profile.",
    color: "from-emerald-500/30 via-emerald-500/10 to-transparent",
    accent: "text-emerald-300",
  },
];

const platformCards = [
  {
    to: "/devices",
    title: "Device Library",
    icon: Library,
    description: "Store active/passive fibers, FBGs, WDM couplers, and pump sources. Mix custom devices with a built-in catalogue of commercial off-the-shelf components.",
    color: "from-emerald-500/40 via-emerald-500/10 to-transparent",
    accent: "text-emerald-300",
    badge: "New",
    badgeVariant: "success" as const,
  },
  {
    to: "/system",
    title: "Laser System Builder",
    icon: Cpu,
    description: "Assemble a complete fiber laser schematic — fibers, FBGs, couplers, and pump sources — then simulate it and inspect the output with a spectrum analyzer, power meter, and CCD-style M² beam profiler.",
    color: "from-sky-500/40 via-sky-500/10 to-transparent",
    accent: "text-sky-300",
    badge: "New",
    badgeVariant: "success" as const,
  },
  {
    to: "/power-ramp",
    title: "Power Ramp Explorer",
    icon: FlaskConical,
    description: "Sweep pump power for a single fiber and watch SRS, SBS, photodarkening, TMI, and Tm/Er ESA-upconversion approach their limits — a fast diagnostic-level effects explorer built on the same engine as the System Builder.",
    color: "from-rose-500/40 via-rose-500/10 to-transparent",
    accent: "text-rose-300",
    badge: "New",
    badgeVariant: "success" as const,
  },
];

const roadmapItems = [
  {
    title: "Run comparison",
    desc: "Side-by-side overlay of any two simulations from history",
  },
  {
    title: "Report export",
    desc: "Generate a PDF with parameters, plots, and metadata for each simulation",
  },
  {
    title: "Parameter sweep",
    desc: "Run N configurations in one click and compare results on a single chart",
  },
];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SolverCard({ card }: { card: typeof solverCards[0] }) {
  return (
    <Link
      to={card.to}
      className="group block focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-xl"
    >
      <Card className="relative overflow-hidden h-full transition-all duration-300 group-hover:translate-y-[-2px] group-hover:border-primary/40 group-hover:shadow-xl group-hover:shadow-primary/10">
        <div className={`absolute inset-0 bg-gradient-to-br ${card.color} opacity-60 group-hover:opacity-100 transition-opacity pointer-events-none`} />
        <CardHeader className="relative pb-2">
          <div className="flex items-start justify-between">
            <card.icon className={`h-6 w-6 ${card.accent}`} />
            <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-foreground" />
          </div>
          <CardTitle className="mt-3 text-sm">{card.title}</CardTitle>
        </CardHeader>
        <CardContent className="relative pt-0">
          <CardDescription className="text-xs leading-relaxed">{card.description}</CardDescription>
        </CardContent>
      </Card>
    </Link>
  );
}

function PlatformCard({ card }: { card: typeof platformCards[0] }) {
  return (
    <Link
      to={card.to}
      className="group block focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-xl"
    >
      <Card className="relative overflow-hidden h-full transition-all duration-300 group-hover:translate-y-[-2px] group-hover:border-primary/40 group-hover:shadow-xl group-hover:shadow-primary/10">
        <div className={`absolute inset-0 bg-gradient-to-br ${card.color} opacity-70 group-hover:opacity-100 transition-opacity pointer-events-none`} />
        <CardHeader className="relative">
          <div className="flex items-start justify-between">
            <div className="p-2 rounded-lg bg-background/20 backdrop-blur-sm">
              <card.icon className={`h-6 w-6 ${card.accent}`} />
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={card.badgeVariant} className="text-[10px]">{card.badge}</Badge>
              <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-foreground" />
            </div>
          </div>
          <CardTitle className="mt-3">{card.title}</CardTitle>
        </CardHeader>
        <CardContent className="relative">
          <CardDescription className="leading-relaxed">{card.description}</CardDescription>
        </CardContent>
      </Card>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function HomePage() {
  return (
    <div className="container mx-auto py-12 px-6 max-w-6xl">

      {/* Hero */}
      <section className="text-center mb-16">
        <Badge variant="accent" className="mb-4 px-2.5 py-1">
          Lampy · Fiber Laser Studio
        </Badge>
        <h1 className="text-5xl font-semibold tracking-tight mb-5">
          Design fiber laser systems.{" "}
          <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
            Block by block.
          </span>
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed mb-8">
          From individual mode and power solvers to a full system canvas — configure components,
          connect optical ports, and simulate with first-principles physics.
        </p>
        <div className="flex items-center justify-center gap-3">
          <Button asChild size="lg">
            <Link to="/system"><Play className="h-4 w-4 mr-2" />Build a system</Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link to="/devices"><Library className="h-4 w-4 mr-2" />Device library</Link>
          </Button>
        </div>
      </section>

      {/* Platform */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-5">
          <div className="text-[11px] uppercase tracking-widest text-accent font-medium">Platform</div>
          <div className="flex-1 h-px bg-border" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {platformCards.map((card) => (
            <PlatformCard key={card.to} card={card} />
          ))}
        </div>
      </section>

      {/* Solvers */}
      <section className="mb-14">
        <div className="flex items-center gap-3 mb-5">
          <div className="text-[11px] uppercase tracking-widest text-muted-foreground font-medium">Individual solvers</div>
          <div className="flex-1 h-px bg-border" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {solverCards.map((card) => (
            <SolverCard key={card.to} card={card} />
          ))}
        </div>
      </section>

      {/* About */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-14">
        {[
          {
            icon: Layers,
            title: "First-principles physics",
            body: "Rate equations, TMM, BPM, and heat conduction — no black boxes. All models live in the fibersim Python library, usable from scripts and notebooks too.",
          },
          {
            icon: Library,
            title: "Off-the-shelf catalogue",
            body: "Nufern/Corning fibers, standard pump diodes, and WDM couplers included out of the box. Add your own lab-measured devices to the custom library.",
          },
          {
            icon: BookOpen,
            title: "Open core",
            body: "The physics logic lives in the fibersim Python library — fully usable from the CLI. This UI is just one consumer of that engine.",
          },
        ].map((f) => (
          <div key={f.title} className="rounded-xl border border-border bg-card/30 p-5 backdrop-blur-sm">
            <f.icon className="h-4 w-4 text-accent mb-3" />
            <div className="text-sm font-semibold mb-1">{f.title}</div>
            <div className="text-xs text-muted-foreground leading-relaxed">{f.body}</div>
          </div>
        ))}
      </section>

      {/* Roadmap */}
      <section className="rounded-xl border border-border bg-card/30 p-8 backdrop-blur-sm">
        <div className="text-[11px] uppercase tracking-widest text-accent font-medium mb-1">Roadmap</div>
        <h2 className="text-lg font-semibold mb-5">What's next</h2>
        <ul className="space-y-3">
          {roadmapItems.map((item) => (
            <li key={item.title} className="flex items-start gap-3 text-sm">
              <span className="text-accent mt-0.5 shrink-0">→</span>
              <div>
                <span className="text-foreground font-medium">{item.title} </span>
                <span className="text-muted-foreground">— {item.desc}</span>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
