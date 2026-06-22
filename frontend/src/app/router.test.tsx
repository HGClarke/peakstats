import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { createQueryWrapper } from "@/test/providers";
import { routes } from "./router";

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(<RouterProvider router={router} />, {
    wrapper: createQueryWrapper(),
  });
}

beforeEach(() => {
  document.documentElement.classList.remove("dark", "light");
  localStorage.clear();
});

it("renders the landing page at /", async () => {
  renderAt("/");
  expect(await screen.findByText("peakstats")).toBeInTheDocument();
});

it("renders a not-found page for unknown routes", async () => {
  renderAt("/does-not-exist");
  expect(await screen.findByText(/page not found/i)).toBeInTheDocument();
});

it("the not-found page links back home", async () => {
  renderAt("/does-not-exist");
  const home = await screen.findByRole("link", { name: /back to home/i });
  expect(home).toHaveAttribute("href", "/");
});

it("renders the activity detail page at /activities/:id", async () => {
  renderAt("/activities/5");
  // Should mount ActivityDetailPage, not NotFoundPage
  expect(screen.queryByText(/page not found/i)).not.toBeInTheDocument();
});
