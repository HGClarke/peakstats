import { useEffect } from "react";
import { useNavigate } from "react-router";
import { disconnect, logout, useAthlete } from "@/api/auth";
import { useOverview } from "@/api/overview";
import { useRefreshSync, useSyncStatus } from "@/api/sync";
import { AppShell } from "@/components/app-shell/AppShell";
import { DistancePanel } from "./components/DistancePanel";
import { KpiCards } from "./components/KpiCards";
import { RecentRidesPanel } from "./components/RecentRidesPanel";

function SkeletonPanels() {
  return (
    <div className="p-7" role="status" aria-label="Loading overview">
      <div className="grid grid-cols-4 gap-4 mb-[18px] max-[1024px]:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="bg-surface-card border border-line rounded-2xl p-5">
            <div className="h-[9px] w-[54px] rounded bg-skel mb-4 animate-pkskel" />
            <div className="h-[26px] w-[88px] rounded bg-skel mb-[14px] animate-pkskel" />
            <div className="h-4 w-[46px] rounded-full bg-skel animate-pkskel" />
          </div>
        ))}
      </div>
      <div className="bg-surface-card border border-line rounded-2xl p-5">
        <div className="h-[11px] w-[150px] rounded bg-skel mb-5 animate-pkskel" />
        <div className="h-[180px] rounded-[10px] bg-skel animate-pkskel" />
      </div>
    </div>
  );
}

export default function AppHome() {
  const { data: athlete, error } = useAthlete();
  const { data: status } = useSyncStatus();
  const { data: overview, isLoading } = useOverview();
  const refreshSync = useRefreshSync();
  const navigate = useNavigate();

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
      headerRight={
        <button
          onClick={() => refreshSync.mutate()}
          disabled={!synced || refreshSync.isPending}
          className="h-[38px] px-4 rounded-[10px] bg-strava text-white font-display font-medium text-[13px] cursor-pointer hover:bg-strava-hover disabled:opacity-60 disabled:cursor-not-allowed"
        >
          Refresh from Strava
        </button>
      }
    >
      <div className="h-full overflow-y-auto">
        {isLoading || !overview ? (
          <SkeletonPanels />
        ) : (
          <div className="p-7">
            <KpiCards kpis={overview.kpis} />
            <DistancePanel week={overview.week} />
            <RecentRidesPanel rides={overview.recentRides} />
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
