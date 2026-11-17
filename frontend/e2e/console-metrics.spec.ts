import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * U-06-T06 — console KPI tiles + trend charts with drill-down (`/console`). Acceptance: a tile's
 * count equals its drill-down list's count (fixtures in the API's shape — backend/numo9/platform/
 * metrics.py, tested against the real service in backend/tests/test_platform_metrics_api.py).
 */
const API = "**/api/v1/platform/metrics";

const point = (date: string, mrr: number, active: number, trials: number) => ({
  date,
  mrr_cents: mrr,
  active,
  trials,
  conversion_rate: "0.5000",
  churn_rate: "0.1000",
});

const row = (index: number) => ({
  id: `0000000${index}-0000-4000-8000-000000000000`,
  name: `Client ${index}`,
  status: "active",
  is_demo: false,
  package: "basic",
  subscription_status: "active",
  province: "ON",
  created_at: "2026-10-01T12:00:00Z",
});

async function mockMetrics(page: Page) {
  await mockCsrf(page);
  await page.route(`${API}?*`, (r) =>
    r.fulfill({
      json: {
        current: {
          ...point("2026-11-18", 870000, 3, 2),
          converted: 1,
          trials_ended: 2,
          cancelled: 1,
          active_at_start: 10,
        },
        history: [
          point("2026-11-16", 800000, 3, 1),
          point("2026-11-17", 840000, 3, 2),
          point("2026-11-18", 870000, 3, 2),
        ],
      },
    }),
  );
  await page.route(`${API}/active/organisations*`, (r) =>
    r.fulfill({
      json: { count: 3, page: 1, page_size: 50, pages: 1, results: [1, 2, 3].map(row) },
    }),
  );
  await page.route(`${API}/trials/organisations*`, (r) =>
    r.fulfill({ json: { count: 2, page: 1, page_size: 50, pages: 1, results: [4, 5].map(row) } }),
  );
}

test("a tile's count equals its drill-down list", async ({ page }) => {
  await mockMetrics(page);
  await page.goto("/console");
  const tile = page.locator('[data-tile="active"]');
  await expect(tile.locator("[data-tile-value]")).toHaveText("3");
  await page.getByRole("button", { name: "Show the organisations: Active organisations" }).click();
  const drill = page.getByRole("region", { name: "Active organisations: 3 organisations" });
  await expect(drill.getByRole("link")).toHaveCount(3);

  await expect(page.locator('[data-tile="trials"] [data-tile-value]')).toHaveText("2");
  await page.getByRole("button", { name: "Show the organisations: Trials" }).click();
  await expect(
    page.getByRole("region", { name: "Trials: 2 organisations" }).getByRole("link"),
  ).toHaveCount(2);
  await expect(page.locator("[data-trend-chart] svg")).toBeVisible();
  await expectAccessible(page);
});
