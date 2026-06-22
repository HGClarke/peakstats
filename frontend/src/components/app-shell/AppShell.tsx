import { useState, type ReactNode } from "react";
import type { Athlete } from "@/types/athlete";
import { MobileNav } from "./MobileNav";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell({
  navActive, athlete, syncLabel, onLogout, title, subtitle, headerRight, backTo, children,
}: {
  navActive: string;
  athlete: Athlete | null;
  syncLabel: string;
  onLogout: () => void;
  title: string;
  subtitle?: string;
  headerRight?: ReactNode;
  backTo?: string;
  children: ReactNode;
}) {
  const [navOpen, setNavOpen] = useState(false);
  return (
    <div className="relative flex min-h-screen h-screen bg-surface-page text-ink overflow-hidden transition-colors duration-300">
      <Sidebar navActive={navActive} athlete={athlete} syncLabel={syncLabel} onLogout={onLogout} />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          title={title}
          subtitle={subtitle}
          right={headerRight}
          backTo={backTo}
          menuOpen={navOpen}
          onMenuClick={() => setNavOpen(true)}
        />
        <div className="flex-1 min-h-0 relative overflow-hidden">{children}</div>
      </div>
      <MobileNav
        open={navOpen}
        onClose={() => setNavOpen(false)}
        navActive={navActive}
        athlete={athlete}
        syncLabel={syncLabel}
        onLogout={onLogout}
      />
    </div>
  );
}
