import { expect, test } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * U-03-T14 — platform-owner override UI: grant a product for N days with a reason, from the
 * console's organisation page. Acceptance: the override is visible in the organisation's audit log
 * (the page reloads its recent audit events after the grant). Fixtures in the API's shape
 * (backend/numo9/entitlements/overrides.py; the audit entry itself is tested against the API in
 * backend/tests/test_entitlements_override_console.py).
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";

test("grant Payroll for 14 days and see it in the organisation's audit log", async ({ page }) => {
  await mockCsrf(page);
  const events: { at: string; action: string; actor: string; record: string }[] = [];
  await page.route(`**/api/v1/platform/organisations/${ORG}`, (r) =>
    r.fulfill({
      json: {
        id: ORG,
        name: "Maple Leaf Supply Ltd.",
        status: "active",
        is_demo: false,
        province: "ON",
        time_zone: "America/Toronto",
        created_at: "2026-10-02T14:00:00Z",
        subscription: null,
        timeline: [],
        users: [],
        practices: [],
        recent_events: events,
      },
    }),
  );
  const grants: Record<string, unknown>[] = [];
  const sent: Record<string, unknown>[] = [];
  await page.route(`**/api/v1/platform/organisations/${ORG}/overrides`, (r) => {
    if (r.request().method() === "POST") {
      sent.push(jsonBody(r));
      const grant = {
        id: "8f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6",
        product: "payroll",
        product_name: "Payroll",
        expires_at: "2026-12-04T15:00:00Z",
        reason: "Payroll pilot agreed with the owner",
        granted_by: "Priya Shah",
        created_at: "2026-11-20T15:00:00Z",
        removed_at: null,
        state: "active",
      };
      grants.unshift(grant);
      events.unshift({
        at: "2026-11-20T15:00:00Z",
        action: "entitlements.entitlementoverride.created",
        actor: "Priya Shah",
        record: "payroll until 2026-12-04",
      });
      return r.fulfill({ status: 201, json: grant });
    }
    return r.fulfill({
      json: {
        overrides: grants,
        products: [
          { code: "payroll", name: "Payroll" },
          { code: "tax", name: "Tax" },
        ],
        max_days: 365,
      },
    });
  });

  await page.goto(`/console/organisations/${ORG}`);
  const section = page.locator("[data-product-grants]");
  await expect(section.getByText("No product granted to this organisation.")).toBeVisible();
  await section.getByLabel("Product").selectOption("payroll");
  await section.getByLabel("Days").fill("14");
  await section.getByLabel("Reason").fill("Payroll pilot agreed with the owner");
  await section.getByRole("button", { name: "Grant product" }).click();
  await expect(section.locator("[data-grants] li")).toContainText(
    "Payroll pilot agreed with the owner",
  );
  expect(sent).toEqual([
    { product: "payroll", days: 14, reason: "Payroll pilot agreed with the owner" },
  ]);
  await expect(page.locator("[data-audit]")).toContainText(
    "entitlements.entitlementoverride.created",
  );
  await expectAccessible(page);
});
