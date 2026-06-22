import { useNavigate, useParams } from "react-router";
import { logout, useAthlete } from "@/api/auth";
import { useActivityDetail, toPrimaryStats, useActivityStreams } from "@/api/activity-detail";
import { useSyncStatus } from "@/api/sync";
import { useSettings } from "@/app/providers/settings-context";
import { AppShell } from "@/components/app-shell/AppShell";
import RouteHero from "./components/RouteHero";
import { PrimaryStats } from "./components/PrimaryStats";
import { PowerChart } from "./components/PowerChart";
import { ElevationChart } from "./components/ElevationChart";

export default function ActivityDetailPage() {
  const { id } = useParams();
  const activityId = Number(id);
  const { data: athlete } = useAthlete();
  const { data: status } = useSyncStatus();
  const { data: detail, isLoading, error } = useActivityDetail(activityId);
  const { data: streams } = useActivityStreams(activityId);
  const { units } = useSettings();
  const navigate = useNavigate();
  const handleLogout = async () => { await logout(); navigate("/", { replace: true }); };

  return (
    <AppShell
      navActive="Activities"
      athlete={athlete ?? null}
      syncLabel={status?.status === "idle" ? "Up to date" : "Syncing…"}
      onLogout={handleLogout}
      title="Activity"
      subtitle="RIDE DETAIL"
      backTo="/activities"
    >
      <div className="h-full overflow-y-auto p-7">
        {isLoading || !detail ? (
          error ? (
            <div className="text-subtle text-[14px] py-12 text-center">Activity not found.</div>
          ) : (
            <div role="status" aria-label="Loading activity" className="h-[330px] rounded-[18px] bg-skel animate-pkskel" />
          )
        ) : (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-4 mb-4">
              <RouteHero detail={detail} />
              <PrimaryStats stats={toPrimaryStats(detail, units)} />
            </div>
            <PowerChart detail={detail} streams={streams} />
            <ElevationChart detail={detail} streams={streams} />
          </>
        )}
      </div>
    </AppShell>
  );
}
