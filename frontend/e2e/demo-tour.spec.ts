import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { entitlements, mockEntitlements } from "./entitlements-fixtures";

/**
 * U-07-T13 guided demo tour: opens by itself on the first visit, six steps (Next/Back), Finish
 * completes it, Skip and Esc close it, the dismissal is remembered across visits, the demo bar
 * reopens it; axe finds nothing.
 */
const ORG = "acme";

async function mockDemo(page: Page) {
  await mockCsrf(page);
  await mockEntitlements(page, ORG, entitlements({ reason: "demo", status: "demo" }));
  await page.route("**/api/v1/o/acme/contacts?*", (r) =>
    r.fulfill({
      json: {
        results: [],
        count: 0,
        next_offset: null,
        role_counts: { customer: 0, supplier: 0, contractor: 0, government_agency: 0, employee: 0 },
      },
    }),
  );
}

test("tour completes in six steps and is remembered", async ({ page }) => {
  await mockDemo(page);
  await page.goto(`/o/${ORG}/contacts`);
  const tour = page.getByRole("dialog", { name: /\(1 of 6\)/ });
  await expect(tour).toBeVisible();
  await expect(tour.getByRole("heading")).toHaveText("Welcome (1 of 6)");
  await expectAccessible(page);
  for (let step = 2; step <= 6; step += 1) {
    await page.getByRole("button", { name: "Next" }).click();
    await expect(
      page.getByRole("dialog", { name: new RegExp(`\\(${step} of 6\\)`) }),
    ).toBeVisible();
  }
  await page.getByRole("button", { name: "Back" }).click();
  await expect(page.getByRole("dialog", { name: /\(5 of 6\)/ })).toBeVisible();
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Finish" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await expect(page.locator("[data-demo-bar]")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Take the tour" }).click();
  await expect(page.getByRole("dialog", { name: /\(1 of 6\)/ })).toBeVisible();
});

test("Esc closes the tour and skip is remembered", async ({ page }) => {
  await mockDemo(page);
  await page.goto(`/o/${ORG}/contacts`);
  await expect(page.getByRole("dialog", { name: /\(1 of 6\)/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("numo9.demoTour.dismissed"))).toBe("1");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.getByRole("button", { name: "Skip the tour" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await expect(page.locator("[data-demo-bar]")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
