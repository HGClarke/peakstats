import { Area, AreaChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { toChartPoints } from "@/api/activity-detail";
import { useSettings } from "@/app/providers/settings-context";
import { elevationLabel } from "@/lib/units";
import type { ActivityDetailDTO, ActivityStreamsDTO } from "@/types/activity-detail";

const card = "bg-surface-card border border-line rounded-[16px] px-[22px] py-5 mb-4";

export function ElevationChart({ detail, streams }: { detail: ActivityDetailDTO; streams?: ActivityStreamsDTO }) {
  const { isDark, units } = useSettings();
  const stroke = isDark ? "#c4cad4" : "#3a414b";
  const pts = toChartPoints(streams?.distance ?? null, streams?.altitude ?? null, units === "imperial" ? "imperial" : "metric");
  return (
    <div className={card}>
      <div className="flex items-center justify-between mb-3.5">
        <span className="font-display font-medium text-[15px] text-ink">Elevation profile</span>
        <span className="font-mono text-[11px] text-faint">+{elevationLabel(detail.elev_gain_m, units)}</span>
      </div>
      {pts.length === 0 ? (
        <div className="h-[140px] flex items-center justify-center text-subtle text-[13px]">No elevation data</div>
      ) : (
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={pts} margin={{ top: 8, right: 4, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="elFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b93a1" stopOpacity={0.28} />
                <stop offset="100%" stopColor="#8b93a1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="x" hide />
            <YAxis hide domain={["dataMin", "dataMax"]} />
            <Area type="monotone" dataKey="y" stroke={stroke} strokeWidth={2} fill="url(#elFill)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
