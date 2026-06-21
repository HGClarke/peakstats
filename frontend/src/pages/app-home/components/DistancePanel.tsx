import { lazy, Suspense } from "react";
import { useTheme } from "@/app/providers/theme-context";
import type { WeekPoint } from "@/types/ride";

const WeekChart = lazy(() => import("@/components/WeekChart"));

function ChartSkeleton() {
  return <div className="h-[140px] rounded-[10px] bg-skel animate-pkskel" />;
}

/** "Distance over time" card showing the current week's daily distances. */
export function DistancePanel({ week }: { week: WeekPoint[] }) {
  const { isDark } = useTheme();
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-5 mb-[18px]">
      <div className="flex items-center justify-between mb-[10px]">
        <span className="font-display font-medium text-[15px] text-ink">
          Distance over time
        </span>
        <span className="font-mono text-[11px] text-faint">THIS WEEK</span>
      </div>
      <Suspense fallback={<ChartSkeleton />}>
        <WeekChart week={week} isDark={isDark} />
      </Suspense>
    </div>
  );
}
