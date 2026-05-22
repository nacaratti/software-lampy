import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import {
  Plus, Trash2, Pencil, X, Check, Search, ChevronRight,
  Activity, Minus, Layers, GitMerge, Zap, BookOpen, Package
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { PageHeader } from "@/components/layout/PageHeader";
import { api } from "@/lib/api";
import type { Device, DeviceType, DeviceCreate } from "@/types/device";
import { defaultParams, deviceTypeLabels } from "@/types/device";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TYPE_ICONS: Record<DeviceType, React.ComponentType<{ className?: string }>> = {
  fiber_active: Activity,
  fiber_passive: Minus,
  fbg: Layers,
  coupler_wdm: GitMerge,
  pump_source: Zap,
};

const TYPE_COLORS: Record<DeviceType, string> = {
  fiber_active: "text-emerald-400",
  fiber_passive: "text-sky-400",
  fbg: "text-violet-400",
  coupler_wdm: "text-amber-400",
  pump_source: "text-rose-400",
};

function TypeIcon({ type, className }: { type: DeviceType; className?: string }) {
  const Icon = TYPE_ICONS[type] ?? Package;
  return <Icon className={className} />;
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") {
    if (Math.abs(v) >= 1e15 || (Math.abs(v) < 1e-3 && v !== 0)) return v.toExponential(3);
    return String(v);
  }
  return String(v);
}

// ---------------------------------------------------------------------------
// Parameter display table
// ---------------------------------------------------------------------------

function ParamTable({ params }: { params: Record<string, unknown> }) {
  const entries = Object.entries(params);
  if (entries.length === 0) return <p className="text-xs text-muted-foreground">No parameters</p>;
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
      {entries.map(([k, v]) => (
        <div key={k} className="contents">
          <span className="text-muted-foreground font-mono truncate py-0.5">{k}</span>
          <span className="font-mono py-0.5 truncate">{formatValue(v)}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Parameter editor: JSON textarea
// ---------------------------------------------------------------------------

function ParamEditor({
  value,
  onChange,
}: {
  value: Record<string, unknown>;
  onChange: (v: Record<string, unknown>) => void;
}) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2));
  const [err, setErr] = useState("");

  function handleChange(t: string) {
    setText(t);
    try {
      const parsed = JSON.parse(t);
      setErr("");
      onChange(parsed);
    } catch {
      setErr("Invalid JSON");
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <textarea
        className="w-full h-52 rounded-md border border-border bg-background font-mono text-xs p-2 resize-y focus:outline-none focus:ring-1 focus:ring-ring"
        value={text}
        onChange={(e) => handleChange(e.target.value)}
        spellCheck={false}
      />
      {err && <p className="text-xs text-destructive">{err}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create dialog
// ---------------------------------------------------------------------------

const ALL_TYPES: DeviceType[] = ["fiber_active", "fiber_passive", "fbg", "coupler_wdm", "pump_source"];

function CreateDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (d: Device) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [deviceType, setDeviceType] = useState<DeviceType>("fiber_active");
  const [manufacturer, setManufacturer] = useState("");
  const [partNumber, setPartNumber] = useState("");
  const [params, setParams] = useState<Record<string, unknown>>(defaultParams.fiber_active);
  const [saving, setSaving] = useState(false);

  function handleTypeChange(t: DeviceType) {
    setDeviceType(t);
    setParams(defaultParams[t]);
  }

  async function handleCreate() {
    if (!name.trim()) { toast.error("Name is required"); return; }
    setSaving(true);
    try {
      const body: DeviceCreate = {
        name: name.trim(),
        description,
        device_type: deviceType,
        category: "custom",
        manufacturer,
        part_number: partNumber,
        parameters: params,
      };
      const created = await api.createDevice(body);
      toast.success("Device created");
      onCreated(created);
      onClose();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to create device");
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    if (open) {
      setName(""); setDescription(""); setDeviceType("fiber_active");
      setManufacturer(""); setPartNumber("");
      setParams(defaultParams.fiber_active);
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New Device</DialogTitle>
          <DialogDescription>Configure a custom device for your library.</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 mt-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <Label>Name *</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Custom Yb-doped fiber" className="mt-1" />
            </div>

            <div className="col-span-2">
              <Label>Device type</Label>
              <Select value={deviceType} onValueChange={(v) => handleTypeChange(v as DeviceType)}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ALL_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>{deviceTypeLabels[t]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>Manufacturer</Label>
              <Input value={manufacturer} onChange={(e) => setManufacturer(e.target.value)} placeholder="Optional" className="mt-1" />
            </div>
            <div>
              <Label>Part number</Label>
              <Input value={partNumber} onChange={(e) => setPartNumber(e.target.value)} placeholder="Optional" className="mt-1" />
            </div>

            <div className="col-span-2">
              <Label>Description</Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional" className="mt-1" />
            </div>

            <div className="col-span-2">
              <Label>Parameters (JSON)</Label>
              <p className="text-[11px] text-muted-foreground mb-1">Pre-filled with template for {deviceTypeLabels[deviceType]}.</p>
              <ParamEditor value={params} onChange={setParams} />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
            <Button onClick={handleCreate} disabled={saving}>
              {saving ? "Saving..." : "Create device"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Edit dialog
// ---------------------------------------------------------------------------

function EditDialog({
  device,
  onClose,
  onSaved,
}: {
  device: Device;
  onClose: () => void;
  onSaved: (d: Device) => void;
}) {
  const [name, setName] = useState(device.name);
  const [description, setDescription] = useState(device.description);
  const [manufacturer, setManufacturer] = useState(device.manufacturer);
  const [partNumber, setPartNumber] = useState(device.part_number);
  const [params, setParams] = useState<Record<string, unknown>>(device.parameters);
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!name.trim()) { toast.error("Name is required"); return; }
    setSaving(true);
    try {
      const updated = await api.updateDevice(device.id, {
        name: name.trim(), description, manufacturer, part_number: partNumber, parameters: params,
      });
      toast.success("Device updated");
      onSaved(updated);
      onClose();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Device</DialogTitle>
          <DialogDescription>{deviceTypeLabels[device.device_type as DeviceType]}</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 mt-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <Label>Name *</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
            </div>
            <div>
              <Label>Manufacturer</Label>
              <Input value={manufacturer} onChange={(e) => setManufacturer(e.target.value)} className="mt-1" />
            </div>
            <div>
              <Label>Part number</Label>
              <Input value={partNumber} onChange={(e) => setPartNumber(e.target.value)} className="mt-1" />
            </div>
            <div className="col-span-2">
              <Label>Description</Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} className="mt-1" />
            </div>
            <div className="col-span-2">
              <Label>Parameters (JSON)</Label>
              <ParamEditor value={params} onChange={setParams} />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : <><Check className="h-3.5 w-3.5 mr-1.5" />Save</>}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Device detail panel
// ---------------------------------------------------------------------------

function DeviceDetail({
  device,
  onEdit,
  onDelete,
  onClose,
}: {
  device: Device;
  onEdit: () => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const isShelf = device.category === "shelf";

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 pb-4 border-b border-border">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`p-2 rounded-lg bg-muted ${TYPE_COLORS[device.device_type as DeviceType]}`}>
            <TypeIcon type={device.device_type as DeviceType} className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-base font-semibold leading-tight truncate">{device.name}</h2>
            <div className="flex items-center gap-2 mt-0.5">
              <Badge variant={isShelf ? "secondary" : "default"} className="text-[10px]">
                {isShelf ? "Catalogue" : "Custom"}
              </Badge>
              <span className="text-xs text-muted-foreground">{deviceTypeLabels[device.device_type as DeviceType]}</span>
            </div>
          </div>
        </div>
        <Button variant="ghost" size="icon" className="shrink-0 h-8 w-8" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1 mt-4">
        <div className="flex flex-col gap-5 pr-1">
          {(device.description || device.manufacturer || device.part_number) && (
            <div className="grid gap-1.5 text-sm">
              {device.description && <p className="text-muted-foreground">{device.description}</p>}
              {device.manufacturer && (
                <p><span className="text-muted-foreground">Manufacturer:</span> {device.manufacturer}</p>
              )}
              {device.part_number && (
                <p><span className="text-muted-foreground">Part number:</span> <span className="font-mono">{device.part_number}</span></p>
              )}
            </div>
          )}

          <div>
            <h3 className="text-xs uppercase tracking-wider text-muted-foreground font-medium mb-2">Parameters</h3>
            <Card className="bg-muted/30">
              <CardContent className="p-3">
                <ParamTable params={device.parameters} />
              </CardContent>
            </Card>
          </div>

          <div className="text-[11px] text-muted-foreground space-y-0.5">
            <p>Created: {new Date(device.created_at).toLocaleString()}</p>
            <p>Updated: {new Date(device.updated_at).toLocaleString()}</p>
          </div>
        </div>
      </ScrollArea>

      {!isShelf && (
        <div className="flex gap-2 pt-4 border-t border-border mt-4">
          <Button variant="outline" size="sm" onClick={onEdit} className="flex-1">
            <Pencil className="h-3.5 w-3.5 mr-1.5" />Edit
          </Button>
          <Button variant="destructive" size="sm" onClick={onDelete}>
            <Trash2 className="h-3.5 w-3.5 mr-1.5" />Delete
          </Button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const CATEGORY_TABS = ["all", "custom", "shelf"] as const;
type CategoryTab = typeof CATEGORY_TABS[number];
const CATEGORY_LABELS: Record<CategoryTab, string> = { all: "All", custom: "Custom", shelf: "Catalogue" };

const TYPE_FILTERS: Array<{ value: string; label: string }> = [
  { value: "all", label: "All types" },
  ...Object.entries(deviceTypeLabels).map(([v, l]) => ({ value: v, label: l })),
];

export function DeviceLibraryPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryTab, setCategoryTab] = useState<CategoryTab>("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Device | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editDevice, setEditDevice] = useState<Device | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listDevices();
      setDevices(data);
    } catch {
      toast.error("Failed to load devices");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = devices.filter((d) => {
    if (categoryTab !== "all" && d.category !== categoryTab) return false;
    if (typeFilter !== "all" && d.device_type !== typeFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        d.name.toLowerCase().includes(q) ||
        d.manufacturer.toLowerCase().includes(q) ||
        d.part_number.toLowerCase().includes(q)
      );
    }
    return true;
  });

  async function handleDelete() {
    if (!selected) return;
    setDeleting(true);
    try {
      await api.deleteDevice(selected.id);
      toast.success("Device deleted");
      setDevices((prev) => prev.filter((d) => d.id !== selected.id));
      setSelected(null);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to delete");
    } finally {
      setDeleting(false);
    }
  }

  function handleCreated(d: Device) {
    setDevices((prev) => [d, ...prev]);
    setSelected(d);
  }

  function handleSaved(d: Device) {
    setDevices((prev) => prev.map((x) => (x.id === d.id ? d : x)));
    setSelected(d);
  }

  return (
    <div className="container mx-auto py-8 max-w-7xl h-full flex flex-col">
      <PageHeader
        eyebrow="Configuration"
        title="Device Library"
        description="Manage fibers, FBGs, couplers, and pump sources. Mix custom devices with the off-the-shelf catalogue."
        actions={
          <Button onClick={() => setShowCreate(true)} size="sm">
            <Plus className="h-4 w-4 mr-1.5" />New device
          </Button>
        }
      />

      <div className="flex gap-4 flex-1 min-h-0">
        {/* ---- Left panel ---- */}
        <div className="flex flex-col w-72 shrink-0 gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search..."
              className="pl-8 h-8 text-sm"
            />
          </div>

          {/* Category tabs */}
          <Tabs value={categoryTab} onValueChange={(v) => setCategoryTab(v as CategoryTab)}>
            <TabsList className="w-full grid grid-cols-3">
              {CATEGORY_TABS.map((t) => (
                <TabsTrigger key={t} value={t} className="text-xs">{CATEGORY_LABELS[t]}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          {/* Type filter */}
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {TYPE_FILTERS.map((f) => (
                <SelectItem key={f.value} value={f.value} className="text-xs">{f.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Device list */}
          <ScrollArea className="flex-1 -mx-1 px-1">
            {loading ? (
              <div className="py-10 text-center text-xs text-muted-foreground">Loading...</div>
            ) : filtered.length === 0 ? (
              <div className="py-10 text-center text-xs text-muted-foreground">
                No devices found.
              </div>
            ) : (
              <ul className="space-y-1">
                {filtered.map((d) => {
                  const isSelected = selected?.id === d.id;
                  return (
                    <li key={d.id}>
                      <button
                        className={`w-full flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors ${
                          isSelected
                            ? "bg-primary/15 text-primary"
                            : "hover:bg-secondary text-foreground"
                        }`}
                        onClick={() => setSelected(d)}
                      >
                        <TypeIcon
                          type={d.device_type as DeviceType}
                          className={`h-4 w-4 shrink-0 ${isSelected ? "text-primary" : TYPE_COLORS[d.device_type as DeviceType]}`}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium truncate">{d.name}</div>
                          <div className="text-[10px] text-muted-foreground truncate">
                            {d.manufacturer || deviceTypeLabels[d.device_type as DeviceType]}
                          </div>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          {d.category === "shelf" && (
                            <BookOpen className="h-3 w-3 text-muted-foreground" />
                          )}
                          <ChevronRight className="h-3 w-3 text-muted-foreground" />
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </ScrollArea>

          <Separator />
          <p className="text-[11px] text-muted-foreground pb-1">
            {filtered.length} of {devices.length} devices
          </p>
        </div>

        {/* ---- Right panel ---- */}
        <div className="flex-1 min-w-0">
          {selected ? (
            <Card className="h-full">
              <CardContent className="p-5 h-full">
                <DeviceDetail
                  device={selected}
                  onEdit={() => setEditDevice(selected)}
                  onDelete={handleDelete}
                  onClose={() => setSelected(null)}
                />
              </CardContent>
            </Card>
          ) : (
            <Card className="h-full flex items-center justify-center">
              <CardContent className="flex flex-col items-center gap-3 text-center p-10">
                <Package className="h-10 w-10 text-muted-foreground/40" />
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Select a device</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Click an item in the list to view its parameters
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={() => setShowCreate(true)}>
                  <Plus className="h-3.5 w-3.5 mr-1.5" />New device
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Create dialog */}
      <CreateDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={handleCreated}
      />

      {/* Edit dialog */}
      {editDevice && (
        <EditDialog
          device={editDevice}
          onClose={() => setEditDevice(null)}
          onSaved={handleSaved}
        />
      )}

      {/* Delete confirmation handled inline with toast — deleting state shown via button */}
      {deleting && (
        <div className="fixed inset-0 z-50 bg-background/60 flex items-center justify-center">
          <Card className="p-6">
            <CardHeader><CardTitle>Deleting...</CardTitle></CardHeader>
          </Card>
        </div>
      )}
    </div>
  );
}
