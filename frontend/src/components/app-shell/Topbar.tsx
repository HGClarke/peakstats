import type { ReactNode } from "react";
import { Menu } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";

export function Topbar({
  title,
  subtitle,
  right,
  onMenuClick,
  menuOpen,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  onMenuClick?: () => void;
  menuOpen?: boolean;
}) {
  return (
    <div className="h-[70px] flex-none border-b border-line2 flex items-center justify-between px-8">
      <div className="flex items-center gap-[14px]">
        {onMenuClick ? (
          <button
            type="button"
            aria-label="Open navigation"
            aria-controls="mobile-nav-drawer"
            aria-expanded={menuOpen ?? false}
            onClick={onMenuClick}
            className="w-[38px] h-[38px] flex-none rounded-[10px] bg-surface-inset border border-line text-subtle flex items-center justify-center cursor-pointer transition-colors hover:text-ink hover:border-strava/40 nav:hidden"
          >
            <Menu size={18} aria-hidden />
          </button>
        ) : null}
        <h1 className="font-display font-semibold text-[22px] m-0 tracking-[-0.01em] text-ink">
          {title}
        </h1>
        {subtitle ? (
          <span className="font-mono text-[11px] text-faint">{subtitle}</span>
        ) : null}
      </div>
      <div className="flex items-center gap-[14px]">
        {right}
        <ThemeToggle />
      </div>
    </div>
  );
}
