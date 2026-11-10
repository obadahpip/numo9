import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import OrganisationModulePage from "./page";

const notFound = vi.hoisted(() =>
  vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
);
vi.mock("next/navigation", () => ({ notFound, useRouter: () => ({ push: vi.fn() }) }));

const renderPage = async (org: string, module: string[]) =>
  render(await OrganisationModulePage({ params: Promise.resolve({ org, module }) }));

describe("organisation module placeholder", () => {
  it("renders the module named by the URL inside the shell", async () => {
    await renderPage("acme", ["accounting", "chart-of-accounts"]);

    expect(screen.getByRole("heading", { level: 1, name: "Chart of accounts" })).toBeVisible();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  });

  it.each<[string, string[]]>([
    ["acme", ["no-such-module"]],
    ["acme", ["home", "extra"]],
    ["Bad_Slug", ["home"]],
  ])("org %s, module %o → 404", async (org, module) => {
    await expect(renderPage(org, module)).rejects.toThrow("NEXT_NOT_FOUND");
  });
});
