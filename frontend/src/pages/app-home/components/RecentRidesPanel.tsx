import type { DashRide } from "@/types/overview";

/** Recent rides list shown on the Overview, mirroring the dashboard design. */
export function RecentRidesPanel({ rides }: { rides: DashRide[] }) {
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-2 pb-1">
      <div className="flex items-center justify-between px-[14px] pt-3 pb-[10px]">
        <span className="font-display font-medium text-[15px] text-ink">Recent rides</span>
        <span className="font-mono text-[11px] text-faint">LAST {rides.length}</span>
      </div>
      {rides.length === 0 ? (
        <div className="px-[14px] py-8 text-center text-[14px] text-subtle">
          No rides yet.
        </div>
      ) : (
        rides.map((r) => (
          <div
            key={r.id}
            className="flex items-center justify-between px-[14px] py-3 rounded-[11px] hover:bg-surface-inset"
          >
            <div className="flex items-center gap-[13px] min-w-0">
              <span className="w-[9px] h-[9px] rounded-full bg-strava flex-none" />
              <div className="min-w-0">
                <div className="text-[14px] font-medium text-ink truncate">{r.name}</div>
                <div className="font-mono text-[10.5px] text-faint mt-[2px]">{r.meta}</div>
              </div>
            </div>
            <div className="text-right flex-none pl-3">
              <div className="font-display font-semibold text-[15px] text-ink">
                {r.distLabel}
              </div>
              <div className="font-mono text-[10px] text-faint">{r.durLabel}</div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
