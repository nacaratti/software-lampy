import { create } from "zustand";
import { navItems } from "@/lib/navItems";

const STORAGE_KEY = "lampy.nav-prefs.hidden";

interface NavPrefsState {
  hidden: Set<string>;
  toggle: (to: string) => void;
  isVisible: (to: string) => boolean;
  showAll: () => void;
}

function loadHidden(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as string[];
    const validPaths = new Set(navItems.map((n) => n.to));
    return new Set(arr.filter((to) => validPaths.has(to)));
  } catch {
    return new Set();
  }
}

function persist(hidden: Set<string>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(hidden)));
}

/** Which nav "packages" (solver pages) the user has chosen to hide from the
 * sidebar. Hiding is cosmetic only — every route stays reachable via the
 * command palette (⌘K) and this store's own settings popup, so a user can
 * never lock themselves out of a page. */
export const useNavPrefsStore = create<NavPrefsState>((set, get) => ({
  hidden: loadHidden(),
  toggle: (to) => {
    const next = new Set(get().hidden);
    if (next.has(to)) next.delete(to);
    else next.add(to);
    persist(next);
    set({ hidden: next });
  },
  isVisible: (to) => !get().hidden.has(to),
  showAll: () => {
    persist(new Set());
    set({ hidden: new Set() });
  },
}));
