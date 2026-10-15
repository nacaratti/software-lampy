import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(value: number, digits = 4): string {
  if (!isFinite(value)) return String(value);
  if (Math.abs(value) >= 1e4 || (Math.abs(value) > 0 && Math.abs(value) < 1e-3)) {
    return value.toExponential(digits);
  }
  return value.toFixed(digits);
}

/** Platform modifier-key glyph for shortcut hints: "⌘" on Apple, "Ctrl" elsewhere
 * (react-hotkeys-hook's `mod` already maps to the right key; this is just the label). */
export const MOD_KEY: string =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/.test(navigator.platform) ? "⌘" : "Ctrl";
