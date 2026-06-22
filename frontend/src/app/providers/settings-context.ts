import { createContext, useContext } from "react";
import type { Units } from "@/lib/units";

export type Theme = "dark" | "light";

export const THEME_STORAGE_KEY = "peakstats-theme";

export type SettingsContextValue = {
  units: Units;
  theme: Theme;
  isDark: boolean;
  setUnits: (units: Units) => void;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
};

export const SettingsContext = createContext<SettingsContextValue | null>(null);

export function useSettings(): SettingsContextValue {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error("useSettings must be used within a SettingsProvider");
  }
  return context;
}
