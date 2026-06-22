import { useNavigate } from "react-router";
import { logout, useAthlete } from "@/api/auth";
import { patchSettings } from "@/api/settings";
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
  const ftp = (athlete?.settings as { ftp_w?: number })?.ftp_w ?? "";
  const hrMax = (athlete?.settings as { hr_max?: number })?.hr_max ?? "";

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
          <div className={heading}>Training zones</div>
          <div className={sub}>FTP and max heart rate power your zone breakdowns.</div>
          <div className="flex gap-4">
            <label className="flex flex-col gap-1 text-[12px] text-subtle">
              FTP (W)
              <input type="number" defaultValue={ftp} aria-label="FTP watts"
                onBlur={(e) => e.target.value && patchSettings({ ftp_w: Number(e.target.value) })}
                className="w-[120px] bg-surface-inset border border-line rounded-[8px] px-3 py-2 text-ink text-[14px]" />
            </label>
            <label className="flex flex-col gap-1 text-[12px] text-subtle">
              Max HR (bpm)
              <input type="number" defaultValue={hrMax} aria-label="Max heart rate"
                onBlur={(e) => e.target.value && patchSettings({ hr_max: Number(e.target.value) })}
                className="w-[120px] bg-surface-inset border border-line rounded-[8px] px-3 py-2 text-ink text-[14px]" />
            </label>
          </div>
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
