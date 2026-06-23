import type { HeadlineKpi, Kpi, TrendPoint } from "@/types/overview";
import { TrendChart } from "./TrendChart";

/** Hero: big headline KPI + 3 secondary KPIs, alongside the period trend chart. */
export function HeroPanel({
  headline, secondary, trend, trendUnit, isDark,
}: {
  headline: HeadlineKpi;
  secondary: Kpi[];
  trend: TrendPoint[];
  trendUnit: string;
  isDark: boolean;
}) {
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-6 mb-4 grid grid-cols-[0.92fr_1.32fr] gap-8 max-[1024px]:grid-cols-1 transition-colors duration-300">
      <div className="flex flex-col">
        <div className="flex items-center gap-[9px] mb-5">
          <span className="w-[7px] h-[7px] rounded-[2px] bg-strava flex-none" />
          <span className="font-mono text-[10px] tracking-[0.16em] text-subtle">
            {headline.label} · {headline.periodLabel}
          </span>
        </div>
        <div className="flex items-end gap-[10px] leading-[0.85]">
          <span className="font-display font-semibold text-[64px] tracking-[-0.035em] text-ink">
            {headline.value}
          </span>
          <span className="font-mono text-[16px] text-muted2 mb-[9px]">{headline.unit}</span>
        </div>
        <div className="mt-4">
          <span
            className={`font-mono text-[11px] px-[11px] py-[5px] rounded-full ${
              headline.deltaPositive ? "text-good bg-good-soft" : "text-bad bg-bad-soft"
            }`}
          >
            {headline.delta} {headline.deltaCaption}
          </span>
        </div>
        <div className="flex-1 min-h-[22px]" />
        <div className="grid grid-cols-3 gap-[14px] border-t border-line pt-[18px]">
          {secondary.map((k) => (
            <div key={k.label} className="flex flex-col gap-[7px]">
              <span className="font-mono text-[9.5px] tracking-[0.12em] text-subtle">{k.label}</span>
              <div className="flex items-baseline gap-1">
                <span className="font-display font-semibold text-[21px] tracking-[-0.01em] leading-none text-ink">
                  {k.value}
                </span>
                {k.unit && <span className="font-mono text-[10px] text-subtle">{k.unit}</span>}
              </div>
              <span className={`font-mono text-[10px] ${k.deltaPositive ? "text-good" : "text-bad"}`}>
                {k.delta}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-col border-l border-line pl-8 min-w-0 max-[1024px]:border-l-0 max-[1024px]:pl-0 max-[1024px]:border-t max-[1024px]:pt-5">
        <div className="flex items-center justify-between mb-4">
          <span className="font-display font-medium text-[14px] text-body">Distance over time</span>
          <span className="font-mono text-[10px] tracking-[0.08em] text-faint">{headline.periodLabel}</span>
        </div>
        <TrendChart points={trend} unit={trendUnit} isDark={isDark} />
      </div>
    </div>
  );
}
