import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";

export function Nav() {
  return (
    <div className="h-[74px] px-11 flex items-center justify-between border-b border-line-subtle">
      <Logo />
      <div className="flex items-center gap-4">
        <ThemeToggle />
        <span className="font-mono text-[11px] tracking-[0.06em] text-faint border border-line px-3 py-[7px] rounded-[7px]">
          POWERED BY STRAVA
        </span>
      </div>
    </div>
  );
}
