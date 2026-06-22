import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";
import type { TrendPoint } from "@/types/segments";

/** Compact recent-time trend line; green when improving, grey otherwise. */
export function SegmentSparkline({ trend }: { trend: TrendPoint[] }) {
  if (trend.length < 2) {
    return <span className="font-mono text-[11px] text-muted5">—</span>;
  }
  const improving = trend[trend.length - 1].t <= trend[0].t; // lower time = faster
  const stroke = improving ? "var(--good)" : "var(--muted2)";
  return (
    <div className="h-[30px] w-full max-w-[120px]" aria-hidden>
      <ResponsiveContainer width="100%" height={30}>
        <LineChart data={trend} margin={{ top: 6, right: 6, bottom: 6, left: 6 }}>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Line
            type="monotone"
            dataKey="t"
            stroke={stroke}
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            isAnimationActive={false}
            dot={false}
            activeDot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
