export type SaralaModeId = "normal" | "love" | "expert";

export interface SaralaModeConfig {
  id: SaralaModeId;
  label: string;
  symbol: string;
  tagline: string;
  description: string;
  background: string;
  badgeClass: string;
  accentColor: string;
  gradient: string;
}

export const SARALA_MODES: Record<SaralaModeId, SaralaModeConfig> = {
  normal: {
    id: "normal",
    label: "Normal Mode",
    symbol: "✦",
    tagline: "Your everyday AI assistant",
    description: "General knowledge, coding, education, business & more",
    background: "/bark-bg.png",
    badgeClass: "bg-sky-500/20 text-sky-300 border-sky-500/30",
    accentColor: "#38bdf8",
    gradient: "from-sky-400 via-blue-500 to-indigo-600",
  },
  love: {
    id: "love",
    label: "Love Mode",
    symbol: "♡",
    tagline: "Your personal AI companion",
    description: "Conversations, daily life, emotions & personal support",
    background: "/love-mode-1.png",
    badgeClass: "bg-pink-500/20 text-pink-300 border-pink-500/30",
    accentColor: "#ec4899",
    gradient: "from-pink-500 via-rose-500 to-red-500",
  },
  expert: {
    id: "expert",
    label: "Expert Mode",
    symbol: "◈",
    tagline: "Deep work & complex tasks",
    description: "Advanced coding, research, analysis & problem solving",
    // Configurable background (uses love-mode-1.png for now, easily swappable)
    background: "/love-mode-1.png",
    badgeClass: "bg-violet-500/20 text-violet-300 border-violet-500/30",
    accentColor: "#a855f7",
    gradient: "from-indigo-500 via-purple-500 to-violet-600",
  },
};

export const DEFAULT_MODE: SaralaModeId = "normal";

export const ALL_MODES: SaralaModeConfig[] = [
  SARALA_MODES.normal,
  SARALA_MODES.love,
  SARALA_MODES.expert,
];

/**
 * Normalizes any mode string (including legacy IDs) to one of the 3 canonical modes.
 * Backward compatibility migration:
 * - light -> normal
 * - dark -> normal
 * - developer / dev -> expert
 * - dark_blue / dark-blue / vedic -> normal
 * - partner -> love
 * - unknown / empty -> normal
 */
export function normalizeModeId(rawMode: string | null | undefined): SaralaModeId {
  if (!rawMode) return DEFAULT_MODE;
  const clean = rawMode.toLowerCase().trim();

  if (clean === "normal") return "normal";
  if (clean === "love" || clean === "partner") return "love";
  if (clean === "expert" || clean === "developer" || clean === "dev") return "expert";

  // Gracefully migrate legacy modes
  if (
    clean === "light" ||
    clean === "dark" ||
    clean === "dark_blue" ||
    clean === "dark-blue" ||
    clean === "vedic"
  ) {
    return "normal";
  }

  return DEFAULT_MODE;
}

/**
 * Reads the active mode from localStorage, safely migrating legacy values.
 */
export function getSavedMode(): SaralaModeId {
  if (typeof window === "undefined") return DEFAULT_MODE;
  try {
    const raw = localStorage.getItem("sarla_theme_mode") || localStorage.getItem("sarla_mode");
    const normalized = normalizeModeId(raw);
    // If the stored value was an old legacy id, migrate it immediately
    if (raw && raw !== normalized) {
      localStorage.setItem("sarla_theme_mode", normalized);
      localStorage.setItem("sarla_mode", normalized);
    }
    return normalized;
  } catch {
    return DEFAULT_MODE;
  }
}

/**
 * Saves and broadcasts a mode change across the entire application.
 */
export function setSavedMode(mode: SaralaModeId): SaralaModeId {
  const normalized = normalizeModeId(mode);
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem("sarla_theme_mode", normalized);
      localStorage.setItem("sarla_mode", normalized);
      window.dispatchEvent(new CustomEvent("sarla_theme_changed", { detail: { mode: normalized } }));
      window.dispatchEvent(new CustomEvent("sarla_mode_changed", { detail: { mode: normalized } }));
    } catch (e) {
      console.error("Failed to save mode:", e);
    }
  }
  return normalized;
}
