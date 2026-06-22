import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SearchInput } from "./SearchInput";

describe("SearchInput", () => {
  it("renders an accessible input and reports changes", () => {
    const onChange = vi.fn();
    render(
      <SearchInput value="" onChange={onChange} placeholder="Search segments…" ariaLabel="Search segments" />,
    );
    const input = screen.getByLabelText("Search segments");
    fireEvent.change(input, { target: { value: "hill" } });
    expect(onChange).toHaveBeenCalledWith("hill");
  });
});
