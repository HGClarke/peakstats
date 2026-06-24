import { fmtDuration } from "@/lib/format";
import type { ZonesBlockDTO } from "@/types/zones";

export interface ZoneRowVM {
  z: string; name: string; range: string; color: string;
  barW: string; dur: string; pctLabel: string;
}

// Reference the raw --zone-N vars (always emitted in :root/.dark), not the
// @theme `--color-zone-N` aliases — Tailwind tree-shakes aliases whose names
// aren't statically visible, and these names are built dynamically.
export function zoneColor(index: number): string {
  return `var(--zone-${Math.min(index + 1, 7)})`;
}

export function toZoneRows(block: ZonesBlockDTO): ZoneRowVM[] {
  return block.buckets.map((b, i) => ({
    z: b.z, name: b.name, range: b.range, color: zoneColor(i),
    barW: `${Math.min(100, b.pct).toFixed(1)}%`,
    dur: fmtDuration(b.seconds),
    pctLabel: `${Math.round(b.pct)}%`,
  }));
}
