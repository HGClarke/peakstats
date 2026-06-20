import { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, ResponsiveContainer } from "recharts";
import { Button } from "@/components/ui/button";

const WEEK_DATA = [
  { day: "MON", km: 8.2 },
  { day: "TUE", km: 12.4 },
  { day: "WED", km: 0 },
  { day: "THU", km: 24.1 },
  { day: "FRI", km: 0 },
  { day: "SAT", km: 59.3 },
  { day: "SUN", km: 38.6 },
];

const STAT_TILES = [
  { label: "ELEVATION", value: "1,240", unit: "m" },
  { label: "MOVING TIME", value: "6h 12m", unit: "" },
  { label: "AVG SPEED", value: "24.8", unit: "km/h" },
] as const;

const RECENT_RIDES = [
  { name: "Morning commute", time: "TUE · 07:42", dist: "12.4 km", dot: "#fc4c02" },
  { name: "River loop", time: "SUN · 09:15", dist: "38.7 km", dot: "#1f9d63" },
] as const;

export default function LandingPage() {
  const [isDark, setIsDark] = useState(true);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
  }, [isDark]);

  const toggleTheme = () => setIsDark((d) => !d);

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#f4f3ee] dark:bg-[#0b0d11] transition-colors duration-300 font-[Archivo,sans-serif]">

      {/* Grid background */}
      <div className="ld-grid absolute inset-0 pointer-events-none" />

      {/* Orange glow blob */}
      <div
        className="absolute pointer-events-none rounded-full"
        style={{
          top: -220,
          right: -140,
          width: 640,
          height: 640,
          background: "radial-gradient(circle, rgba(252,76,2,0.18), transparent 68%)",
          filter: "blur(8px)",
        }}
      />

      <div className="relative z-10 max-w-[1240px] mx-auto">

        {/* ── Nav ── */}
        <div className="h-[74px] px-11 flex items-center justify-between border-b border-black/[0.07] dark:border-white/[0.06]">

          {/* Logo */}
          <div className="flex items-center gap-[11px]">
            <div className="w-[30px] h-[30px] rounded-[9px] bg-white dark:bg-[#15181e] border border-black/10 dark:border-white/[0.08] flex items-center justify-center">
              <svg width="20" height="20" viewBox="0 0 100 100" fill="none" aria-hidden>
                <polyline
                  points="16,70 44,34 64,56 84,30"
                  stroke="#fc4c02"
                  strokeWidth="10"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
                <line
                  x1="16" y1="86" x2="84" y2="86"
                  stroke="currentColor"
                  className="text-[#6b7280] dark:text-[#6b7280]"
                  strokeWidth="8"
                  strokeLinecap="round"
                />
              </svg>
            </div>
            <span className="font-display font-semibold text-[18px] text-[#15181d] dark:text-[#f4f5f7] tracking-[-0.01em]">
              peakstats
            </span>
          </div>

          {/* Right: toggle + badge */}
          <div className="flex items-center gap-4">
            <button
              title="Toggle theme"
              onClick={toggleTheme}
              className="w-[38px] h-[38px] rounded-[10px] bg-[#f7f6f1] dark:bg-[#0e1116] border border-black/10 dark:border-white/[0.08] text-[#6b7480] dark:text-[#8b93a1] flex items-center justify-center cursor-pointer transition-colors hover:text-[#15181d] dark:hover:text-[#f4f5f7] hover:border-strava/40"
            >
              {isDark ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <circle cx="12" cy="12" r="4" />
                  <line x1="12" y1="1" x2="12" y2="3" />
                  <line x1="12" y1="21" x2="12" y2="23" />
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                  <line x1="1" y1="12" x2="3" y2="12" />
                  <line x1="21" y1="12" x2="23" y2="12" />
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
              ) : (
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              )}
            </button>
            <span className="font-mono text-[11px] tracking-[0.06em] text-[#8a909a] dark:text-[#6b7280] border border-black/10 dark:border-white/[0.08] px-3 py-[7px] rounded-[7px]">
              POWERED BY STRAVA
            </span>
          </div>
        </div>

        {/* ── Hero ── */}
        <div className="grid grid-cols-1 lg:grid-cols-[1.02fr_1.12fr] gap-14 lg:gap-[56px] items-center px-5 py-12 lg:px-11 lg:pt-[80px] lg:pb-[90px]">

          {/* Left: copy + CTA */}
          <div>
            <div className="font-mono text-[12px] tracking-[0.14em] uppercase text-strava mb-[22px]">
              Ride analytics for everyday riders
            </div>

            <h1 className="font-display font-semibold text-[31px] sm:text-[42px] lg:text-[54px] leading-[1.04] tracking-[-0.02em] text-[#15181d] dark:text-[#f4f5f7] mt-0 mb-[22px]">
              Make sense of<br className="hidden sm:inline" /> every mile you ride.
            </h1>

            <p className="text-[18px] leading-[1.6] text-[#55606e] dark:text-[#9aa3b1] max-w-[455px] mb-[34px]">
              Whether you ride to work, chase weekend miles, or are just getting
              started, Peakstats turns your Strava rides into a clear, beautiful
              picture of your progress. Every ride counts — no racing required.
            </p>

            <div className="mb-[18px]">
              <Button
                asChild
                className="h-14 px-7 bg-strava hover:bg-strava/90 text-white font-display font-semibold text-base rounded-[11px] shadow-[0_8px_24px_rgba(252,76,2,0.32)] hover:shadow-[0_14px_34px_rgba(252,76,2,0.42)] hover:-translate-y-0.5 transition-all duration-150"
              >
                <a href="#">
                  <span className="w-[22px] h-[22px] rounded-[6px] bg-white/[0.92] flex items-center justify-center shrink-0 mr-1">
                    <span className="block w-[2.5px] h-[11px] bg-strava rotate-[38deg] rounded-[2px]" />
                  </span>
                  Connect with Strava
                </a>
              </Button>
            </div>

            <p className="font-mono text-[11.5px] tracking-[0.03em] text-[#8a909a] dark:text-[#6b7280]">
              Read-only access · We never post on your behalf · Disconnect anytime
            </p>
          </div>

          {/* Right: dashboard preview card */}
          <div className="bg-white dark:bg-[#13161c] border border-black/10 dark:border-white/[0.08] rounded-[18px] p-[22px] shadow-[0_24px_60px_rgba(0,0,0,0.10)] dark:shadow-[0_30px_70px_rgba(0,0,0,0.45)] transition-colors duration-300">

            {/* Card header */}
            <div className="flex items-start justify-between mb-[18px]">
              <div>
                <div className="font-mono text-[10.5px] tracking-[0.14em] text-[#6b7480] dark:text-[#8b93a1] mb-2">
                  THIS WEEK
                </div>
                <div className="flex items-baseline gap-[7px]">
                  <span className="font-display font-semibold text-[40px] text-[#15181d] dark:text-[#f4f5f7] tracking-[-0.02em] leading-none">
                    142.6
                  </span>
                  <span className="font-mono text-[13px] text-[#6b7480] dark:text-[#8b93a1]">km</span>
                </div>
              </div>
              <span className="font-mono text-[11px] text-ride-green bg-ride-green/[0.14] px-[11px] py-[6px] rounded-full">
                +18% vs last
              </span>
            </div>

            {/* Area chart */}
            <div className="mb-2">
              <ResponsiveContainer width="100%" height={140}>
                <AreaChart data={WEEK_DATA} margin={{ top: 8, right: 4, bottom: 0, left: 4 }}>
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
            </div>

            {/* Stat tiles */}
            <div className="grid grid-cols-3 gap-[10px] my-4">
              {STAT_TILES.map(({ label, value, unit }) => (
                <div
                  key={label}
                  className="bg-[#f7f6f1] dark:bg-[#0e1116] border border-black/[0.07] dark:border-white/[0.06] rounded-[12px] px-[14px] py-[13px]"
                >
                  <div className="font-mono text-[9.5px] tracking-[0.1em] text-[#6b7480] dark:text-[#8b93a1] mb-[7px]">
                    {label}
                  </div>
                  <div className="font-display font-semibold text-[19px] text-[#15181d] dark:text-[#f4f5f7]">
                    {value}
                    {unit && (
                      <span className="text-[11px] font-normal text-[#6b7480] dark:text-[#8b93a1]"> {unit}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Recent rides */}
            <div className="border-t border-black/[0.07] dark:border-white/[0.06] pt-[14px] flex flex-col gap-3">
              {RECENT_RIDES.map(({ name, time, dist, dot }) => (
                <div key={name} className="flex items-center justify-between">
                  <div className="flex items-center gap-[11px]">
                    <span
                      className="block w-2 h-2 rounded-full shrink-0"
                      style={{ background: dot }}
                    />
                    <div>
                      <div className="text-[13.5px] font-medium text-[#15181d] dark:text-[#f4f5f7]">
                        {name}
                      </div>
                      <div className="font-mono text-[10px] text-[#8a909a] dark:text-[#6b7280]">
                        {time}
                      </div>
                    </div>
                  </div>
                  <span className="font-mono text-[13px] text-[#55606e] dark:text-[#9aa3b1]">
                    {dist}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
