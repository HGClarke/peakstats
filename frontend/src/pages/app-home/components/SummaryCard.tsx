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
    <div className="bg-surface-card border border-line rounded-2xl p-5 mb-4 transition-colors duration-300">
      <div className="grid grid-cols-6 gap-4 max-[1024px]:grid-cols-2">
        {stats.map((s) => (
          <div key={s.label} className="flex flex-col gap-[6px]">
            <span className="font-mono text-[9px] tracking-[0.1em] text-subtle">{s.label}</span>
            <span className={`font-display font-semibold text-[22px] tracking-[-0.01em] leading-none ${s.accent ? "text-strava" : "text-ink"}`}>
              {s.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
