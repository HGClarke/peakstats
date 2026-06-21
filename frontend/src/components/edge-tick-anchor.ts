/**
 * Horizontal anchor for an x-axis tick. The first and last labels sit at the
 * plot edges; anchoring them inward (start / end) instead of "middle" keeps the
 * area chart full-bleed while stopping the edge labels (e.g. "MON") from
 * clipping off the side of the SVG.
 */
export function edgeTickAnchor(
  index: number,
  count: number,
): "start" | "middle" | "end" {
  if (index === 0) return "start";
  if (index === count - 1) return "end";
  return "middle";
}
