import { Check } from "lucide-react";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router";
import { logout, useAthlete } from "@/api/auth";
import { useStartSync, useSyncStatus } from "@/api/sync";
import { AppShell } from "@/components/app-shell/AppShell";

const STAGE_DEFS = [
  { label: "Connect your Strava account", start: 0 },
  { label: "Fetch activity history", start: 8 },
  { label: "Process ride metrics", start: 55 },
  { label: "Build your stats", start: 86 },
];

export default function SyncPage() {
  const navigate = useNavigate();
  const { data: athlete } = useAthlete();
  const { data: status } = useSyncStatus();
  const start = useStartSync();
  const started = useRef(false);

  useEffect(() => {
    if (!started.current) {
      started.current = true;
      start.mutate();
    }
  }, [start]);

  const pct = status?.progress ?? 0;
  const synced = status?.synced ?? 0;
  const state = status?.status ?? "never_synced";
  const isError = state === "error";
  const isDone = state === "idle" && synced > 0;
  const isEmpty = state === "idle" && synced === 0;
  const isSyncing = !isError && !isDone && !isEmpty;

  const activeIdx = isDone
    ? STAGE_DEFS.length
    : STAGE_DEFS.reduce((acc, s, i) => (pct >= s.start ? i : acc), 0);

  const handleLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  return (
    <AppShell
      navActive="Overview"
      athlete={athlete}
      syncLabel={isDone ? "Up to date" : isEmpty ? "No rides yet" : "Syncing…"}
      onLogout={handleLogout}
      title="Setting up your dashboard"
      subtitle="FIRST SYNC"
    >
      {/* blurred skeleton backdrop */}
      <div className="absolute inset-0 p-7 blur-[1.5px] opacity-60 pointer-events-none">
        <div className="grid grid-cols-4 gap-4 mb-[18px]">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="bg-surface-card border border-line rounded-2xl p-5 transition-colors duration-300">
              <div className="h-[9px] w-[54px] rounded bg-skel mb-4 animate-pkskel" />
              <div className="h-[26px] w-[88px] rounded bg-skel mb-[14px] animate-pkskel" />
              <div className="h-4 w-[46px] rounded-full bg-skel animate-pkskel" />
            </div>
          ))}
        </div>
        <div className="bg-surface-card border border-line rounded-2xl p-5 mb-[18px] transition-colors duration-300">
          <div className="h-[11px] w-[150px] rounded bg-skel mb-5 animate-pkskel" />
          <div className="h-[180px] rounded-[10px] bg-skel animate-pkskel" />
        </div>
      </div>

      {/* overlay card */}
      <div className="absolute inset-0 bg-overlay flex items-center justify-center p-6 transition-colors duration-300">
        <div className="w-[480px] max-w-full bg-surface-card border border-line-strong rounded-[20px] p-[32px_32px_30px] shadow-[0_30px_80px_rgba(0,0,0,0.45)] transition-colors duration-300">
          <div className="flex items-center gap-[11px] mb-6">
            <div className="w-[30px] h-[30px] rounded-[8px] bg-strava flex items-center justify-center flex-none">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="#fff" aria-hidden>
                <path d="M8.6 0 3.2 10.6h3.2L8.6 6.2l2.2 4.4h3.2L8.6 0z" />
                <path d="M13.6 10.6 12 13.8l1.6 3.2 3.2-6.4h-3.2z" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[13.5px] font-medium text-ink2">Connected to Strava</div>
              <div className="font-mono text-[10.5px] text-faint">
                {athlete?.name ?? "athlete"} · authorized
              </div>
            </div>
            <span className="flex items-center gap-[5px] font-mono text-[10px] text-good bg-good-soft px-[10px] py-[5px] rounded-full">
              <Check size={11} aria-hidden /> LINKED
            </span>
          </div>

          <div className="font-display font-semibold text-[21px] tracking-[-0.01em] mb-[6px] text-ink">
            {isEmpty ? "No rides found" : isDone ? "You're all set" : "Importing your rides"}
          </div>
          <div className="text-[13.5px] leading-[1.55] text-body mb-6">
            {isEmpty
              ? "Your Strava account is linked, but there's nothing to import yet."
              : isDone
                ? `We imported ${synced} activities and crunched your stats. Your dashboard is ready.`
                : "Hang tight while we pull your full ride history from Strava and build your analytics. This usually takes under a minute."}
          </div>

          {isEmpty ? (
            <div className="flex gap-[10px]">
              <button
                onClick={() => start.mutate()}
                className="flex-1 h-[46px] rounded-[11px] border-none bg-strava text-white font-display font-semibold text-[14px] cursor-pointer hover:bg-strava-hover"
              >
                Refresh from Strava
              </button>
              <button
                onClick={() => navigate("/home")}
                className="flex-none px-[18px] h-[46px] rounded-[11px] border border-line-strong bg-transparent text-ink2 font-display font-medium text-[14px] cursor-pointer hover:border-strava/40"
              >
                Skip
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-baseline justify-between mb-[11px]">
                <div className="flex items-baseline gap-2">
                  <span className="font-display font-semibold text-[34px] leading-none tracking-[-0.02em] text-ink">
                    {Math.round(pct)}
                  </span>
                  <span className="font-mono text-[12px] text-muted2">%</span>
                </div>
                <span className="font-mono text-[11.5px] text-subtle">
                  {synced} activities
                </span>
              </div>

              <div className="h-[10px] rounded-full bg-track overflow-hidden relative mb-[26px]">
                <div
                  className="h-full bg-gradient-to-r from-strava to-strava-light rounded-full relative overflow-hidden transition-[width] duration-200"
                  style={{ width: `${pct}%` }}
                >
                  {isSyncing ? (
                    <div className="absolute top-0 left-0 h-full w-[60px] bg-gradient-to-r from-transparent via-white/45 to-transparent animate-pkshimmer" />
                  ) : null}
                </div>
              </div>

              <div className="flex flex-col gap-[3px] mb-[26px]">
                {STAGE_DEFS.map((stage, i) => {
                  const done = isDone || i < activeIdx;
                  const active = !isDone && i === activeIdx;
                  return (
                    <div key={stage.label} className="flex items-center gap-3 px-1 py-2">
                      <span className="w-[22px] h-[22px] flex-none flex items-center justify-center">
                        {done ? (
                          <span className="w-[22px] h-[22px] rounded-full bg-strava flex items-center justify-center">
                            <Check size={12} color="#fff" aria-hidden />
                          </span>
                        ) : active ? (
                          <span className="w-[18px] h-[18px] rounded-full border-[2.5px] border-strava-soft border-t-strava animate-pkspin" />
                        ) : (
                          <span className="w-4 h-4 rounded-full border-2 border-track" />
                        )}
                      </span>
                      <span
                        className={`flex-1 text-[13.5px] font-medium ${
                          done || active ? "text-ink2" : "text-subtle"
                        }`}
                      >
                        {stage.label}
                      </span>
                      <span className="font-mono text-[10.5px] text-faint">
                        {done ? "done" : active ? "in progress" : "waiting"}
                      </span>
                    </div>
                  );
                })}
              </div>

              {isError ? (
                <button
                  onClick={() => start.mutate()}
                  className="w-full h-[46px] rounded-[11px] border-none bg-strava text-white font-display font-semibold text-[14.5px] cursor-pointer hover:bg-strava-hover"
                >
                  Sync failed — retry
                </button>
              ) : isDone ? (
                <button
                  onClick={() => navigate("/home")}
                  className="w-full h-[46px] rounded-[11px] border-none bg-strava text-white font-display font-semibold text-[14.5px] cursor-pointer flex items-center justify-center gap-2 hover:bg-strava-hover animate-pkrise"
                >
                  Go to dashboard →
                </button>
              ) : null}
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
