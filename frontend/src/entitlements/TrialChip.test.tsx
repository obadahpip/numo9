import { QueryClient } from "@tanstack/react-query";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { entitlementsBody } from "@/test/entitlements";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { EntitlementsProvider } from "./store";
import { TrialChip, trialTone } from "./TrialChip";

/**
 * U-05-T10 — header trial chip + comparison drawer. Acceptance: colour thresholds correct (neutral
 * above 7 days, amber at 7 or fewer, red at 1 or 0) with the days always in words; the drawer
 * compares the packages and marks the trial's; axe passes.
 */

const TRIAL = {
  reason: "trialing",
  status: "trialing",
  trial_ends_at: "2026-11-14T04:59:59+00:00",
  time_zone: "America/Toronto",
};

function render(days: number, viewer = { can_change_package: true }) {
  const body = entitlementsBody({ ...TRIAL, trial_days_left: days, viewer });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const json = (data: unknown) =>
        new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
      if (url.includes("/package-features"))
        return json({
          products: [],
          features: [],
          current_package: "growth",
          packages: [
            { code: "starter", name: "Starter", products: ["accounting"] },
            { code: "growth", name: "Growth", products: ["accounting", "payroll"] },
          ],
        });
      return json(body);
    }),
  );
  return renderWithIntl(
    <EntitlementsProvider
      org="acme"
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <TrialChip />
    </EntitlementsProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it.each([
  [30, "neutral", "Trial — 30 days left"],
  [8, "neutral", "Trial — 8 days left"],
  [7, "warning", "Trial — 7 days left"],
  [2, "warning", "Trial — 2 days left"],
  [1, "danger", "Trial — 1 day left"],
  [0, "danger", "Trial — last day"],
])("%i days: %s, %s", async (days, tone, text) => {
  expect(trialTone(days)).toBe(tone);
  render(days);
  const chip = await screen.findByRole("button", { name: text });
  expect(chip).toHaveAttribute("data-trial-chip", tone);
});

it("opens the package comparison; axe passes", async () => {
  const user = userEvent.setup();
  const { container } = render(12);
  await user.click(await screen.findByRole("button", { name: "Trial — 12 days left" }));
  const drawer = await screen.findByRole("dialog", { name: "Your free trial" });
  expect(drawer).toHaveTextContent("The trial ends on 13 Nov 2026");
  const growth = await within(drawer).findByText("Growth");
  expect(growth.closest("li")).toHaveTextContent("Your trial");
  expect(within(drawer).getByText("Includes Accounting, Payroll")).toBeInTheDocument();
  expect(within(drawer).getByRole("link", { name: "Choose a package" })).toHaveAttribute(
    "href",
    "/o/acme/settings/subscription",
  );
  await expectNoAxeViolations(container);
  await expectNoAxeViolations(drawer);
});

it("is not shown outside a trial", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(entitlementsBody()))),
  );
  renderWithIntl(
    <EntitlementsProvider org="acme" client={new QueryClient()}>
      <TrialChip />
      <p>loaded</p>
    </EntitlementsProvider>,
  );
  await screen.findByText("loaded");
  expect(screen.queryByRole("button", { name: /Trial/ })).toBeNull();
});
