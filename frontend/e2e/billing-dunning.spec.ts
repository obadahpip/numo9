import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { entitlements, mockEntitlements } from "./entitlements-fixtures";

/**
 * U-04-T13 — Proration comparison and the dunning banner. Acceptance: the banner appears in
 * past_due with its call to action — the owner's "Update payment method" opens Stripe's page in one
 * click; others are told to ask the owner; nothing shows when the payment is fine. A downgrade's
 * comparison says nothing is charged today and when the new price starts.
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";

async function pastDue(page: Page, owner: boolean) {
  await mockCsrf(page);
  await mockEntitlements(
    page,
    ORG,
    entitlements({
      reason: "past_due",
      status: "past_due",
      grace_until: "2026-11-23T15:00:00Z",
      viewer: { can_change_package: owner },
    }),
  );
}

test.use({ viewport: { width: 1280, height: 1000 } });

test("past due: the owner updates the payment method in one click", async ({ page }) => {
  await pastDue(page, true);
  let portal = 0;
  await page.route(`**/api/v1/o/${ORG}/billing/portal`, (route) => {
    portal += 1;
    return route.fulfill({ status: 201, json: { url: `/o/${ORG}/home?portal=1` } });
  });
  await page.goto(`/o/${ORG}/home`);
  const notice = page.getByRole("region", { name: "Payment overdue" });
  await expect(notice).toContainText(
    "The subscription payment didn't go through. Everything works until 23 Nov 2026",
  );
  await expectAccessible(page);
  await notice.getByRole("button", { name: "Update payment method" }).click();
  await expect(page).toHaveURL(/portal=1/);
  expect(portal).toBe(1);
});

test("past due: everyone else is told to ask the owner", async ({ page }) => {
  await pastDue(page, false);
  await page.goto(`/o/${ORG}/home`);
  const notice = page.getByRole("region", { name: "Payment overdue" });
  await expect(notice).toContainText("Ask the organisation's owner to update the payment method.");
  await expect(notice.getByRole("button")).toHaveCount(0);
});

test("downgrade comparison: nothing today, the new price from the period end", async ({ page }) => {
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/billing`, (route) =>
    route.fulfill({
      json: {
        billing_available: true,
        subscription: {
          status: "active",
          package: { code: "growth", name: "Growth" },
          interval: "month",
          amount_cents: 4900,
          current_period_end: "2026-12-15T12:00:00Z",
          cancel_at_period_end: false,
          payment_method_type: "acss_debit",
          grace_until: null,
          paying: true,
        },
        pending_change: null,
        packages: [
          { code: "starter", name: "Starter", prices: { month: 2900, year: 29000 } },
          { code: "growth", name: "Growth", prices: { month: 4900, year: 49000 } },
        ],
        invoices: [],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/billing/export`, (route) =>
    route.fulfill({
      json: { job: null, status: null, url: null, expires_at: null, created_at: null },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/billing/change/preview*`, (route) =>
    route.fulfill({
      json: {
        kind: "downgrade",
        package: "starter",
        interval: "month",
        amount_cents: 2900,
        charged_today_cents: 0,
        currency: "CAD",
        effective_at: "2026-12-15T12:00:00Z",
        proration_date: 1790000000,
      },
    }),
  );
  await page.goto(`/o/${ORG}/settings/subscription`);
  await expect(page.locator("[data-method]")).toHaveText("Pre-authorised debit (PAD)");
  await page.getByRole("button", { name: "Choose Starter" }).click();
  await expect(page.getByRole("dialog").locator("[data-charge]")).toHaveText(
    "Nothing to pay today. You keep Growth until 15 Dec 2026; from then on you'll pay $29.00 per month.",
  );
});

test("no notice when the payment is fine", async ({ page }) => {
  await mockCsrf(page);
  await mockEntitlements(page, ORG, entitlements());
  await page.goto(`/o/${ORG}/home`);
  await expect(page.locator("main")).toBeVisible();
  await expect(page.locator("[data-payment-due]")).toHaveCount(0);
});
