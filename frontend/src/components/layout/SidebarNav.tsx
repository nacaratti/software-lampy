import { NavLink } from "react-router-dom";
import { Waves, Zap, Aperture, Home, History, Grid3X3, Link, Thermometer, Library, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import { useJobsStore } from "@/stores/useJobsStore";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  desc: string;
}

const items: NavItem[] = [
  { to: "/", label: "Home", icon: Home, desc: "Overview & quick starts" },
  { to: "/modes", label: "Fiber Modes Solver", icon: Aperture, desc: "LP modes, fields" },
  { to: "/power", label: "Power & ASE", icon: Zap, desc: "Pumps, signals, ASE" },
  { to: "/bpm", label: "BPM", icon: Waves, desc: "Beam propagation" },
  { to: "/fbg", label: "FBG Solver", icon: Grid3X3, desc: "Bragg gratings, phase mask" },
  { to: "/splicing", label: "Splicing Loss", icon: Link, desc: "Fiber splicing overlap" },
  { to: "/thermal", label: "Thermal Simulator", icon: Thermometer, desc: "Cavity heating & pumps" },
  { to: "/devices", label: "Device Library", icon: Library, desc: "Fibers, FBGs, couplers" },
  { to: "/system", label: "Laser System", icon: Cpu, desc: "Drag-and-drop canvas" },
];

export function SidebarNav() {
  const history = useJobsStore((s) => s.history);
  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-border bg-card/30 backdrop-blur-sm">
      <nav className="flex flex-col gap-1 p-3">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "group flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors",
                isActive
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              )
            }
          >
            {({ isActive }) => (
              <>
                <item.icon
                  className={cn(
                    "h-4 w-4 mt-0.5 shrink-0",
                    isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
                  )}
                />
                <div className="flex-1 leading-tight">
                  <div className="text-sm font-medium">{item.label}</div>
                  <div className="text-[11px] text-muted-foreground">{item.desc}</div>
                </div>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <Separator className="my-2" />

      <div className="px-4 pt-2 pb-1 flex items-center gap-2">
        <History className="h-3.5 w-3.5 text-muted-foreground" />
        <h3 className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">
          History
        </h3>
      </div>

      <ScrollArea className="flex-1 px-2 pb-3">
        {history.length === 0 && (
          <div className="px-3 py-6 text-xs text-muted-foreground text-center">
            No runs yet.
          </div>
        )}
        <ul className="space-y-1">
          {history.map((j) => (
            <li
              key={j.jobId}
              className="rounded-md px-3 py-2 text-xs hover:bg-secondary cursor-default group"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono truncate">{j.label}</span>
                <Badge variant={statusVariant(j.status)} className="text-[10px]">
                  {j.status}
                </Badge>
              </div>
              <div className="text-muted-foreground mt-1 truncate">
                {new Date(j.startedAt).toLocaleTimeString()}
              </div>
            </li>
          ))}
        </ul>
      </ScrollArea>
    </aside>
  );
}

function statusVariant(s: string) {
  switch (s) {
    case "completed":
      return "success" as const;
    case "running":
      return "default" as const;
    case "queued":
      return "secondary" as const;
    case "cancelled":
      return "warning" as const;
    case "error":
      return "danger" as const;
    default:
      return "secondary" as const;
  }
}
