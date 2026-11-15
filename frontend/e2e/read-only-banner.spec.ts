import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { entitlements, mockEntitlements } from "./entitlements-fixtures";

/**
 * U-03-T12 — read-only organisation header notice: the text names the reason and the date; the
 * owner gets "Reactivate the subscription", everyone else is told to ask the owner; reading
 * stays possible (the module renders); no notice for an organisation in full mode.
 */
const ORG = "acme";
const READ_ONLY = { mode: "read_only", since: "2026-11-20T05:00:00+00:00" };

test.use({ viewport: { width: 1280, height: 900 } });

test.beforeEach(async ({ page }) => {
  await mockCsrf(page);
});

for (const [reason, text] of [
  ["payment_failed", "the payment failed and the grace period ended."],
  ["trial_ended", "the free trial ended."],
  ["cancelled", "the subscription was cancelled."],
] as const) {
  test(`banner text names the reason: ${reason}`, async ({ page }) => {
    await mockEntitlements(page, ORG, entitlements({ ...READ_ONLY, reason }));
    await page.goto("/o/acme/accounting/journals");
    const notice = page.getByRole("region", { name: "Organisation status" });
    await expect(notice).toContainText(
      `This organisation has been read-only since 20 Nov 2026: ${text}`,
    );
    await expect(notice).toContainText("You can still see and export everything.");
    // Under the top bar, above the breadcrumb bar; the work area still renders.
    await expect(page.locator('[data-shell="banner"]')).toBeVisible();
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toHaveText("Journals");
  });
}

test("owner gets the reactivate link; staff are told to ask the owner", async ({ page }) => {
  await mockEntitlements(page, ORG, entitlements({ ...READ_ONLY, reason: "payment_failed" }));
  await page.goto("/o/acme/home");
  const notice = page.getByRole("region", { name: "Organisation status" });
  await expect(notice.getByRole("link", { name: "Reactivate the subscription" })).toHaveAttribute(
    "href",
    "/o/acme/settings/subscription",
  );
  await expect(page).toHaveTitle(/.+/);
  await expectAccessible(page);

  await page.unroute(`**/api/v1/o/${ORG}/entitlements`);
  await mockEntitlements(
    page,
    ORG,
    entitlements({ ...READ_ONLY, reason: "payment_failed", viewer: { can_change_package: false } }),
  );
  await page.goto("/o/acme/home");
  await expect(notice).toContainText("Ask the organisation's owner to reactivate it.");
  await expect(notice.getByRole("link")).toHaveCount(0);
});

test("no notice while the organisation has full access", async ({ page }) => {
  await mockEntitlements(page, ORG, entitlements({ reason: "past_due", status: "past_due" }));
  await page.goto("/o/acme/home");
  await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Organisation status" })).toHaveCount(0);
});
