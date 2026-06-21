import { AreaChart, Area, XAxis, ResponsiveContainer } from "recharts";
import type { WeekPoint } from "@/types/ride";

export default function WeekChart({
  week,
  isDark,
}: {
  week: WeekPoint[];
  isDark: boolean;
}) {
  return (
    <ResponsiveContainer width="100%" height={140}>
      <AreaChart data={week} margin={{ top: 8, right: 4, bottom: 0, left: 4 }}>
        <defs>
          <linearGradient id="ldChartFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fc4c02" stopOpacity={0.32} />
            <stop offset="100%" stopColor="#fc4c02" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="day"
          axisLine={false}
          tickLine={false}
          tick={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            fill: isDark ? "#6b7280" : "#8a909a",
          }}
        />
        <Area
          type="monotone"
          dataKey="km"
          stroke="#fc4c02"
          strokeWidth={2.5}
          fill="url(#ldChartFill)"
          dot={false}
          activeDot={{ r: 4.5, fill: "#fc4c02", strokeWidth: 2.5, stroke: isDark ? "#13161c" : "#fff" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
