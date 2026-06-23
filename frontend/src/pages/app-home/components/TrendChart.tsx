import { Area, AreaChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { edgeTickAnchor } from "@/components/edge-tick-anchor";
import type { TrendPoint } from "@/types/overview";

type TickProps = {
  x?: number; y?: number; index?: number; visibleTicksCount?: number;
  payload?: { value?: string | number }; fill?: string;
};

function LabelTick({ x = 0, y = 0, index = 0, visibleTicksCount = 1, payload, fill }: TickProps) {
  return (
    <text x={x} y={y} dy="0.71em" textAnchor={edgeTickAnchor(index, visibleTicksCount)}
      fontFamily="'JetBrains Mono', monospace" fontSize={11} fill={fill}>
      {payload?.value}
    </text>
  );
}

/** Distance trend (area+line) for the selected period. */
export function TrendChart({
  points, unit, isDark,
}: {
  points: TrendPoint[];
  unit: string;
  isDark: boolean;
}) {
  const tick = isDark ? "#6b7280" : "#8a909a";
  // Avoid crowding day-level labels on the month view.
  const interval = points.length > 12 ? Math.floor(points.length / 8) : 0;
  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={points} margin={{ top: 8, right: 6, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fc4c02" stopOpacity={0.28} />
            <stop offset="100%" stopColor="#fc4c02" stopOpacity={0} />
          </linearGradient>
        </defs>
        <YAxis
          width={40} axisLine={false} tickLine={false}
          tick={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, fill: tick }}
          tickFormatter={(v: number) => `${v}`}
          unit={` ${unit}`}
        />
        <XAxis
          dataKey="label" axisLine={false} tickLine={false} interval={interval}
          tick={<LabelTick fill={tick} />}
        />
        <Area
          type="monotone" dataKey="value" stroke="#fc4c02" strokeWidth={2.5}
          fill="url(#trendFill)" dot={false}
          activeDot={{ r: 4.5, fill: "#fc4c02", strokeWidth: 2.5, stroke: isDark ? "#13161c" : "#fff" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
