import type { SummaryView } from "@/types/overview";

/** Records summary for the selected period. */
export function SummaryCard({ summary }: { summary: SummaryView }) {
  const stats: { label: string; value: string; accent?: boolean }[] = [
    { label: "RIDES", value: summary.rides },
    { label: "PERSONAL RECORDS", value: summary.prs, accent: true },
    { label: "TOP AVG SPEED", value: summary.topSpeed },
    { label: "TOP AVG POWER", value: summary.topAvgPower },
    { label: "LONGEST RIDE", value: summary.longestRide },
    { label: "MAX ELEV GAIN", value: summary.maxElev },
  ];
  return (
    <div className="bg-surface-card border border-line rounded-2xl px-[22px] py-5 transition-colors duration-300">
      <div className="flex flex-col gap-[14px]">
        {stats.map((s) => (
          <div key={s.label} className="flex items-center justify-between gap-3">
            <span className="font-mono text-[9px] tracking-[0.1em] text-subtle">{s.label}</span>
            <span className={`font-display font-semibold text-[18px] tracking-[-0.01em] leading-none whitespace-nowrap ${s.accent ? "text-strava" : "text-ink"}`}>
              {s.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
