import { LogOut } from "lucide-react";
import { Link } from "react-router";
import { Logo } from "@/components/Logo";
import type { Athlete } from "@/types/athlete";

const NAV_ITEMS: { label: string; to?: string }[] = [
  { label: "Overview", to: "/home" },
  { label: "Activities", to: "/activities" },
  { label: "Segments" },
  { label: "Trends" },
  { label: "Goals" },
];

function initials(name: string): string {
  return name.split(" ").map((p) => p[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();
}

export function Sidebar({
  navActive,
  athlete,
  syncLabel,
  onLogout,
}: {
  navActive: string;
  athlete: Athlete | null;
  syncLabel: string;
  onLogout: () => void;
}) {
  return (
    <div className="w-[236px] flex-none border-r border-line2 flex flex-col p-[22px_16px] bg-surface-sidebar max-[760px]:hidden">
      <div className="px-2 mb-[30px]">
        <Logo />
      </div>
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ label, to }) => {
          const active = label === navActive;
          const className = `flex items-center gap-[11px] px-[11px] py-[9px] rounded-[9px] ${
            active ? "bg-strava-soft" : ""
          }`;
          const inner = (
            <>
              <span
                className={`w-[6px] h-[6px] rounded-full ${active ? "bg-strava" : "bg-muted5"}`}
              />
              <span
                className={`text-[14px] font-medium ${active ? "text-ink2" : "text-subtle"}`}
              >
                {label}
              </span>
            </>
          );
          return to ? (
            <Link key={label} to={to} className={className}>
              {inner}
            </Link>
          ) : (
            <div key={label} className={className}>
              {inner}
            </div>
          );
        })}
      </nav>
      <div className="flex-1" />
      <div className="border-t border-line2 pt-4 flex items-center gap-[11px]">
        {athlete?.avatar_url ? (
          <img
            src={athlete.avatar_url}
            alt=""
            aria-hidden
            className="w-9 h-9 rounded-full object-cover flex-none"
          />
        ) : (
          <div className="w-9 h-9 rounded-full flex-none flex items-center justify-center font-display font-semibold text-[14px] text-white bg-gradient-to-br from-strava to-strava-deep">
            {athlete ? initials(athlete.name) : "--"}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-medium text-ink2 truncate">
            {athlete?.name ?? "…"}
          </div>
          <div className="font-mono text-[10px] text-faint flex items-center gap-[5px]">
            <span className="w-[6px] h-[6px] rounded-full bg-strava" />
            {syncLabel}
          </div>
        </div>
        <button
          title="Log out"
          aria-label="Log out"
          onClick={onLogout}
          className="w-8 h-8 flex-none rounded-[8px] bg-transparent border border-line text-body cursor-pointer flex items-center justify-center transition-colors hover:text-strava hover:border-strava/40"
        >
          <LogOut size={16} aria-hidden />
        </button>
      </div>
    </div>
  );
}
