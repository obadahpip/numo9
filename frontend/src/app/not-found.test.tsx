import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import NotFound from "./not-found";

vi.mock("next/navigation", () => ({ usePathname: () => "/settngs-old" }));

describe("custom 404", () => {
  it("explains, offers search and a way Home", () => {
    render(<NotFound />);

    expect(
      screen.getByRole("heading", { level: 1, name: "We can't find that page" }),
    ).toBeVisible();
    expect(screen.getByRole("search")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Home" })).toHaveAttribute("href", "/");
  });
});
