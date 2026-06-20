import { render, screen } from "@testing-library/react";
import App from "./App";

it("renders the landing page", () => {
  render(<App />);
  expect(screen.getByText("peakstats")).toBeInTheDocument();
});
