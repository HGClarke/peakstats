import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { TrendChart } from "./TrendChart";

// Recharts ResponsiveContainer renders nothing at 0x0 in jsdom; force a size.
vi.mock("recharts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("recharts")>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactNode }) => (
      <actual.ResponsiveContainer width={600} height={180}>{children}</actual.ResponsiveContainer>
    ),
  };
});

describe("TrendChart", () => {
  it("renders an area path for the provided points", () => {
    const { container } = render(
      <TrendChart unit="km" isDark points={[{ label: "MON", value: 1 }, { label: "TUE", value: 4 }]} />,
    );
    expect(container.querySelector("svg")).toBeTruthy();
  });
});
