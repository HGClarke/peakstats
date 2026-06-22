import { Area, AreaChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { toChartPoints } from "@/api/activity-detail";
import { useSettings } from "@/app/providers/settings-context";
import type { ActivityDetailDTO, ActivityStreamsDTO } from "@/types/activity-detail";

const card = "bg-surface-card border border-line rounded-[16px] px-[22px] py-5 mb-4";
const title = "font-display font-medium text-[15px] text-ink";
const meta = "font-mono text-[11px] text-faint";

export function PowerChart({ detail, streams }: { detail: ActivityDetailDTO; streams?: ActivityStreamsDTO }) {
  const { isDark, units } = useSettings();
  const pts = toChartPoints(streams?.distance ?? null, streams?.watts ?? null, units);
  const gridColor = isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.08)";
  return (
    <div className={card}>
      <div className="flex items-center justify-between mb-3.5">
        <span className={title}>Power</span>
        <div className={`flex items-center gap-4 ${meta}`}>
          {detail.avg_power_w !== null && (
            <span className="flex items-center gap-1.5"><span className="w-3.5 h-0.5 bg-strava" />AVG {Math.round(detail.avg_power_w)} W</span>
          )}
          {detail.normalized_power_w !== null && (
            <span className="flex items-center gap-1.5"><span className="w-3.5 border-t-2 border-dashed border-subtle" />NP {Math.round(detail.normalized_power_w)} W</span>
          )}
        </div>
      </div>
      {pts.length === 0 ? (
        <div className="h-[140px] flex items-center justify-center text-subtle text-[13px]">No power data for this ride</div>
      ) : (
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={pts} margin={{ top: 8, right: 4, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="pwFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fc4c02" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#fc4c02" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="x" hide />
            <YAxis hide domain={[0, "dataMax"]} />
            {detail.avg_power_w !== null && (
              <ReferenceLine y={detail.avg_power_w} stroke="#fc4c02" strokeDasharray="4 4" strokeOpacity={0.5} />
            )}
            {detail.normalized_power_w !== null && (
              <ReferenceLine y={detail.normalized_power_w} stroke={gridColor} strokeDasharray="4 4" />
            )}
            <Area type="monotone" dataKey="y" stroke="#fc4c02" strokeWidth={2.2} fill="url(#pwFill)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
