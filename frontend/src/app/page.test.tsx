import { vi } from "vitest";
import { screen } from "@testing-library/react";

import HomePage from "./page";
import { renderWithIntl } from "@/test/intl";

vi.mock("@/i18n/server", async () => {
  const intl = await import("@/test/intl");
  return { getFormatMessage: async () => intl.testFormatMessage() };
});

describe("HomePage (no organisation)", () => {
  it("renders the brand, main navigation and Home heading", async () => {
    renderWithIntl(await HomePage());

    expect(screen.getByRole("link", { name: "Numo9 home" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Home" })).toBeInTheDocument();
  });
});
