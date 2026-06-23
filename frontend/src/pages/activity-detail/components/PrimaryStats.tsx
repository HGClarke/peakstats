import type { PrimaryStat } from "@/types/activity-detail";

export function PrimaryStats({ stats }: { stats: PrimaryStat[] }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {stats.map((s) => (
        <div key={s.label} className="bg-surface-card border border-line rounded-[14px] px-[17px] py-[15px] flex flex-col justify-center">
          <div className="font-mono text-[9px] tracking-[0.1em] text-subtle mb-2">{s.label}</div>
          <div className="font-display font-semibold text-[23px] leading-none tracking-[-0.01em] text-ink">
            {s.value}
            {s.unit && <span className="text-[12px] text-body font-normal"> {s.unit}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
