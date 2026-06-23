import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { useUrlQueryState } from "./useUrlQueryState";

function wrapperAt(url: string) {
  return ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[url]}>{children}</MemoryRouter>
  );
}

describe("useUrlQueryState", () => {
  it("reads existing params from the URL", () => {
    const { result } = renderHook(() => useUrlQueryState(), {
      wrapper: wrapperAt("/activities?page=3&q=loop"),
    });
    const [params] = result.current;
    expect(params.get("page")).toBe("3");
    expect(params.get("q")).toBe("loop");
  });

  it("sets and merges params without clobbering existing ones", () => {
    const { result } = renderHook(() => useUrlQueryState(), {
      wrapper: wrapperAt("/activities?q=loop"),
    });
    act(() => result.current[1]({ page: 2 }));
    const [params] = result.current;
    expect(params.get("page")).toBe("2");
    expect(params.get("q")).toBe("loop");
  });

  it("removes a key when the value is null or empty", () => {
    const { result } = renderHook(() => useUrlQueryState(), {
      wrapper: wrapperAt("/activities?page=2&q=loop"),
    });
    act(() => result.current[1]({ page: null, q: "" }));
    const [params] = result.current;
    expect(params.get("page")).toBeNull();
    expect(params.get("q")).toBeNull();
  });
});
