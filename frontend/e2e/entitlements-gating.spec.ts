import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { entitlements, mockEntitlements, WITHOUT_ACCOUNTING } from "./entitlements-fixtures";

/**
 * U-03-T11 (gap-14) — navigation items of gated modules keep their place with a lock glyph and a
 * tooltip; visiting a gated URL shows the locked panel, the URL unchanged (no route redirects).
 * The entitlements bootstrap is answered with the API's shape (e2e/entitlements-fixtures.ts).
 */
const ORG = "acme";
const GATED_ROUTES = [
  "/o/acme/contacts",
  "/o/acme/accounting/chart-of-accounts",
  "/o/acme/accounting/journals",
  "/o/acme/documents",
];

test.use({ viewport: { width: 1280, height: 900 } });

test.beforeEach(async ({ page }) => {
  await mockCsrf(page);
});

test("@gap-14 visiting a gated URL shows the locked panel, the URL unchanged", async ({ page }) => {
  await mockEntitlements(page, ORG, entitlements(WITHOUT_ACCOUNTING));
  for (const path of GATED_ROUTES) {
    const response = await page.goto(path);
    expect(response?.status(), path).toBe(200);
    const panel = page.locator('[data-explain="gated"]');
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "Accounting isn't in this organisation's package",
      }),
    ).toBeVisible();
    await expect(panel).toContainText(
      "It's part of the Accounting product, included in Starter, Growth.",
    );
    expect(new URL(page.url()).pathname, path).toBe(path); // no redirect, ever
    await expect(page.locator(`[data-feature-state="gated"]`)).toHaveCount(1);
  }
});

test("navigation items of gated modules show a lock glyph and a tooltip", async ({ page }) => {
  await mockEntitlements(page, ORG, entitlements(WITHOUT_ACCOUNTING));
  await page.goto("/o/acme/home");
  const nav = page.getByRole("banner").getByRole("navigation", { name: "Main" });
  const contacts = nav.getByRole("link", { name: /^Contacts/ });
  await expect(contacts).toHaveAttribute("data-locked", "true");
  await expect(contacts.locator('[data-icon="lock"]')).toBeVisible();
  await expect(nav.getByRole("link", { name: "Home", exact: true })).not.toHaveAttribute(
    "data-locked",
  );
  await expect(nav.getByRole("link", { name: "Settings", exact: true })).not.toHaveAttribute(
    "data-locked",
  );
  await expect(nav.locator('[data-locked="true"]')).toHaveCount(3); // Contacts, Accounting, Documents

  await contacts.hover();
  await expect(page.getByRole("tooltip")).toHaveText(
    "Accounting isn't in this organisation's package",
  );

  // The item still opens its module, which shows the locked panel in place.
  await contacts.click();
  await expect(page).toHaveURL(/\/o\/acme\/contacts$/);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Accounting isn't in this organisation's package",
    }),
  ).toBeVisible();
  // axe after a full page load: client-side navigation sets the document title a moment later.
  await page.goto("/o/acme/contacts");
  await expect(page.locator('[data-explain="gated"]')).toBeVisible();
  await expect(page).toHaveTitle(/.+/);
  await expectAccessible(page);
});

test("the drawer writes the explanation out for touch users", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockEntitlements(page, ORG, entitlements(WITHOUT_ACCOUNTING));
  await page.goto("/o/acme/home");
  await page.getByRole("button", { name: "Open navigation" }).click();
  const drawer = page.getByRole("dialog", { name: "Navigation" });
  const contacts = drawer.getByRole("link", { name: /^Contacts/ });
  await expect(contacts).toContainText("Accounting isn't in this organisation's package");
  await expect(contacts).toHaveAttribute("data-locked", "true");
});

test("an entitled organisation sees its modules, no lock", async ({ page }) => {
  await mockEntitlements(page, ORG, entitlements());
  await page.goto("/o/acme/accounting/journals");
  await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toHaveText("Journals");
  await expect(page.locator('[data-locked="true"]')).toHaveCount(0);
});

test("locked panel buttons per role: the owner changes the package, staff ask the owner", async ({
  page,
}) => {
  await mockEntitlements(page, ORG, entitlements(WITHOUT_ACCOUNTING));
  await page.goto("/o/acme/contacts");
  const panel = page.locator('[data-explain="gated"]');
  await expect(panel.getByRole("link", { name: "See what's in each package" })).toHaveAttribute(
    "href",
    "/o/acme/settings/package-features",
  );
  await expect(panel.getByRole("link", { name: "Change the package" })).toHaveAttribute(
    "href",
    "/o/acme/settings/subscription",
  );

  await page.unroute(`**/api/v1/o/${ORG}/entitlements`);
  await mockEntitlements(
    page,
    ORG,
    entitlements({ ...WITHOUT_ACCOUNTING, viewer: { can_change_package: false } }),
  );
  await page.goto("/o/acme/contacts");
  await expect(panel.getByRole("link", { name: "Change the package" })).toHaveCount(0);
  await panel.getByRole("button", { name: "Ask the owner" }).click();
  await expect(panel.getByRole("status")).toHaveText(
    "Only the organisation's owner can change the package. Ask them to add Accounting.",
  );
  await expect(page).toHaveTitle(/.+/);
  await expectAccessible(page);
});
