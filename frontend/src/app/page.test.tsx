import { render, screen } from "@testing-library/react";

import HomePage from "./page";

describe("HomePage shell placeholder", () => {
  it("renders the brand, main navigation and Home heading", () => {
    render(<HomePage />);

    expect(screen.getByText("Numo9")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Home" })).toBeInTheDocument();
  });
});
