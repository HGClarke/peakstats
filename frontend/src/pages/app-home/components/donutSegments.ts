import type { RideTypeSlice } from "@/types/overview";

export const R = 80;
const CIRC = 2 * Math.PI * R;

export interface DonutSegment {
  color: string;
  circumference: number;
  /** Visible arc length (user units) — the drawn portion of the ring. */
  length: number;
  dashArray: string;
  dashOffset: number;
  /** Cumulative fraction where this slice starts [0,1) — drives the draw stagger. */
  startFraction: number;
  /** This slice's share of the ring [0,1]. */
  fraction: number;
}

/** Stacked-circle donut segments: each slice is an arc via stroke-dasharray. */
export function donutSegments(items: RideTypeSlice[]): DonutSegment[] {
  let acc = 0;
  return items.map((it) => {
    const length = it.fraction * CIRC;
    const seg: DonutSegment = {
      color: it.color,
      circumference: CIRC,
      length,
      dashArray: `${length} ${CIRC}`,
      dashOffset: acc === 0 ? 0 : -acc * CIRC,
      startFraction: acc,
      fraction: it.fraction,
    };
    acc += it.fraction;
    return seg;
  });
}
