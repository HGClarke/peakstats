import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders the peakstats wordmark", () => {
  render(<App />);
  expect(screen.getByText(/peakstats/i)).toBeInTheDocument();
});
