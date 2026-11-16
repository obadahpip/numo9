import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * U-04-T12 — Settings → Subscription (the owner's billing page): the current package card (status,
 * price, next charge), payment method with "Update payment method", the packages offered
 * (monthly/annual), the Numo9 invoices with PDF links, cancellation with the export link.
 * Acceptance: the owner completes an upgrade in ≤ 3 clicks; a trial organisation goes to Stripe
 * Checkout in one click; anyone else sees the owner-only message; axe clean.
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}/billing`;

const PACKAGES = [
  { code: "starter", name: "Starter", prices: { month: 2900, year: 29000 } },
  { code: "growth", name: "Growth", prices: { month: 4900, year: 49000 } },
  { code: "complete", name: "Complete", prices: { month: 9900, year: 99000 } },
];

export const paying = {
  billing_available: true,
  subscription: {
    status: "active",
    package: { code: "growth", name: "Growth" },
    interval: "month",
    amount_cents: 4900,
    current_period_end: "2026-12-15T12:00:00Z",
    cancel_at_period_end: false,
    payment_method_type: "card",
    grace_until: null,
    paying: true,
  },
  pending_change: null,
  packages: PACKAGES,
  invoices: [
    {
      id: "i2",
      number: "NUMO9-0002",
      status: "paid",
      issued_at: "2026-11-15T12:00:00Z",
      total_cents: 5537,
      currency: "CAD",
      pdf_url: "https://pay.stripe.com/invoice/in_2/pdf",
      hosted_url: "",
    },
  ],
};

const noExport = { job: null, status: null, url: null, expires_at: null, created_at: null };

async function mock(page: Page, overview: unknown = paying) {
  await mockCsrf(page);
  const calls: { url: string; body?: Record<string, unknown> }[] = [];
  await page.route(API, (route) => route.fulfill({ json: overview }));
  await page.route(`${API}/export`, (route) => route.fulfill({ json: noExport }));
  await page.route(`${API}/change/preview*`, (route) =>
    route.fulfill({
      json: {
        kind: "upgrade",
        package: "complete",
        interval: "month",
        amount_cents: 9900,
        charged_today_cents: 2513,
        currency: "CAD",
        effective_at: "2026-11-16T12:00:00Z",
        proration_date: 1790000000,
      },
    }),
  );
  await page.route(`${API}/change`, (route) => {
    calls.push({ url: route.request().url(), body: jsonBody(route) });
    return route.fulfill({
      json: {
        kind: "upgrade",
        package: "complete",
        interval: "month",
        amount_cents: 9900,
        charged_today_cents: 0,
        currency: "CAD",
        effective_at: "2026-11-16T12:00:00Z",
        proration_date: 1790000000,
      },
    });
  });
  await page.route(`${API}/checkout`, (route) => {
    calls.push({ url: route.request().url(), body: jsonBody(route) });
    return route.fulfill({
      status: 201,
      json: { url: `/o/${ORG}/settings/subscription?checkout=success` },
    });
  });
  await page.route(`${API}/cancel`, (route) => {
    calls.push({ url: route.request().url(), body: jsonBody(route) });
    return route.fulfill({
      json: {
        cancel_at_period_end: true,
        current_period_end: "2026-12-15T12:00:00Z",
        export: { ...noExport, job: "j1", status: "queued" },
      },
    });
  });
  return calls;
}

test.use({ viewport: { width: 1280, height: 1100 } });

test("billing page: package card, method, invoices; upgrade in ≤ 3 clicks", async ({ page }) => {
  const calls = await mock(page);
  await page.goto(`/o/${ORG}/settings/subscription`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Subscription");
  const card = page.locator("[data-current-package]");
  await expect(card).toContainText("Growth");
  await expect(card).toContainText("Active");
  await expect(card).toContainText("$49.00 per month");
  await expect(card.locator("[data-next-charge]")).toContainText("Next charge: $49.00 on");
  await expect(card.locator("[data-method]")).toHaveText("Card");
  await expect(card.getByRole("button", { name: "Update payment method" })).toBeVisible();
  await expect(page.getByRole("link", { name: "PDF of invoice NUMO9-0002" })).toHaveAttribute(
    "href",
    "https://pay.stripe.com/invoice/in_2/pdf",
  );
  await expect(page.locator('[data-package="growth"]')).toContainText("Your package");
  await expectAccessible(page);

  // 1: choose, 2: confirm.
  await page.getByRole("button", { name: "Choose Complete" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Confirm change" }).click();
  await expect(page.locator("[data-billing-status]")).toHaveText("Your package is now Complete.");
  expect(calls.at(-1)?.body).toMatchObject({ package: "complete", interval: "month" });
});

test("a trial organisation goes to Stripe Checkout in one click", async ({ page }) => {
  const calls = await mock(page, {
    ...paying,
    subscription: {
      ...paying.subscription,
      status: "trialing",
      package: null,
      paying: false,
      payment_method_type: "",
    },
    invoices: [],
  });
  await page.goto(`/o/${ORG}/settings/subscription`);
  await expect(page.locator("[data-current-package]")).toContainText("Trial — every product");
  await expect(page.getByText("No invoices yet.")).toBeVisible();
  await page.getByRole("button", { name: "Annual" }).click();
  await expect(page.locator('[data-package="growth"]')).toContainText("$490.00 per year");
  await page.getByRole("button", { name: "Choose Growth" }).click();
  await expect(page).toHaveURL(/checkout=success/);
  expect(calls[0].body).toEqual({ package: "growth", interval: "year" });
});

test("cancel at the period end, then the export is prepared", async ({ page }) => {
  const calls = await mock(page);
  await page.goto(`/o/${ORG}/settings/subscription`);
  await page.getByRole("button", { name: "Cancel subscription" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Everyone keeps full access until");
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Cancel at the end of the period" }).click();
  await expect(page.locator("[data-billing-status]")).toContainText("The subscription ends on");
  await expect(
    page.getByText("Your export is being prepared. Come back in a few minutes."),
  ).toBeVisible();
  expect(calls.at(-1)?.body).toEqual({ resume: false });
});

test("anyone but the owner sees the owner-only message", async ({ page }) => {
  await mockCsrf(page);
  await page.route(API, (route) =>
    route.fulfill({ status: 403, json: { code: "permission.denied", detail: "No" } }),
  );
  await page.goto(`/o/${ORG}/settings/subscription`);
  await expect(
    page.getByText("Only the organisation's owner can see and change the subscription."),
  ).toBeVisible();
});
