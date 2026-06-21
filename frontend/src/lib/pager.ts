export type PagerToken =
  | { kind: "page"; page: number; label: string; active: boolean }
  | { kind: "gap" };

/** Build pager tokens for a 1-based `current` page over `totalPages`. */
export function makePager(current: number, totalPages: number): PagerToken[] {
  const out: PagerToken[] = [];
  const add = (p: number) =>
    out.push({ kind: "page", page: p, label: String(p), active: p === current });
  const gap = () => out.push({ kind: "gap" });

  if (totalPages <= 7) {
    for (let p = 1; p <= totalPages; p++) add(p);
    return out;
  }
  add(1);
  let start = Math.max(2, current - 1);
  let end = Math.min(totalPages - 1, current + 1);
  if (current <= 3) { start = 2; end = 4; }
  if (current >= totalPages - 2) { start = totalPages - 3; end = totalPages - 1; }
  if (start > 2) gap();
  for (let p = start; p <= end; p++) add(p);
  if (end < totalPages - 1) gap();
  add(totalPages);
  return out;
}
