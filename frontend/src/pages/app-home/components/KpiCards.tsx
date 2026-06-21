import type { Kpi } from "@/types/overview";

/** The four headline metrics for the current week (distance, time, elevation, speed). */
export function KpiCards({ kpis }: { kpis: Kpi[] }) {
  return (
    <div className="grid grid-cols-4 gap-4 mb-[18px] max-[1024px]:grid-cols-2">
      {kpis.map((k) => (
        <div
          key={k.label}
          className="bg-surface-card border border-line rounded-2xl p-5 transition-transform hover:-translate-y-0.5"
        >
          <div className="font-mono text-[10px] tracking-[0.12em] text-subtle mb-3">
            {k.label}
          </div>
          <div className="flex items-baseline gap-[6px] mb-[10px]">
            <span className="font-display font-semibold text-[30px] leading-none tracking-[-0.02em] text-ink">
              {k.value}
            </span>
            {k.unit && <span className="font-mono text-[12px] text-muted2">{k.unit}</span>}
          </div>
          <span
            className={`inline-block font-mono text-[11px] px-[9px] py-1 rounded-full ${
              k.deltaPositive ? "text-good bg-good-soft" : "text-bad bg-bad-soft"
            }`}
          >
            {k.delta}
          </span>
        </div>
      ))}
    </div>
  );
}
