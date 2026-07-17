import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { navItems } from "@/lib/navItems";
import { useNavPrefsStore } from "@/stores/useNavPrefsStore";

interface PackagesDialogProps {
  open: boolean;
  onClose: () => void;
}

/** Lets the user pick which solver "packages" show up in the sidebar.
 * Hidden pages stay reachable via the command palette (⌘K). */
export function PackagesDialog({ open, onClose }: PackagesDialogProps) {
  const hidden = useNavPrefsStore((s) => s.hidden);
  const toggle = useNavPrefsStore((s) => s.toggle);
  const showAll = useNavPrefsStore((s) => s.showAll);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Sidebar packages</DialogTitle>
          <DialogDescription>
            Choose which pages appear in the sidebar. Hidden pages are still one ⌘K search away.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-1">
          {navItems.map((item) => {
            const visible = !hidden.has(item.to);
            return (
              <label
                key={item.to}
                className="flex items-center justify-between gap-3 rounded-md px-3 py-2 hover:bg-accent/30 transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <item.icon className="h-4 w-4 text-muted-foreground shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{item.label}</p>
                    <p className="text-[11px] text-muted-foreground truncate">{item.desc}</p>
                  </div>
                </div>
                <Switch checked={visible} onCheckedChange={() => toggle(item.to)} />
              </label>
            );
          })}
        </div>
        <div className="flex justify-end pt-2">
          <Button variant="outline" size="sm" onClick={showAll} disabled={hidden.size === 0}>
            Show all
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
