import { useEffect, useState } from "react";
import type { GoalView } from "@/types/overview";

const R = 54;
const CIRC = 2 * Math.PI * R;

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  !!window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;

/** Radial progress ring: current-week distance against the athlete's weekly goal. */
export function WeeklyGoalRing({ goal }: { goal: GoalView }) {
  // Fill from empty up to the percentage once, on first mount only. After the
  // entrance the ring tracks the live value instantly (no re-fill on period
  // change); reduced-motion users skip the fill entirely.
  const [filled, setFilled] = useState(prefersReducedMotion);
  const [animating, setAnimating] = useState(false);
  useEffect(() => {
    if (filled) return;
    const id = requestAnimationFrame(() => {
      setAnimating(true);
      setFilled(true);
    });
    return () => cancelAnimationFrame(id);
  }, [filled]);
  const offset = CIRC * (1 - (filled ? goal.pct : 0) / 100);
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-6 flex flex-col items-center justify-center gap-[18px] text-center transition-colors duration-300">
      <div className="flex items-center gap-2 self-start">
        <span className="w-[7px] h-[7px] rounded-[2px] bg-strava flex-none" />
        <span className="font-display font-medium text-[14px] text-ink whitespace-nowrap">Weekly goal</span>
      </div>
      <div className="relative w-[124px] h-[124px] flex-none">
        <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
          <circle cx="60" cy="60" r={R} fill="none" className="stroke-surface-inset" strokeWidth={9} />
          <circle
            cx="60" cy="60" r={R} fill="none" stroke="#fc4c02" strokeWidth={9} strokeLinecap="round"
            strokeDasharray={CIRC} strokeDashoffset={offset}
            className={animating ? "transition-[stroke-dashoffset] duration-[1200ms] ease-out" : undefined}
            onTransitionEnd={() => setAnimating(false)}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display font-semibold text-[24px] leading-none text-ink">{goal.pctLabel}</span>
          <span className="font-mono text-[9px] tracking-[0.08em] text-subtle mt-[3px]">OF GOAL</span>
        </div>
      </div>
      <div className="flex flex-col items-center gap-[6px]">
        <div className="flex items-baseline gap-[5px]">
          <span className="font-display font-semibold text-[22px] text-ink">{goal.doneLabel}</span>
          <span className="font-mono text-[11px] text-subtle">/ {goal.targetLabel} {goal.unit}</span>
        </div>
        <div className="font-mono text-[10.5px] text-faint whitespace-nowrap">
          {goal.remainingLabel} {goal.unit} to go
        </div>
      </div>
    </div>
  );
}
