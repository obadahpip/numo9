import { expect, test } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";
import {
  ACCOUNTING_FEATURES,
  entitlements,
  mockEntitlements,
  WITHOUT_ACCOUNTING,
} from "./entitlements-fixtures";

/**
 * U-03-T15 — gap-closure tests (xero_teardown §2.2, §2.5, §6.3; Project Plan gap table):
 *
 * - gap-06 — Xero paywalls invoice approval. In Numo9 approval is part of the Accounting product:
 *   an organisation whose package has Accounting gets every Accounting approval key and no
 *   Accounting screen is locked (backend half: tests/test_entitlements_gaps.py);
 * - gap-14 — Xero's credit note silently redirects. A gated route renders the locked panel at its
 *   own URL — no redirect, no navigation;
 * - gap-41 — Xero shows generic upgrade banners and the advisor can't see the plan. The prompt is
 *   explicit: it names the product and the packages that include it, and links to the in-app
 *   Package and features page; nothing generic ("Upgrade now") appears anywhere.
 */
const ORG = "acme";
const ROUTES = ["/o/acme/contacts", "/o/acme/accounting/chart-of-accounts", "/o/acme/documents"];

test.use({ viewport: { width: 1280, height: 900 } });

test.beforeEach(async ({ page }) => {
  await mockCsrf(page);
});

test("@gap-06 approval is never gated inside Accounting", async ({ page }) => {
  const approve = ACCOUNTING_FEATURES.filter((key) => key.endsWith(".approve"));
  expect(approve.length).toBeGreaterThan(0);
  // Starter = Accounting only: every Accounting approval key comes with it.
  await mockEntitlements(page, ORG, entitlements({ package: "starter" }));
  for (const path of [...ROUTES, "/o/acme/accounting/journals"]) {
    await page.goto(path);
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.locator('[data-feature-state="gated"]')).toHaveCount(0);
    await expect(page.locator('[data-locked="true"]')).toHaveCount(0);
  }
});

test("@gap-14 a gated route never redirects", async ({ page }) => {
  await mockEntitlements(page, ORG, entitlements(WITHOUT_ACCOUNTING));
  const navigations: string[] = [];
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame()) navigations.push(new URL(frame.url()).pathname);
  });
  for (const path of ROUTES) {
    navigations.length = 0;
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
    expect(response?.request().redirectedFrom()).toBeNull();
    await expect(page.locator('[data-explain="gated"]')).toBeVisible();
    await page.waitForTimeout(300); // a client-side redirect would land here
    expect(new URL(page.url()).pathname).toBe(path);
    expect(navigations.every((p) => p === path)).toBe(true);
  }
});

test("@gap-41 the prompt names the product and its packages, never a generic upgrade", async ({
  page,
}) => {
  await mockEntitlements(page, ORG, entitlements(WITHOUT_ACCOUNTING));
  await page.goto("/o/acme/contacts");
  const panel = page.locator('[data-explain="gated"]');
  await expect(panel.getByRole("heading")).toHaveText(
    "Accounting isn't in this organisation's package",
  );
  await expect(panel).toContainText("included in Starter, Growth");
  await expect(panel.getByRole("link", { name: "See what's in each package" })).toHaveAttribute(
    "href",
    "/o/acme/settings/package-features",
  );
  const text = (await page.locator("body").innerText()).toLowerCase();
  for (const generic of ["upgrade now", "upgrade your plan", "go premium", "unlock all"]) {
    expect(text).not.toContain(generic);
  }
});
