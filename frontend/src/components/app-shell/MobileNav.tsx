import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import type { Athlete } from "@/types/athlete";
import { SidebarContent } from "./Sidebar";

// Must match the hamburger's aria-controls in Topbar.tsx.
const DRAWER_ID = "mobile-nav-drawer";

/** Slide-in navigation drawer for screens below the `nav` breakpoint.
 *  Conditionally rendered: returns null when closed. */
export function MobileNav({
  open,
  onClose,
  navActive,
  athlete,
  syncLabel,
  onLogout,
}: {
  open: boolean;
  onClose: () => void;
  navActive: string;
  athlete: Athlete | null;
  syncLabel: string;
  onLogout: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const prevFocused = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      prevFocused?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div id={DRAWER_ID} className="fixed inset-0 z-50 nav:hidden">
      <div
        aria-hidden
        onClick={onClose}
        className="absolute inset-0 bg-overlay animate-pkfadein"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        className="absolute left-0 top-0 bottom-0 w-[236px] border-r border-line2 flex flex-col p-[22px_16px] bg-surface-sidebar animate-pkslidein"
      >
        <div className="flex justify-end mb-1">
          <button
            ref={closeRef}
            type="button"
            aria-label="Close navigation"
            onClick={onClose}
            className="w-8 h-8 flex-none rounded-[8px] bg-transparent border border-line text-body cursor-pointer flex items-center justify-center transition-colors hover:text-strava hover:border-strava/40"
          >
            <X size={16} aria-hidden />
          </button>
        </div>
        <SidebarContent
          navActive={navActive}
          athlete={athlete}
          syncLabel={syncLabel}
          onLogout={onLogout}
          onNavigate={onClose}
        />
      </div>
    </div>
  );
}
