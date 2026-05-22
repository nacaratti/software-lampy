import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useHotkeys } from "react-hotkeys-hook";
import { Toaster } from "sonner";
import { TopBar } from "./TopBar";
import { SidebarNav } from "./SidebarNav";
import { CommandPalette } from "./CommandPalette";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const navigate = useNavigate();

  useHotkeys("mod+k", (e) => {
    e.preventDefault();
    setPaletteOpen((v) => !v);
  });

  useHotkeys("g h", () => navigate("/"));
  useHotkeys("g m", () => navigate("/modes"));
  useHotkeys("g p", () => navigate("/power"));
  useHotkeys("g b", () => navigate("/bpm"));

  return (
    <div className="min-h-screen shell-backdrop flex flex-col">
      <TopBar onOpenCommand={() => setPaletteOpen(true)} />
      <div className="flex flex-1 overflow-hidden">
        <SidebarNav />
        <main className="flex-1 overflow-y-auto animate-fade-in">{children}</main>
      </div>
      <CommandPalette open={paletteOpen} setOpen={setPaletteOpen} />
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
