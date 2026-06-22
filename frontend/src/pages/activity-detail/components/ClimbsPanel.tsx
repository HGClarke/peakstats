import { toClimbRows } from "@/api/activity-detail";
import type { ClimbDTO } from "@/types/activity-detail";
import type { Units } from "@/lib/units";

const head = "grid grid-cols-[2.2fr_1fr_1fr_1fr_1fr_0.9fr] gap-3";

export function ClimbsPanel({ climbs, units }: { climbs: ClimbDTO[]; units: Units }) {
  const rows = toClimbRows(climbs, units);
  return (
    <div className="bg-surface-card border border-line rounded-[16px] px-[22px] py-5 mb-4 overflow-x-auto">
      <div className="flex items-center justify-between mb-2">
        <span className="font-display font-medium text-[15px] text-ink">Climbs on this ride</span>
        <span className="font-mono text-[11px] text-faint">{rows.length} CATEGORIZED</span>
      </div>
      {rows.length === 0 ? (
        <div className="text-[13px] text-subtle py-6 text-center">No categorized climbs on this ride</div>
      ) : (
        <div className="min-w-[640px]">
          <div className={`${head} px-3 py-[11px] font-mono text-[9.5px] tracking-[0.1em] text-faint border-b border-line-subtle`}>
            <span>CLIMB</span><span>LENGTH</span><span>AVG GRADE</span><span>ELEV GAIN</span><span>VAM</span><span>TIME</span>
          </div>
          {rows.map((r) => (
            <div key={r.name} className={`${head} items-center px-3 py-3.5 rounded-[10px] hover:bg-surface-panel2`}>
              <div className="flex items-center gap-[11px] min-w-0">
                <span
                  className="font-mono text-[9px] font-semibold tracking-[0.04em] px-[7px] py-0.5 rounded-[5px] flex-none border"
                  style={{ color: r.catColor, borderColor: r.catColor }}
                >{r.catLabel}</span>
                <span className="text-[13.5px] font-medium text-ink2 truncate">{r.name}</span>
              </div>
              <span className="font-mono text-[13px] text-ink">{r.length}</span>
              <span className="font-mono text-[13px] font-medium" style={{ color: r.gradeColor }}>{r.grade}</span>
              <span className="font-mono text-[13px] text-ink">{r.gain}</span>
              <span className="font-mono text-[13px] text-body">{r.vam}</span>
              <span className="font-mono text-[13px] text-ink">{r.time}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
