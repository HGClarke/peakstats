import { cloneElement } from "react";
import { ActivityCalendar } from "react-activity-calendar";
import { distanceLabel, type Units } from "@/lib/units";
import type { HeatmapView } from "@/types/overview";

// Distance ramp (level 0→4). JS literals per the chart-color exception; the empty
// (level-0) cell differs per theme, the saturated steps are theme-invariant.
const THEME = {
  light: ["#ebedf0", "#fcd9c8", "#fba271", "#fc7032", "#fc4c02"],
  dark: ["#1d2127", "#5a2a13", "#8f3d12", "#c44a0d", "#fc4c02"],
};

/** GitHub-style activity calendar for the year, shaded by distance/day. */
export function ActivityHeatmap({
  view,
  isDark,
  units,
}: {
  view: HeatmapView;
  isDark: boolean;
  units: Units;
}) {
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-6 transition-colors duration-300">
      {/* Shrink-wrap the header to the calendar's width so the active-days
          text aligns to the grid's right edge, not the card's. */}
      <div className="w-fit max-w-full">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-[9px]">
            <span className="w-[7px] h-[7px] rounded-[2px] bg-strava flex-none" />
            <span className="font-display font-medium text-[15px] text-ink">Activity</span>
          </div>
          <span className="font-mono text-[11px] text-faint whitespace-nowrap">
            {view.year} · {view.activeDays} ACTIVE DAYS
          </span>
        </div>
        <ActivityCalendar
        data={view.data}
        maxLevel={4}
        colorScheme={isDark ? "dark" : "light"}
        theme={THEME}
        weekStart={0}
        blockSize={11}
        blockMargin={3}
        fontSize={11}
        showWeekdayLabels={["mon", "wed", "fri"]}
        showMonthLabels
        showTotalCount={false}
        labels={{ legend: { less: "Less", more: "More" } }}
        renderBlock={(block, activity) =>
          cloneElement(
            block,
            {},
            <title>{`${distanceLabel(activity.count, units)} on ${activity.date}`}</title>,
          )
        }
        />
      </div>
    </div>
  );
}
