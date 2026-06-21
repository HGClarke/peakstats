import type { RecentRide } from "@/types/ride";

export function RecentRides({ rides }: { rides: RecentRide[] }) {
  return (
    <div className="border-t border-line-subtle pt-[14px] flex flex-col gap-3">
      {rides.map(({ id, name, timeLabel, distanceLabel, markerColor }) => (
        <div key={id} className="flex items-center justify-between">
          <div className="flex items-center gap-[11px]">
            <span
              className="block w-2 h-2 rounded-full shrink-0"
              style={{ background: markerColor }}
            />
            <div>
              <div className="text-[13.5px] font-medium text-ink">
                {name}
              </div>
              <div className="font-mono text-[10px] text-faint">
                {timeLabel}
              </div>
            </div>
          </div>
          <span className="font-mono text-[13px] text-body">
            {distanceLabel}
          </span>
        </div>
      ))}
    </div>
  );
}
