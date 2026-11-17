import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import { MetricsScreen } from "./MetricsScreen";

/**
 * U-06-T06 — KPI tiles + trend charts with drill-down. Acceptance: a tile's count equals its
 * drill-down list's count; rates without a denominator show a dash; the period switch asks the
 * API for that history.
 */

const METRICS = {
  current: {
    date: "2026-11-18",
    mrr_cents: 1120000,
    active: 2,
    trials: 1,
    conversion_rate: "0.5000",
    churn_rate: null,
    converted: 1,
    trials_ended: 2,
    cancelled: 0,
    active_at_start: 0,
  },
  history: [
    {
      date: "2026-11-17",
      mrr_cents: 1000000,
      active: 2,
      trials: 1,
      conversion_rate: null,
      churn_rate: null,
    },
    {
      date: "2026-11-18",
      mrr_cents: 1120000,
      active: 2,
      trials: 1,
      conversion_rate: "0.5000",
      churn_rate: null,
    },
  ],
};

const ROW = (id: string, name: string) => ({
  id,
  name,
  status: "active",
  is_demo: false,
  package: "basic",
  subscription_status: "active",
  province: "ON",
  created_at: "2026-10-01T12:00:00Z",
});

const calls: string[] = [];

function serve() {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      calls.push(url);
      const body = url.includes("/active/organisations")
        ? {
            count: 2,
            page: 1,
            page_size: 50,
            pages: 1,
            results: [ROW("a", "Alpha"), ROW("b", "Beta")],
          }
        : METRICS;
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

it("shows the tiles, and a tile's drill-down lists as many organisations as it counts", async () => {
  serve();
  const { container } = renderWithIntl(<MetricsScreen />);
  const active = await screen.findByRole("button", {
    name: /Active organisations/,
    pressed: false,
  });
  expect(active).toHaveTextContent("2");
  expect(container.querySelector('[data-tile="mrr"] [data-tile-value]')).toHaveTextContent(
    "$11,200.00",
  );
  expect(container.querySelector('[data-tile="conversion"]')).toHaveTextContent("50%");
  expect(container.querySelector('[data-tile="conversion"]')).toHaveTextContent(
    "1 of 2 trials that ended",
  );
  expect(container.querySelector('[data-tile="churn"] [data-tile-value]')).toHaveTextContent("—");

  await userEvent.click(
    screen.getByRole("button", { name: "Show the organisations: Active organisations" }),
  );
  const drill = await screen.findByRole("region", {
    name: "Active organisations: 2 organisations",
  });
  expect(within(drill).getAllByRole("link")).toHaveLength(2);
  expect(calls.some((url) => url.includes("/metrics/active/organisations"))).toBe(true);
  await expectNoAxeViolations(container);
});

it("switches the chart's metric and period", async () => {
  serve();
  renderWithIntl(<MetricsScreen />);
  await userEvent.click(await screen.findByRole("button", { name: /^Trials/ }));
  expect(screen.getByRole("heading", { name: "Trend: Trials" })).toBeVisible();
  expect(screen.getByRole("img", { name: "Trials by day, last 90 days" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "365 days" }));
  expect(calls.at(-1)).toContain("days=365");
});
