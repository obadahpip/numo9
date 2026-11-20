import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * U-06-T13 — founding counter & demo manager panels on the console home (`/console`).
 * Acceptance: the counter shows x/1,000. Fixtures in the API's shape (backend/numo9/founding/api.py,
 * backend/numo9/demo/console.py).
 */
test("the console home shows the founding counter x/1,000 and the open demos", async ({ page }) => {
  await mockCsrf(page);
  await page.route("**/api/v1/platform/metrics*", (r) => r.fulfill({ status: 500, json: {} }));
  await page.route("**/api/v1/platform/founding", (r) =>
    r.fulfill({
      json: {
        cap: 1000,
        allocated: 427,
        remaining: 573,
        active: 427,
        churn_rule: "keep_if_returns_within_days",
        return_window_days: 90,
        refund_release_hours: 24,
        slots: [],
      },
    }),
  );
  await page.route("**/api/v1/platform/demos", (r) =>
    r.fulfill({
      json: {
        seed_version: 1,
        idle_days: 30,
        open: 1,
        purge_soon: 0,
        templates: [{ seed_version: 1, built_at: "2026-11-01T10:00:00Z" }],
        demos: [
          {
            id: "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6",
            name: "Maple & Pine Supply Co.",
            seed_version: 1,
            created_at: "2026-11-01T10:00:00Z",
            last_active_at: "2026-11-18T15:00:00Z",
            purge_on: "2026-12-19",
            members: 1,
          },
        ],
      },
    }),
  );
  await page.goto("/console");
  const founding = page.locator('[data-panel="founding"]');
  await expect(founding.locator("[data-founding-counter]")).toContainText("427/1,000");
  await expect(founding.getByRole("link", { name: "See founding places" })).toHaveAttribute(
    "href",
    "/console/founding",
  );
  const demos = page.locator('[data-panel="demos"]');
  await expect(demos.getByRole("row")).toHaveCount(2);
  await expect(
    demos.getByRole("button", { name: "Purge now: Maple & Pine Supply Co." }),
  ).toBeVisible();
  await expectAccessible(page);
});
