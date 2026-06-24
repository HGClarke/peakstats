import type { Period, SummaryView } from "@/types/overview";

const PERIOD_TITLE: Record<Period, string> = {
  week: "Weekly Highlights",
  month: "Monthly Highlights",
  year: "Year Highlights",
};

function splitVal(s: string): [string, string] {
  if (s === "—") return ["—", ""];
  const last = s.lastIndexOf(" ");
  if (last === -1) return [s, ""];
  return [s.slice(0, last), s.slice(last + 1)];
}

export function SummaryCard({ summary, period }: { summary: SummaryView; period: Period }) {
  const stats: { label: string; value: string; accent?: boolean }[] = [
    { label: "RIDES", value: summary.rides },
    { label: "PERSONAL RECORDS", value: summary.prs, accent: true },
    { label: "TOP AVG SPEED", value: summary.topSpeed },
    { label: "TOP AVG POWER", value: summary.topAvgPower },
    { label: "LONGEST RIDE", value: summary.longestRide },
    { label: "MAX ELEV GAIN", value: summary.maxElev },
  ];
  return (
    <div className="bg-surface-card border border-line rounded-2xl px-[22px] py-5 flex flex-col transition-colors duration-300">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-[7px] h-[7px] rounded-[2px] bg-strava flex-none" />
        <span className="font-display font-semibold text-[14px] text-ink">{PERIOD_TITLE[period]}</span>
      </div>
      <div className="flex-1 grid grid-cols-2 gap-x-[18px] gap-y-4 content-center">
        {stats.map((s) => {
          const [num, unit] = splitVal(s.value);
          return (
            <div key={s.label} className="flex flex-col gap-[5px]">
              <span className="font-mono text-[9px] tracking-[0.1em] text-subtle">{s.label}</span>
              <span className={`font-display font-semibold text-[22px] tracking-[-0.01em] leading-none ${s.accent ? "text-strava" : "text-ink"}`}>
                {num}{unit && <span className="font-mono text-[10px] font-normal text-subtle ml-[3px]">{unit}</span>}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
