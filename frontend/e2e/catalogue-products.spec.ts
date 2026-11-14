import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, expectNoHorizontalScroll, mockCsrf } from "./auth-helpers";
import products from "./fixtures/catalogue-products.json" with { type: "json" };

/**
 * U-01-T11 — platform-owner Products screen (`/console/products`). Acceptance: renders the 7
 * products; planned companion apps are greyed with "Planned"; a detail drawer shows each
 * product's feature keys. Fixture: the real API answer (backend/tests/test_catalogue_fixtures.py
 * keeps it equal to `GET /api/v1/platform/catalogue/products`).
 */
const API = "**/api/v1/platform/catalogue/products";

async function mockProducts(page: Page, answer: { status: number; json: unknown }) {
  await mockCsrf(page);
  await page.route(API, (r) => r.fulfill(answer));
}

test.use({ viewport: { width: 1280, height: 900 } });

test("renders the 7 products, planned companion apps greyed, keys in the drawer", async ({
  page,
}) => {
  await mockProducts(page, { status: 200, json: products });
  await page.goto("/console/products");
  await expect(page.getByRole("heading", { level: 1, name: "Products" })).toBeVisible();

  const main = page.getByRole("table", { name: "Products" });
  await expect(main.locator("tbody tr")).toHaveCount(7);
  for (const name of ["Accounting", "Tax", "Payroll", "Inventory", "Finance", "Practice"]) {
    await expect(
      main.getByRole("button", { name: `Show the feature keys of ${name}` }),
    ).toBeVisible();
  }
  await expect(
    main.locator('[data-product="practice"]').getByText("Free", { exact: true }),
  ).toBeVisible();
  await expect(main.locator('[data-product="tax"]').getByText("Active")).toBeVisible();

  const companions = page.getByRole("table", { name: "Companion apps" });
  await expect(companions.locator("tbody tr")).toHaveCount(3);
  const commerce = companions.locator('[data-product="app.commerce"]');
  await expect(commerce.getByText("Planned")).toBeVisible();
  await expect(commerce).toHaveClass(/text-fg-muted/); // greyed
  await expect(commerce.locator('[data-status="planned"]')).toBeVisible();

  await main.getByRole("button", { name: "Show the feature keys of Accounting" }).click();
  const drawer = page.getByRole("dialog", { name: "Accounting" });
  await expect(drawer).toBeVisible();
  const accounting = products.products.find((p) => p.code === "accounting")!;
  await expect(drawer.getByText(`${accounting.features.length} feature keys`)).toBeVisible();
  await expect(drawer.locator("[data-feature-key]")).toHaveCount(accounting.features.length);
  const invoices = drawer.locator('[data-feature-key="accounting.sales_invoices.write"]');
  await expect(invoices.locator("code")).toHaveText("accounting.sales_invoices.write");
  const described = accounting.features.find((f) => f.key === "accounting.sales_invoices.write")!;
  await expect(invoices).toContainText(described.description);
  await expectAccessible(page);
  await drawer.getByRole("button", { name: "Close" }).click();
  await expect(drawer).toBeHidden();

  await companions.getByRole("button", { name: "Show the feature keys of Numo9 Commerce" }).click();
  await expect(
    page.getByRole("dialog").getByText("Feature keys are added when this product is built."),
  ).toBeVisible();
});

test("export links download the feature matrix", async ({ page }) => {
  await mockProducts(page, { status: 200, json: products });
  await page.goto("/console/products");
  await expect(page.getByRole("link", { name: "Export feature matrix (CSV)" })).toHaveAttribute(
    "href",
    "/api/v1/platform/catalogue/feature-matrix/export/csv",
  );
  await expect(page.getByRole("link", { name: "Export feature matrix (XLSX)" })).toHaveAttribute(
    "href",
    "/api/v1/platform/catalogue/feature-matrix/export/xlsx",
  );
});

test("someone without platform.catalogue.view gets the refusal panel", async ({ page }) => {
  await mockProducts(page, {
    status: 403,
    json: {
      code: "permission.denied",
      detail: "You don't have permission to see products, feature keys and the feature matrix.",
    },
  });
  await page.goto("/console/products");
  await expect(
    page.getByRole("heading", { level: 1, name: "You can't open the product catalogue" }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);
});

test("fits a phone screen", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await mockProducts(page, { status: 200, json: products });
  await page.goto("/console/products");
  await expect(page.getByRole("table", { name: "Products" })).toBeVisible();
  await expectNoHorizontalScroll(page);
});
