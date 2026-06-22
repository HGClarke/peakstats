import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Pager } from "./Pager";

describe("Pager", () => {
  it("renders nothing for a single page", () => {
    const { container } = render(
      <Pager page={1} totalPages={1} total={5} pageSize={9} onPage={vi.fn()} noun="attempts" />,
    );
    expect(container).toBeEmptyDOMElement();
  });
  it("shows the range with the noun and pages on Next", () => {
    const onPage = vi.fn();
    render(<Pager page={1} totalPages={3} total={20} pageSize={9} onPage={onPage} noun="attempts" />);
    expect(screen.getByText(/of 20 attempts/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(onPage).toHaveBeenCalledWith(2);
  });
});
