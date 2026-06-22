import { lazy, Suspense } from "react";
import { useSettings } from "@/app/providers/settings-context";
import { useWeeklySummary } from "@/api/weekly-summary";
import { StatTiles } from "./StatTiles";
import { RecentRides } from "./RecentRides";

const WeekChart = lazy(() => import("@/components/WeekChart"));

const CARD_CLASS =
  "bg-surface-card border border-line rounded-[18px] p-[22px] shadow-[0_24px_60px_rgba(0,0,0,0.10)] dark:shadow-[0_30px_70px_rgba(0,0,0,0.45)] transition-colors duration-300";

function ChartSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading chart"
      className="h-[140px] rounded-[12px] bg-surface-inset animate-pulse"
    />
  );
}

function DashboardCardSkeleton() {
  return (
    <div className={CARD_CLASS} role="status" aria-label="Loading dashboard">
      <div className="flex items-start justify-between mb-[18px]">
        <div className="flex flex-col gap-2">
          <div className="h-3 w-20 rounded bg-surface-inset animate-pulse" />
          <div className="h-9 w-28 rounded bg-surface-inset animate-pulse" />
        </div>
        <div className="h-6 w-20 rounded-full bg-surface-inset animate-pulse" />
      </div>
      <ChartSkeleton />
      <div className="grid grid-cols-3 gap-[10px] my-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-[58px] rounded-[12px] bg-surface-inset animate-pulse" />
        ))}
      </div>
      <div className="border-t border-line-subtle pt-[14px] flex flex-col gap-3">
        {[0, 1].map((i) => (
          <div key={i} className="h-8 rounded bg-surface-inset animate-pulse" />
        ))}
      </div>
    </div>
  );
}

export function DashboardPreview() {
  const { isDark } = useSettings();
  const { data } = useWeeklySummary();

  if (!data) {
    return <DashboardCardSkeleton />;
  }

  return (
    <div className={CARD_CLASS}>

      {/* Card header */}
      <div className="flex items-start justify-between mb-[18px]">
        <div>
          <div className="font-mono text-[10.5px] tracking-[0.14em] text-subtle mb-2">
            THIS WEEK
          </div>
          <div className="flex items-baseline gap-[7px]">
            <span className="font-display font-semibold text-[40px] text-ink tracking-[-0.02em] leading-none">
              {data.totalDistanceKm}
            </span>
            <span className="font-mono text-[13px] text-subtle">km</span>
          </div>
        </div>
        <span className="font-mono text-[11px] text-ride-green bg-ride-green/[0.14] px-[11px] py-[6px] rounded-full">
          {data.deltaLabel}
        </span>
      </div>

      {/* Area chart */}
      <div className="mb-2">
        <Suspense fallback={<ChartSkeleton />}>
          <WeekChart week={data.week} isDark={isDark} />
        </Suspense>
      </div>

      <StatTiles stats={data.stats} />
      <RecentRides rides={data.recentRides} />
    </div>
  );
}
