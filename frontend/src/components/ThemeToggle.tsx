import { Moon, Sun } from "lucide-react";
import { useSettings } from "@/app/providers/settings-context";

/** Light/dark switch wired to the app SettingsProvider (persists on toggle). */
export function ThemeToggle() {
  const { isDark, toggleTheme } = useSettings();
  return (
    <button
      title="Toggle theme"
      onClick={toggleTheme}
      className="w-[38px] h-[38px] rounded-[10px] bg-surface-inset border border-line text-subtle flex items-center justify-center cursor-pointer transition-colors hover:text-ink hover:border-strava/40"
    >
      {isDark ? (
        <Sun size={18} aria-hidden />
      ) : (
        <Moon size={17} aria-hidden />
      )}
    </button>
  );
}
