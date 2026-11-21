import { expect, test } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * U-08-T11 — founding admin panel (`/console/founding`): list slots, export, release with a
 * reason. Fixtures in the API's shape (backend/numo9/founding/api.py; that the export's row count
 * equals the allocated count: backend/tests/test_founding_console_api.py).
 */
const slot = (n: number, state = "active") => ({
  slot_no: n,
  organisation_id: `7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f${n}`,
  organisation_name: ["Maple Bakery Inc.", "Birch Ltd.", "Pine Co."][n - 1],
  allocated_at: "2026-11-18T15:00:00Z",
  payment_ref: `in_${n}`,
  lapsed_at: null,
  released_at: state === "released" ? "2026-11-19T15:00:00Z" : null,
  release_reason: state === "released" ? "admin" : "",
  state,
});

test("list the slots, export, release one with a reason", async ({ page }) => {
  await mockCsrf(page);
  const released: Record<string, unknown>[] = [];
  await page.route("**/api/v1/platform/founding", (r) =>
    r.fulfill({
      json: {
        cap: 1000,
        allocated: 3,
        remaining: 997,
        active: 3,
        churn_rule: "keep_if_returns_within_days",
        return_window_days: 90,
        refund_release_hours: 24,
        slots: [slot(1), slot(2), slot(3)],
      },
    }),
  );
  await page.route("**/api/v1/platform/founding/slots/2/release", (r) => {
    released.push(jsonBody(r));
    return r.fulfill({ json: slot(2, "released") });
  });

  await page.goto("/console/founding");
  await expect(page.getByRole("heading", { name: "3 of 1,000 places given" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
    "href",
    "/api/v1/platform/founding/export",
  );
  await expect(page.locator("tbody tr")).toHaveCount(3);
  await expectAccessible(page);

  await page.getByRole("button", { name: "Release place 0002 (Birch Ltd.)" }).click();
  const dialog = page.getByRole("dialog", { name: "Release founding place 0002?" });
  await dialog.getByLabel("Reason").fill("Duplicate account of Maple");
  await dialog.getByRole("button", { name: "Release" }).click();
  await expect(page.locator('[data-slot="2"]')).toContainText("Released (released by Numo9)");
  expect(released).toEqual([{ reason: "Duplicate account of Maple" }]);
});
