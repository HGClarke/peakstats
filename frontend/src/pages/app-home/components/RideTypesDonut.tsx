import { useEffect, useState } from "react";
import type { RideTypesView } from "@/types/overview";
import { donutSegments, R } from "./donutSegments";

/** Total time for the ring to trace fully around, at constant angular speed. */
const SWEEP_MS = 1100;

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  !!window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;

/** Ride-type breakdown: donut + legend. */
export function RideTypesDonut({ data }: { data: RideTypesView }) {
  const segments = donutSegments(data.items);
  // Start undrawn (each arc at length 0), then reveal on mount so the CSS
  // transition runs; reduced-motion users get the final state immediately.
  const [drawn, setDrawn] = useState(prefersReducedMotion);
  useEffect(() => {
    if (drawn) return;
    const id = requestAnimationFrame(() => setDrawn(true));
    return () => cancelAnimationFrame(id);
  }, [drawn]);
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-5 flex flex-col transition-colors duration-300">
      <div className="flex items-center justify-between mb-5">
        <span className="font-display font-medium text-[15px] text-ink">Ride types</span>
        <span className="font-mono text-[11px] text-faint">{data.total} TOTAL</span>
      </div>
      <div className="flex items-center gap-5">
        <div className="flex-1 flex flex-col gap-3 min-w-0">
          {data.items.map((it) => (
            <div key={it.type} className="flex items-center gap-[9px]">
              <span className="w-[9px] h-[9px] rounded-[2px] flex-none" style={{ background: it.color }} />
              <span className="flex-1 text-[13px] text-body truncate">{it.label}</span>
              <span className="font-mono text-[11px] text-subtle">{it.pct}</span>
            </div>
          ))}
        </div>
        <div className="flex-none w-[140px] h-[140px]">
          <svg viewBox="0 0 200 200" className="w-full h-full -rotate-90">
            {segments.map((s, i) => (
              <circle
                key={i} cx="100" cy="100" r={R} fill="none" stroke={s.color} strokeWidth={26}
                strokeDasharray={drawn ? s.dashArray : `0 ${s.circumference}`}
                strokeDashoffset={s.dashOffset}
                style={{
                  // Each slice draws over its own share of the sweep, starting
                  // exactly when the previous one finishes → one connected trace.
                  transition: `stroke-dasharray ${s.fraction * SWEEP_MS}ms linear ${s.startFraction * SWEEP_MS}ms`,
                }}
              />
            ))}
          </svg>
        </div>
      </div>
    </div>
  );
}
