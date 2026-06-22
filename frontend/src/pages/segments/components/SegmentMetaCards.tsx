// frontend/src/pages/segments/components/SegmentMetaCards.tsx
import { fmtClock } from "@/lib/format";
import type { SegmentDetailDTO } from "@/types/segments";

const card = "bg-surface-card border border-line rounded-[14px] p-[16px_18px]";
const label = "font-mono text-[9.5px] tracking-[0.1em] text-subtle mb-[9px]";
const value = "font-display font-semibold text-[24px] leading-none";

export function SegmentMetaCards({ seg }: { seg: SegmentDetailDTO }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
      <div className={card}>
        <div className={label}>PR TIME</div>
        <div className={`${value} text-strava`}>{fmtClock(seg.pr_time_s)}</div>
      </div>
      <div className={card}>
        <div className={label}>LENGTH</div>
        <div className={value}>{(seg.distance_m / 1000).toFixed(1)} km</div>
      </div>
      <div className={card}>
        <div className={label}>AVG GRADE</div>
        <div className={value}>{seg.avg_grade}%</div>
      </div>
      <div className={card}>
        <div className={label}>ATTEMPTS</div>
        <div className={value}>{seg.attempts}</div>
      </div>
    </div>
  );
}
