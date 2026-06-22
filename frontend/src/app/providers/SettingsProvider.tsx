import { useEffect, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAthlete } from "@/api/auth";
import { patchSettings } from "@/api/settings";
import type { Units } from "@/lib/units";
import {
  SettingsContext,
  THEME_STORAGE_KEY,
  type Theme,
} from "./settings-context";

function initialTheme(): Theme {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  return stored === "light" || stored === "dark" ? stored : "dark";
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { data: athlete } = useAthlete();

  // Local overrides — null means "defer to server record".
  const [localUnits, setLocalUnits] = useState<Units | null>(null);
  const [localTheme, setLocalTheme] = useState<Theme | null>(null);

  // Effective values: local override takes precedence over the server record.
  const serverUnits =
    athlete?.settings.units === "imperial" || athlete?.settings.units === "metric"
      ? (athlete.settings.units as Units)
      : "metric";
  const serverTheme =
    athlete?.settings.theme === "light" || athlete?.settings.theme === "dark"
      ? (athlete.settings.theme as Theme)
      : initialTheme();

  const units = localUnits ?? serverUnits;
  const theme = localTheme ?? serverTheme;

  // Apply theme to the DOM and mirror it as the pre-auth boot hint.
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const setUnits = (next: Units) => {
    const prev = localUnits;
    setLocalUnits(next);
    patchSettings({ units: next })
      .then((updated) => queryClient.setQueryData(["athlete"], updated))
      .catch(() => setLocalUnits(prev));
  };

  const setTheme = (next: Theme) => {
    const prev = localTheme;
    setLocalTheme(next);
    patchSettings({ theme: next })
      .then((updated) => queryClient.setQueryData(["athlete"], updated))
      .catch(() => setLocalTheme(prev));
  };

  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

  return (
    <SettingsContext.Provider
      value={{ units, theme, isDark: theme === "dark", setUnits, setTheme, toggleTheme }}
    >
      {children}
    </SettingsContext.Provider>
  );
}
