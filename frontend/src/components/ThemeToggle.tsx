import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/app/providers/theme-context";

/** Light/dark switch wired to the app ThemeProvider. */
export function ThemeToggle() {
  const { isDark, toggleTheme } = useTheme();
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
