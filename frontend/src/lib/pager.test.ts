import { describe, expect, it } from "vitest";
import { makePager, type PagerToken } from "./pager";

const labels = (t: PagerToken[]) =>
  t.map((x) => (x.kind === "gap" ? "…" : x.label));

describe("makePager", () => {
  it("lists every page when there are 7 or fewer", () => {
    expect(labels(makePager(1, 5))).toEqual(["1", "2", "3", "4", "5"]);
  });
  it("marks the current page active", () => {
    const active = makePager(3, 5).find((t) => t.kind === "page" && t.active);
    expect(active).toMatchObject({ kind: "page", page: 3 });
  });
  it("gaps on the right near the start", () => {
    expect(labels(makePager(2, 12))).toEqual(["1", "2", "3", "4", "…", "12"]);
  });
  it("gaps on the left near the end", () => {
    expect(labels(makePager(11, 12))).toEqual(["1", "…", "9", "10", "11", "12"]);
  });
  it("gaps on both sides in the middle", () => {
    expect(labels(makePager(6, 12))).toEqual(["1", "…", "5", "6", "7", "…", "12"]);
  });
});
