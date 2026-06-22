import { useNavigate } from "react-router";
import { logout, useAthlete } from "@/api/auth";
import { useSettings } from "@/app/providers/settings-context";
import { useSyncStatus } from "@/api/sync";
import { AppShell } from "@/components/app-shell/AppShell";
import { SegmentedControl } from "./components/SegmentedControl";
import { DisconnectCard } from "./components/DisconnectCard";

const section = "bg-surface-card border border-line rounded-[14px] p-[18px_20px] mb-4";
const heading = "font-display font-medium text-[15px] mb-1";
const sub = "text-[13px] text-subtle mb-4";

export default function SettingsPage() {
  const { data: athlete } = useAthlete();
  const { data: status } = useSyncStatus();
  const { units, theme, setUnits, setTheme } = useSettings();
  const navigate = useNavigate();
  const handleLogout = async () => { await logout(); navigate("/", { replace: true }); };

  return (
    <AppShell
      navActive="Settings"
      athlete={athlete ?? null}
      syncLabel={status?.status === "idle" ? "Up to date" : "Syncing…"}
      onLogout={handleLogout}
      title="Settings"
      subtitle=""
    >
      <div className="h-full overflow-y-auto p-7 max-w-[640px]">
        <div className={section}>
          <div className={heading}>Units</div>
          <div className={sub}>Distance, elevation, and speed display.</div>
          <SegmentedControl
            ariaLabel="Units"
            value={units}
            onChange={setUnits}
            options={[{ label: "Metric", value: "metric" }, { label: "Imperial", value: "imperial" }]}
          />
        </div>

        <div className={section}>
          <div className={heading}>Appearance</div>
          <div className={sub}>Light or dark theme.</div>
          <SegmentedControl
            ariaLabel="Theme"
            value={theme}
            onChange={setTheme}
            options={[{ label: "Dark", value: "dark" }, { label: "Light", value: "light" }]}
          />
        </div>

        <div className={section}>
          <div className={heading}>Account</div>
          <div className="flex items-center gap-3 mb-4">
            {athlete?.avatar_url && (
              <img src={athlete.avatar_url} alt="" aria-hidden className="w-10 h-10 rounded-full object-cover" />
            )}
            <div>
              <div className="text-[14px] text-ink">{athlete?.name ?? "—"}</div>
              <div className="text-[12px] text-subtle">Connected to Strava</div>
            </div>
          </div>
        </div>

        <DisconnectCard />
      </div>
    </AppShell>
  );
}
