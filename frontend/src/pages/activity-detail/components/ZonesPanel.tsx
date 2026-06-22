import { Link } from "react-router";
import { toZoneRows } from "@/api/activity-detail";
import type { ZonesBlockDTO } from "@/types/activity-detail";

export function ZonesPanel({ title, meta, block }: { title: string; meta: string; block: ZonesBlockDTO }) {
  const rows = toZoneRows(block);
  return (
    <div className="bg-surface-card border border-line rounded-[16px] px-[22px] py-5">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display font-medium text-[15px] text-ink">{title}</span>
        <span className="font-mono text-[11px] text-faint">{meta}</span>
      </div>
      {block.unset ? (
        <div className="text-[13px] text-subtle py-6 text-center">
          Set your FTP and max HR in{" "}
          <Link to="/settings" className="text-strava hover:underline">Settings</Link>{" "}
          to see zones.
        </div>
      ) : (
        <>
          <div className="flex h-[9px] rounded-[5px] overflow-hidden mb-[18px]">
            {block.buckets.map((b, i) => (
              <div key={b.z} style={{ width: `${b.pct}%`, background: `var(--color-zone-${Math.min(i + 1, 7)})` }} />
            ))}
          </div>
          <div className="flex flex-col gap-[11px]">
            {rows.map((r) => (
              <div key={r.z} className="flex items-center gap-3">
                <span className="w-[9px] h-[9px] rounded-[3px] flex-none" style={{ background: r.color }} />
                <div className="w-[142px] flex-none">
                  <div className="text-[12.5px] font-medium text-ink2">{r.z} · {r.name}</div>
                  <div className="font-mono text-[9.5px] text-faint mt-px">{r.range}</div>
                </div>
                <div className="flex-1 h-[13px] bg-track rounded-[4px] overflow-hidden">
                  <div className="h-full rounded-[4px]" style={{ width: r.barW, background: r.color }} />
                </div>
                <span className="font-mono text-[11px] text-ink-hi w-[54px] text-right flex-none">{r.dur}</span>
                <span className="font-mono text-[11px] text-subtle w-[34px] text-right flex-none">{r.pctLabel}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
