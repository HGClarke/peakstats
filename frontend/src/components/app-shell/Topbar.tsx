import type { ReactNode } from "react";
import { ArrowLeft, Menu } from "lucide-react";
import { useNavigate } from "react-router";
import { ThemeToggle } from "@/components/ThemeToggle";

export function Topbar({
  title,
  subtitle,
  right,
  onMenuClick,
  menuOpen,
  backTo,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  onMenuClick?: () => void;
  menuOpen?: boolean;
  backTo?: string;
}) {
  const navigate = useNavigate();

  // Prefer real history-back so the previous list view (its page/filters live in
  // the URL) is restored exactly. Fall back to `backTo` when there's no in-app
  // history to return to — e.g. a deep link or refresh straight onto this page.
  const handleBack = () => {
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0;
    if (idx > 0) navigate(-1);
    else if (backTo) navigate(backTo);
  };

  return (
    <div className="h-[70px] flex-none border-b border-line2 flex items-center justify-between px-8 transition-colors duration-300">
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
        {backTo ? (
          <button
            type="button"
            onClick={handleBack}
            aria-label="Back"
            className="w-[34px] h-[34px] rounded-[9px] border border-line-strong text-body flex items-center justify-center cursor-pointer hover:text-ink"
          >
            <ArrowLeft size={17} aria-hidden />
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
