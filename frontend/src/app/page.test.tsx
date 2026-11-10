import { render, screen } from "@testing-library/react";

import HomePage from "./page";

describe("HomePage (no organisation)", () => {
  it("renders the brand, main navigation and Home heading", () => {
    render(<HomePage />);

    expect(screen.getByRole("link", { name: "Numo9 home" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Home" })).toBeInTheDocument();
  });
});
