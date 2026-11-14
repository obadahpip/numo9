import { expect, test, type Page, type Route } from "@playwright/test";

import { expectAccessible, expectNoHorizontalScroll, jsonBody, mockCsrf } from "./auth-helpers";
import products from "./fixtures/catalogue-products.json" with { type: "json" };
import fixture from "./fixtures/console-packages.json" with { type: "json" };

/**
 * U-02-T09 — package editor (`/console/packages`, `/console/packages/new`, `/console/packages/<code>`).
 * Acceptance: the platform owner creates a package in under 2 minutes (usability target); product
 * cards, limits and a live preview of the public pricing card. Fixtures: the real API answers
 * (backend/tests/test_packages_fixtures.py, test_catalogue_fixtures.py).
 */
type Pkg = Record<string, unknown>;
const API = "**/api/v1/platform/packages";
const byCode = (code: string): Pkg => fixture.packages.find((p) => p.code === code)! as Pkg;

async function mockCatalogue(page: Page) {
  await mockCsrf(page);
  await page.route("**/api/v1/platform/catalogue/products", (r) =>
    r.fulfill({ status: 200, json: products }),
  );
}

test.use({ viewport: { width: 1280, height: 900 } });

test("lists every package with status, products, prices today and subscribers", async ({
  page,
}) => {
  await mockCatalogue(page);
  await page.route(API, (r) => r.fulfill({ status: 200, json: fixture }));
  await page.goto("/console/packages");
  await expect(page.getByRole("heading", { level: 1, name: "Packages and prices" })).toBeVisible();
  const rows = page.locator("tr[data-package]");
  await expect(rows).toHaveCount(4);
  const growth = page.locator('tr[data-package="growth"]');
  await expect(growth.getByRole("link", { name: "Open Growth" })).toHaveAttribute(
    "href",
    "/console/packages/growth",
  );
  await expect(growth).toContainText("Accounting, Tax");
  await expect(growth).toContainText("$39.00");
  await expect(growth).toContainText("$468.00");
  await expect(growth.getByText("Active")).toBeVisible();
  await expect(page.locator('tr[data-package="complete"]')).toContainText("No price");
  await expect(page.locator('tr[data-package="complete"]').getByText("Draft")).toBeVisible();
  await expect(page.locator('tr[data-package="legacy"]').getByText("Retired")).toBeVisible();
  await expectAccessible(page);
});

test("empty list invites the first package", async ({ page }) => {
  await mockCatalogue(page);
  await page.route(API, (r) => r.fulfill({ status: 200, json: { packages: [] } }));
  await page.goto("/console/packages");
  await expect(page.getByText("No packages yet")).toBeVisible();
  await expect(page.getByRole("link", { name: "Create a package" })).toHaveAttribute(
    "href",
    "/console/packages/new",
  );
});

test("owner creates and activates a package in under 2 minutes, preview follows the form", async ({
  page,
}) => {
  const started = Date.now();
  const created: Pkg = {
    ...byCode("growth"),
    status: "draft",
    status_label: "Draft",
    prices: [],
    current_prices: { month: null, year: null },
  };
  let posted: Record<string, unknown> | null = null;
  let stored: Pkg = created;
  await mockCatalogue(page);
  await page.route(API, async (r: Route) => {
    if (r.request().method() === "POST") {
      posted = jsonBody(r);
      await r.fulfill({ status: 201, json: created });
    } else await r.fulfill({ status: 200, json: { packages: [] } });
  });
  await page.route(`${API}/growth`, (r) => r.fulfill({ status: 200, json: stored }));
  await page.route(`${API}/growth/activate`, async (r) => {
    jsonBody(r);
    stored = { ...created, status: "active", status_label: "Active" };
    await r.fulfill({ status: 200, json: stored });
  });

  await page.goto("/console/packages/new");
  await expect(page.getByRole("heading", { level: 1, name: "New package" })).toBeVisible();
  const card = page.getByTestId("pricing-card");
  await expect(card.getByTestId("card-name")).toHaveText("Package name");

  await page.getByLabel("Code").fill("growth");
  await page.getByLabel("Name (English)").fill("Growth");
  await page.getByLabel("Name (French)").fill("Croissance");
  await page.getByLabel("Description (English)").fill("For growing teams.");
  await page.getByRole("switch", { name: "Include Accounting" }).click();
  await page.getByRole("switch", { name: "Include Tax" }).click();
  await page.getByLabel("Organisation users").fill("10");
  await page.getByRole("switch", { name: /Founding offer/ }).click();

  // live preview of the public pricing card
  await expect(card.getByTestId("card-name")).toHaveText("Growth");
  await expect(card).toContainText("For growing teams.");
  await expect(card.getByTestId("card-lines")).toContainText("Accounting");
  await expect(card.getByTestId("card-lines")).toContainText("Tax");
  await expect(card.getByTestId("card-lines")).toContainText("Practice, Client portal (free)");
  await expect(card.getByTestId("card-lines")).toContainText("Up to 10 organisation users");
  await expect(card.getByText("Founding offer")).toBeVisible();
  await expect(card.getByTestId("card-price")).toHaveText("Price to come");

  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page).toHaveURL(/\/console\/packages\/growth$/);
  expect(posted).toEqual({
    code: "growth",
    name_i18n: { "en-CA": "Growth", "fr-CA": "Croissance" },
    description_i18n: { "en-CA": "For growing teams." },
    products: ["accounting", "tax"],
    limits: { max_org_users: 10 },
    is_founding_eligible: true,
  });
  await expect(page.getByRole("heading", { level: 1, name: "Growth" })).toBeVisible();

  await page.route(`${API}/growth`, async (r) => {
    if (r.request().method() === "PATCH") jsonBody(r);
    await r.fulfill({ status: 200, json: stored });
  });
  await page.getByRole("button", { name: "Activate package" }).click();
  await expect(page.getByRole("status")).toHaveText("Growth is offered at sign-up.");
  await expect(page.getByRole("button", { name: "Retire package" })).toBeVisible();
  expect(Date.now() - started).toBeLessThan(120_000); // usability target: < 2 minutes
});

test("planned companion apps can't be switched on; free sets are named", async ({ page }) => {
  await mockCatalogue(page);
  await page.goto("/console/packages/new");
  const commerce = page.locator('[data-product-card="app.commerce"]');
  await expect(commerce).toContainText("Planned — can't be added yet");
  await expect(commerce.getByRole("switch")).toBeDisabled();
  await expect(page.locator('[data-product-card="practice"]')).toHaveCount(0);
  await expect(
    page.getByText("Included free in every package: Practice, Client portal."),
  ).toBeVisible();
  await expectAccessible(page);
});

test("the API's field errors show under each field", async ({ page }) => {
  await mockCatalogue(page);
  await page.route(API, (r) =>
    r.fulfill({
      status: 400,
      json: {
        code: ["A package with the code growth already exists. Choose another code."],
        products: ["practice is free and part of every package: it isn't added to one."],
      },
    }),
  );
  await page.goto("/console/packages/new");
  await page.getByLabel("Code").fill("growth");
  await page.getByLabel("Name (English)").fill("Growth");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Some fields need attention." }),
  ).toHaveText("Some fields need attention. Fix them and save again.");
  await expect(page.getByLabel("Code")).toHaveAttribute("aria-invalid", "true");
  await expect(
    page.getByText("A package with the code growth already exists. Choose another code."),
  ).toBeVisible();
  await expect(page.getByTestId("products-error")).toContainText("practice is free");
  await expect(page).toHaveURL(/\/console\/packages\/new$/);
});

test("activation refused without products shows the API's message", async ({ page }) => {
  const draft = { ...byCode("complete"), products: [] };
  await mockCatalogue(page);
  await page.route(`${API}/complete`, (r) => r.fulfill({ status: 200, json: draft }));
  await page.route(`${API}/complete/activate`, (r) =>
    r.fulfill({
      status: 400,
      json: {
        code: "packages.no_products",
        detail: "Add at least one product before activating this package.",
      },
    }),
  );
  await page.goto("/console/packages/complete");
  for (const name of ["Accounting", "Tax", "Payroll", "Inventory"]) {
    await page.getByRole("switch", { name: `Include ${name}` }).click();
    await page.getByRole("switch", { name: `Include ${name}` }).click();
  }
  await page.getByRole("button", { name: "Activate package" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Add at least one product" })).toHaveText(
    "Add at least one product before activating this package.",
  );
});

test("retire asks first, names the subscribers, then shows the retired notice", async ({
  page,
}) => {
  const growth = { ...byCode("growth"), subscriber_count: 14 };
  await mockCatalogue(page);
  await page.route(`${API}/growth`, (r) => r.fulfill({ status: 200, json: growth }));
  await page.route(`${API}/growth/retire`, (r) =>
    r.fulfill({ status: 200, json: { ...growth, status: "retired", status_label: "Retired" } }),
  );
  await page.goto("/console/packages/growth");
  await page.getByRole("button", { name: "Retire package" }).click();
  const dialog = page.getByRole("dialog", { name: "Retire Growth?" });
  await expect(dialog).toContainText("The 14 organisations that subscribe keep it.");
  await dialog.getByRole("button", { name: "Retire package" }).click();
  await expect(page.getByTestId("retired-notice")).toHaveText(
    "Retired — hidden from sign-up. 14 organisations keep their subscription.",
  );
  await expect(page.getByLabel("Code")).toHaveAttribute("readonly", "");
});

test("a draft can be deleted after confirming", async ({ page }) => {
  await mockCatalogue(page);
  let deleted = false;
  await page.route(`${API}/complete`, async (r) => {
    if (r.request().method() === "DELETE") {
      deleted = true;
      await r.fulfill({ status: 204, body: "" });
    } else await r.fulfill({ status: 200, json: byCode("complete") });
  });
  await page.route(API, (r) => r.fulfill({ status: 200, json: fixture }));
  await page.goto("/console/packages/complete");
  await page.getByRole("button", { name: "Delete draft" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete draft" }).click();
  await expect(page).toHaveURL(/\/console\/packages$/);
  expect(deleted).toBe(true);
});

test("someone without platform.catalogue.manage gets the refusal panel", async ({ page }) => {
  await mockCatalogue(page);
  await page.route(API, (r) =>
    r.fulfill({
      status: 403,
      json: { code: "permission.denied", detail: "You don't have permission to manage packages." },
    }),
  );
  await page.goto("/console/packages");
  await expect(
    page.getByRole("heading", { level: 1, name: "You can't manage packages and prices" }),
  ).toBeVisible();
});

test("editor fits a phone screen", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await mockCatalogue(page);
  await page.route(`${API}/growth`, (r) => r.fulfill({ status: 200, json: byCode("growth") }));
  await page.goto("/console/packages/growth");
  await expect(page.getByTestId("pricing-card")).toBeVisible();
  await expectNoHorizontalScroll(page);
});
