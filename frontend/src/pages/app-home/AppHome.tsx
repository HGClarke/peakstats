import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { disconnect, logout, useAthlete } from "@/api/auth";
import { useOverview } from "@/api/overview";
import { useSyncStatus } from "@/api/sync";
import { useSettings } from "@/app/providers/settings-context";
import { AppShell } from "@/components/app-shell/AppShell";
import type { Period } from "@/types/overview";
import { HeroPanel } from "./components/HeroPanel";
import { PeriodSelector } from "./components/PeriodSelector";
import { RecentRidesPanel } from "./components/RecentRidesPanel";
import { RideTypesDonut } from "./components/RideTypesDonut";
import { SummaryCard } from "./components/SummaryCard";
import { ZonePanel } from "./components/ZonePanel";
import { ActivityHeatmap } from "./components/ActivityHeatmap";
import { WeeklyGoalRing } from "./components/WeeklyGoalRing";

const VALID_PERIODS: Period[] = ["week", "month", "year"];

function SkeletonPanels() {
  return (
    <div className="p-7" role="status" aria-label="Loading overview">
      <div className="bg-surface-card border border-line rounded-2xl p-6 mb-4">
        <div className="h-[11px] w-[120px] rounded bg-skel mb-5 animate-pkskel" />
        <div className="h-[180px] rounded-[10px] bg-skel animate-pkskel" />
      </div>
      <div className="grid grid-cols-[1.1fr_1fr_1fr] gap-4 mb-4 max-[1024px]:grid-cols-1">
        {[0, 1, 2].map((i) => (
          <div key={i} className="bg-surface-card border border-line rounded-2xl p-5">
            <div className="h-[140px] rounded-[10px] bg-skel animate-pkskel" />
          </div>
        ))}
      </div>
      <div className="bg-surface-card border border-line rounded-2xl p-5">
        <div className="h-[180px] rounded-[10px] bg-skel animate-pkskel" />
      </div>
    </div>
  );
}

export default function AppHome() {
  const { data: athlete, error } = useAthlete();
  const { data: status } = useSyncStatus();
  const { isDark, units } = useSettings();
  const navigate = useNavigate();

  const [period, setPeriod] = useState<Period>("week");
  const seeded = useRef(false);
  useEffect(() => {
    if (!seeded.current && athlete) {
      const dp = athlete.settings.default_period as Period;
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (VALID_PERIODS.includes(dp)) setPeriod(dp);
      seeded.current = true;
    }
  }, [athlete]);

  const { data: overview, isLoading } = useOverview(period);

  useEffect(() => {
    if (error) navigate("/", { replace: true });
  }, [error, navigate]);

  useEffect(() => {
    if (status?.status === "never_synced") navigate("/sync", { replace: true });
  }, [status, navigate]);

  const synced = status?.status === "idle";

  const handleLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  const handleDisconnect = async () => {
    await disconnect();
    navigate("/", { replace: true });
  };

  return (
    <AppShell
      navActive="Overview"
      athlete={athlete}
      syncLabel={synced ? "Up to date" : "Syncing…"}
      onLogout={handleLogout}
      title="Overview"
      subtitle={synced ? "UP TO DATE" : "SYNCING"}
      headerRight={<PeriodSelector value={period} onChange={setPeriod} />}
    >
      <div className="h-full overflow-y-auto">
        {isLoading || !overview ? (
          <SkeletonPanels />
        ) : (
          <div className="p-7">
            <HeroPanel
              headline={overview.headline}
              secondary={overview.secondary}
              trend={overview.trend}
              trendUnit={overview.trendUnit}
              isDark={isDark}
            />
            <div className="grid grid-cols-[1.1fr_1fr_1fr] gap-4 mb-4 max-[1024px]:grid-cols-1">
              <SummaryCard summary={overview.summary} />
              <ZonePanel
                title="Power zones"
                caption={overview.headline.periodLabel}
                kind="power"
                block={overview.powerZones}
              />
              <ZonePanel
                title="Heart-rate zones"
                caption={overview.headline.periodLabel}
                kind="hr"
                block={overview.hrZones}
              />
            </div>
            <div className="grid grid-cols-[auto_1fr] gap-4 mb-4 max-[1024px]:grid-cols-1">
              <ActivityHeatmap view={overview.heatmap} isDark={isDark} units={units} />
              <WeeklyGoalRing goal={overview.goal} />
            </div>
            <div className="grid grid-cols-[1.55fr_1fr] gap-4 max-[1024px]:grid-cols-1">
              <RecentRidesPanel rides={overview.recentRides} />
              <RideTypesDonut data={overview.rideTypes} />
            </div>
          </div>
        )}
        <div className="px-7 pb-10">
          <button
            onClick={handleDisconnect}
            className="font-mono text-[11px] text-faint bg-transparent border-none cursor-pointer hover:text-strava"
          >
            Disconnect Strava
          </button>
        </div>
      </div>
    </AppShell>
  );
}
