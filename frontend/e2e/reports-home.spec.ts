import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { CATALOGUE } from "./reports-fixtures";

/**
 * K-01-T12 — report home: search "tax" finds the tax reports; favourites; tabs. The catalogue,
 * favourites and gating are tested on the real API in backend/tests/test_report_api.py.
 */
async function mockCatalogue(page: Page) {
  await mockCsrf(page);
  await page.route("**/api/v1/o/acme/reports", (r) => r.fulfill({ json: CATALOGUE }));
  await page.route("**/api/v1/o/acme/reports/*/favourite", (r) => r.fulfill({ status: 204 }));
}

test("search 'tax' finds the tax reports", async ({ page }) => {
  await mockCatalogue(page);
  await page.goto("/o/acme/reports");
  await expect(page.getByRole("heading", { name: "Reports", level: 1 })).toBeVisible();
  await page.getByRole("searchbox", { name: "Search reports" }).fill("tax");
  const list = page.getByRole("list", { name: "Reports" });
  await expect(list.getByRole("listitem")).toHaveCount(1);
  await expect(list.getByRole("link", { name: "GST/HST summary" })).toBeVisible();
  await expect(list.getByText("Part of Tax — not in this organisation's package")).toBeVisible();
  await expectAccessible(page);
});

test("a starred report is listed under Favourites", async ({ page }) => {
  await mockCatalogue(page);
  await page.goto("/o/acme/reports");
  await page.getByRole("button", { name: "Add Trial balance to favourites" }).click();
  await page.getByRole("button", { name: "Favourites", exact: true }).click();
  await expect(page.getByRole("list", { name: "Reports" }).getByRole("listitem")).toHaveCount(1);
  await expect(page.getByRole("link", { name: "Trial balance" })).toBeVisible();
});
