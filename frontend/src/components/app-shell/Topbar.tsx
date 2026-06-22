import type { ReactNode } from "react";
import { ArrowLeft } from "lucide-react";
import { Link } from "react-router";
import { ThemeToggle } from "@/components/ThemeToggle";

export function Topbar({
  title, subtitle, right, backTo,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  backTo?: string;
}) {
  return (
    <div className="h-[70px] flex-none border-b border-line2 flex items-center justify-between px-8 transition-colors duration-300">
      <div className="flex items-center gap-[14px]">
        {backTo ? (
          <Link
            to={backTo}
            aria-label="Back"
            className="w-[34px] h-[34px] rounded-[9px] border border-line-strong text-body flex items-center justify-center hover:text-ink"
          >
            <ArrowLeft size={17} aria-hidden />
          </Link>
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
