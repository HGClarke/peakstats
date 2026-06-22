// frontend/src/pages/segments/components/SegmentCompare.tsx
import { barWidth, compareDelta, toEffortRow } from "@/api/segments";
import { fmtClock } from "@/lib/format";
import type { SegmentEffortDTO } from "@/types/segments";

function Stats({ e }: { e: SegmentEffortDTO }) {
  const r = toEffortRow(e);
  const item = (l: string, v: string) => (
    <div>
      <div className="font-mono text-[9.5px] text-subtle mb-1">{l}</div>
      <div className="font-mono text-[14px] text-body">{v}</div>
    </div>
  );
  return (
    <div className="flex gap-5">
      {item("AVG POWER", r.power)}
      {item("AVG SPEED", r.speed)}
      {item("AVG HR", r.hr)}
    </div>
  );
}

export function SegmentCompare({ best, selected }: { best: SegmentEffortDTO; selected: SegmentEffortDTO }) {
  const delta = compareDelta(best.elapsed_time_s, selected.elapsed_time_s);
  const max = Math.max(best.elapsed_time_s, selected.elapsed_time_s);
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-[22px_24px] mb-4">
      <div className="font-display font-medium text-[16px] mb-5">Compare attempt</div>
      <div className="grid md:grid-cols-2 gap-4 mb-[22px]">
        <div className="bg-surface-inset border border-strava/30 rounded-[14px] p-[18px_20px]">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full bg-strava" />
            <span className="text-[12.5px] font-medium text-ink2">Personal best</span>
          </div>
          <div className="font-display font-semibold text-[34px] leading-none mb-[14px]">{fmtClock(best.elapsed_time_s)}</div>
          <Stats e={best} />
        </div>
        <div className="bg-surface-inset border border-line rounded-[14px] p-[18px_20px]">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full bg-muted2" />
            <span className="text-[12.5px] font-medium text-ink2">Selected attempt</span>
          </div>
          <div className="flex items-baseline gap-3 mb-[14px]">
            <span className="font-display font-semibold text-[34px] leading-none">{fmtClock(selected.elapsed_time_s)}</span>
            <span className={`font-mono text-[12px] px-[9px] py-1 rounded-full ${delta.isBest ? "text-ride-green bg-ride-green-soft" : "text-bad bg-bad-soft"}`}>
              {delta.text}
            </span>
          </div>
          <Stats e={selected} />
        </div>
      </div>
      <div className="flex flex-col gap-3">
        {[{ l: "PERSONAL BEST", e: best, c: "bg-strava" }, { l: "SELECTED", e: selected, c: "bg-muted2" }].map((b) => (
          <div key={b.l} className="flex items-center gap-[14px]">
            <span className="w-24 flex-none font-mono text-[10px] text-subtle">{b.l}</span>
            <div className="flex-1 h-[22px] bg-surface-inset rounded-[6px] overflow-hidden">
              <div className={`h-full rounded-[6px] ${b.c} transition-[width] duration-300`} style={{ width: barWidth(b.e.elapsed_time_s, max) }} />
            </div>
            <span className="w-16 text-right font-mono text-[12px] text-ink">{fmtClock(b.e.elapsed_time_s)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
