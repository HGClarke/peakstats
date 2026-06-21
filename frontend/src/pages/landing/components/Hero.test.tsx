import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { stravaLoginUrl } from "@/api/auth";
import { Hero } from "./Hero";

describe("Hero", () => {
  it("links the Connect with Strava CTA to the backend login URL", () => {
    render(<Hero />);
    const cta = screen.getByRole("link", { name: /connect with strava/i });
    expect(cta).toHaveAttribute("href", stravaLoginUrl);
  });
});
