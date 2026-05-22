/** Lightweight localStorage-backed preset library. */

const STORAGE_PREFIX = "lampy.preset.";

export interface Preset<T = unknown> {
  id: string;
  name: string;
  kind: string;
  config: T;
  createdAt: string;
}

export function savePreset<T>(kind: string, name: string, config: T): Preset<T> {
  const id = `${kind}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
  const preset: Preset<T> = {
    id,
    name,
    kind,
    config,
    createdAt: new Date().toISOString(),
  };
  localStorage.setItem(STORAGE_PREFIX + id, JSON.stringify(preset));
  return preset;
}

export function listPresets<T>(kind?: string): Preset<T>[] {
  const out: Preset<T>[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (!key || !key.startsWith(STORAGE_PREFIX)) continue;
    try {
      const p = JSON.parse(localStorage.getItem(key)!) as Preset<T>;
      if (!kind || p.kind === kind) out.push(p);
    } catch {
      /* ignore */
    }
  }
  out.sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
  return out;
}

export function deletePreset(id: string): void {
  localStorage.removeItem(STORAGE_PREFIX + id);
}

export function getPreset<T>(id: string): Preset<T> | null {
  const raw = localStorage.getItem(STORAGE_PREFIX + id);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}
