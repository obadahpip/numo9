import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, expectNoHorizontalScroll, mockCsrf } from "./auth-helpers";
import matrix from "./fixtures/catalogue-feature-matrix.json" with { type: "json" };

/**
 * U-01-T12 — Settings → Package and features (`/o/:org/settings/package-features`).
 * Acceptance: searching "reminder" filters the rows; the current package column is highlighted;
 * axe clean. Fixture: the real feature matrix (backend/tests/test_catalogue_fixtures.py). The
 * package columns are a U-02-shaped sample (packages arrive with U-02, the current package with
 * U-03/U-04): Starter = Accounting + free sets, Growth = + Tax, Complete = every main product.
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const PAGE = `/o/${ORG}/settings/package-features`;
const API = `**/api/v1/o/${ORG}/package-features`;

const FREE = ["practice", "portal"];
const PACKAGES = [
  { code: "starter", name: "Starter", products: ["accounting", ...FREE] },
  { code: "growth", name: "Growth", products: ["accounting", "tax", ...FREE] },
  {
    code: "complete",
    name: "Complete",
    products: ["accounting", "tax", "payroll", "inventory", "finance", ...FREE],
  },
];

function withPackages(current: string | null) {
  return {
    ...matrix,
    packages: PACKAGES,
    features: matrix.features.map((row) => ({
      ...row,
      packages: PACKAGES.filter((p) => p.products.includes(row.product)).map((p) => p.code),
    })),
    current_package: current,
  };
}

async function mockMatrix(page: Page, body: unknown, status = 200) {
  await mockCsrf(page);
  await page.route(API, (r) => r.fulfill({ status, json: body }));
}

test.use({ viewport: { width: 1280, height: 900 } });

test("search filters the rows and the current package column is highlighted", async ({ page }) => {
  await mockMatrix(page, withPackages("growth"));
  await page.goto(PAGE);
  await expect(page.getByRole("heading", { level: 1, name: "Package and features" })).toBeVisible();
  const rows = page.locator("tr[data-feature-key]");
  await expect(rows).toHaveCount(matrix.features.length);
  // Grouped by product.
  for (const name of ["Accounting", "Tax", "Practice", "Client portal"]) {
    await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
  }

  // Current package: "You are here", aria-current, highlighted header and cells.
  const growth = page.getByRole("columnheader", { name: /Growth/ }).first();
  await expect(growth).toHaveAttribute("aria-current", "true");
  await expect(growth.getByText("You are here")).toBeVisible();
  await expect(growth).toHaveClass(/bg-surface-accent-subtle/);
  await expect(page.locator('th[data-current="true"]')).toHaveCount(4); // one per product table
  await expect(page.getByRole("columnheader", { name: "Starter" }).first()).not.toHaveAttribute(
    "aria-current",
    "true",
  );

  // Ticks per package.
  const returns = page.locator('tr[data-feature-key="tax.returns.write"]');
  await expect(returns.locator('td[data-package="starter"]')).toContainText("Not in Starter");
  await expect(returns.locator('td[data-package="growth"]')).toContainText("Included in Growth");

  await page.getByLabel("Search features").fill("reminder");
  await expect(rows).toHaveCount(2);
  await expect(
    page.locator('tr[data-feature-key="accounting.invoice_reminders.write"]'),
  ).toContainText("Send invoice reminders before and after the due date");
  await expect(page.getByRole("status")).toHaveText("2 features match “reminder”.");
  await expect(page.getByRole("heading", { level: 2, name: "Tax" })).toHaveCount(0);
  await expectAccessible(page);

  await page.getByLabel("Search features").fill("gst approve");
  await expect(rows).toHaveCount(0);
  await page.getByLabel("Search features").fill("returns approve");
  await expect(rows).toHaveCount(1);
  await page.getByLabel("Search features").fill("");
  await expect(rows).toHaveCount(matrix.features.length);
});

test("before packages exist every feature is listed under its product", async ({ page }) => {
  await mockMatrix(page, { ...matrix, current_package: null });
  await page.goto(PAGE);
  await expect(
    page.getByText("Packages and prices aren't published yet.", { exact: false }),
  ).toBeVisible();
  await expect(page.locator("tr[data-feature-key]")).toHaveCount(matrix.features.length);
  await expect(page.locator("th[data-package]")).toHaveCount(0);
  await expectAccessible(page);
});

test("another organisation's page answers not available", async ({ page }) => {
  await mockMatrix(page, { detail: "Not found.", code: "not_found" }, 404);
  await page.goto(PAGE);
  await expect(
    page.getByRole("heading", { level: 1, name: "This organisation isn't available" }),
  ).toBeVisible();
});

test("fits a phone screen", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await mockMatrix(page, withPackages("complete"));
  await page.goto(PAGE);
  await expect(page.getByRole("heading", { level: 2, name: "Accounting" })).toBeVisible();
  await expectNoHorizontalScroll(page);
});
