import { Link } from "react-router";
import { toZoneRows } from "@/api/zones";
import type { ZonesBlockDTO } from "@/types/zones";

type Kind = "power" | "hr";

const PROMPT: Record<Kind, { setting: string; noData: string }> = {
  power: { setting: "Set your FTP", noData: "No power data for this period" },
  hr: { setting: "Set your Max HR", noData: "No heart-rate data for this period" },
};

export function ZonePanel(
  { title, caption, kind, block }: { title: string; caption: string; kind: Kind; block: ZonesBlockDTO },
) {
  const rows = toZoneRows(block);
  const hasData = !block.unset && block.buckets.some((b) => b.seconds > 0);
  const copy = PROMPT[kind];
  return (
    <div className="bg-surface-card border border-line rounded-2xl px-[22px] py-5 flex flex-col transition-colors duration-300">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display font-medium text-[15px] text-ink">{title}</span>
        <span className="font-mono text-[9px] tracking-[0.1em] text-subtle">{caption}</span>
      </div>
      {block.unset ? (
        <div className="text-[13px] text-subtle py-6 text-center">
          {copy.setting} in{" "}
          <Link to="/settings" className="text-strava hover:underline">Settings</Link>{" "}
          to see zones.
        </div>
      ) : !hasData ? (
        <div className="text-[13px] text-subtle py-6 text-center">{copy.noData}</div>
      ) : (
        <div className="flex flex-col gap-[9px] flex-1 justify-center">
          {rows.map((r) => (
            <div key={r.z} className="flex items-center gap-3">
              <span className="font-mono text-[10px] text-subtle w-[18px] flex-none">{r.z}</span>
              <span className="text-[12px] text-body w-[76px] flex-none">{r.name}</span>
              <div className="flex-1 h-[9px] bg-track rounded-[4px] overflow-hidden min-w-0">
                <div className="h-full rounded-[4px]" style={{ width: r.barW, background: r.color }} />
              </div>
              <span className="font-mono text-[10.5px] text-ink w-[30px] text-right flex-none">{r.pctLabel}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
