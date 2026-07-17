import { NavLink } from "react-router-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { navItems } from "@/lib/navItems";
import { useNavPrefsStore } from "@/stores/useNavPrefsStore";

interface MobileNavProps {
  open: boolean;
  onClose: () => void;
}

/** Slide-in navigation drawer for viewports below the `lg` breakpoint, where
 * the persistent sidebar (SidebarNav) is hidden. */
export function MobileNav({ open, onClose }: MobileNavProps) {
  const hidden = useNavPrefsStore((s) => s.hidden);
  if (!open) return null;
  const visibleItems = navItems.filter((item) => !hidden.has(item.to));

  return (
    <div className="fixed inset-0 z-40 lg:hidden">
      <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-card border-r border-border flex flex-col shadow-xl">
        <div className="flex items-center justify-between px-4 h-14 border-b border-border">
          <span className="text-sm font-semibold">Navigation</span>
          <button
            onClick={onClose}
            aria-label="Close navigation menu"
            className="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <nav className="flex flex-col gap-1 p-3 overflow-y-auto">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  "group flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors",
                  isActive
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon
                    className={cn(
                      "h-4 w-4 mt-0.5 shrink-0",
                      isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground",
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
      </aside>
    </div>
  );
}
