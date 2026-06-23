import type { RideTypeSlice } from "@/types/overview";

export const R = 80;
const CIRC = 2 * Math.PI * R;

export interface DonutSegment {
  color: string;
  circumference: number;
  dashArray: string;
  dashOffset: number;
}

/** Stacked-circle donut segments: each slice is an arc via stroke-dasharray. */
export function donutSegments(items: RideTypeSlice[]): DonutSegment[] {
  let acc = 0;
  return items.map((it) => {
    const seg: DonutSegment = {
      color: it.color,
      circumference: CIRC,
      dashArray: `${it.fraction * CIRC} ${CIRC}`,
      dashOffset: acc === 0 ? 0 : -acc * CIRC,
    };
    acc += it.fraction;
    return seg;
  });
}
