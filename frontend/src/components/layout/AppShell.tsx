import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useHotkeys } from "react-hotkeys-hook";
import { Toaster } from "sonner";
import { TopBar } from "./TopBar";
import { SidebarNav } from "./SidebarNav";
import { CommandPalette } from "./CommandPalette";
import { MobileNav } from "./MobileNav";
import { PackagesDialog } from "./PackagesDialog";
import { navItems } from "@/lib/navItems";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [packagesOpen, setPackagesOpen] = useState(false);
  const navigate = useNavigate();

  useHotkeys("mod+k", (e) => {
    e.preventDefault();
    setPaletteOpen((v) => !v);
  });

  // "g x" go-to chords. react-hotkeys-hook v4 has no key-sequence support
  // (a "g h" string is parsed as one key and never fires), so the two-key
  // sequence is tracked here: press g, then the page's chord within 1 s.
  useEffect(() => {
    let armedUntil = 0;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName))) return;
      const key = e.key.toLowerCase();
      if (Date.now() < armedUntil) {
        armedUntil = 0;
        const item = navItems.find((n) => n.chord === key);
        if (item) {
          e.preventDefault();
          navigate(item.to);
        }
        return;
      }
      if (key === "g") armedUntil = Date.now() + 1000;
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigate]);

  return (
    <div className="min-h-screen shell-backdrop flex flex-col">
      <TopBar
        onOpenCommand={() => setPaletteOpen(true)}
        onOpenMobileNav={() => setMobileNavOpen(true)}
        onOpenPackages={() => setPackagesOpen(true)}
      />
      <div className="flex flex-1 overflow-hidden">
        <SidebarNav />
        <main className="flex-1 overflow-y-auto animate-fade-in">{children}</main>
      </div>
      <MobileNav open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
      <CommandPalette open={paletteOpen} setOpen={setPaletteOpen} />
      <PackagesDialog open={packagesOpen} onClose={() => setPackagesOpen(false)} />
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: "hsl(var(--card))",
            color: "hsl(var(--card-foreground))",
            border: "1px solid hsl(var(--border))",
          },
        }}
      />
    </div>
  );
}
