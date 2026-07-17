import { Moon, Sun, Command as CommandIcon, Github, Menu, Blocks } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useThemeStore } from "@/stores/useThemeStore";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";

interface TopBarProps {
  onOpenCommand: () => void;
  onOpenMobileNav: () => void;
  onOpenPackages: () => void;
}

export function TopBar({ onOpenCommand, onOpenMobileNav, onOpenPackages }: TopBarProps) {
  const { theme, toggle } = useThemeStore();
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-background/60 px-4 sm:px-6 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden -ml-1"
          onClick={onOpenMobileNav}
          aria-label="Open navigation menu"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <div className="relative h-7 w-7">
          <div className="absolute inset-0 rounded-md bg-gradient-to-br from-primary to-accent animate-glow" />
          <div className="absolute inset-[3px] rounded-sm bg-background" />
          <div className="absolute inset-[6px] rounded-[2px] bg-gradient-to-br from-primary to-accent" />
        </div>
        <div className="leading-tight">
          <div className="font-semibold tracking-tight">Lampy</div>
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
            Optical Fiber Studio
          </div>
        </div>
      </div>

      <TooltipProvider delayDuration={150}>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onOpenCommand}
            className="gap-2 font-normal text-muted-foreground"
          >
            <CommandIcon className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Search...</span>
            <kbd className="ml-1 hidden sm:inline rounded bg-secondary px-1.5 py-0.5 text-[10px] font-mono">
              ⌘K
            </kbd>
          </Button>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" onClick={onOpenPackages} aria-label="Choose sidebar packages">
                <Blocks className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Sidebar packages</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle theme">
                {theme === "dark" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Toggle theme</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <a
                href="https://github.com/nacaratti/software-lampy"
                target="_blank"
                rel="noreferrer"
                className="text-muted-foreground hover:text-foreground transition-colors"
                aria-label="Source"
              >
                <Github className="h-4 w-4" />
              </a>
            </TooltipTrigger>
            <TooltipContent>fibersim on GitHub</TooltipContent>
          </Tooltip>
        </div>
      </TooltipProvider>
    </header>
  );
}
