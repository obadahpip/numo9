import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { CATALOGUE, profitAndLoss } from "./reports-fixtures";

/**
 * K-01-T13 — runner: a 12-column comparison renders without breaking the layout (the table
 * scrolls, the page doesn't); sticky parameter bar; Update and Enter run the report.
 */
async function mockRunner(page: Page, columns: number) {
  await mockCsrf(page);
  const runs: string[] = [];
  await page.route("**/api/v1/o/acme/reports", (r) => r.fulfill({ json: CATALOGUE }));
  await page.route("**/api/v1/o/acme/reports/profit-and-loss/run*", (r) => {
    runs.push(r.request().url());
    return r.fulfill({ json: profitAndLoss(columns) });
  });
  return runs;
}

for (const width of [1440, 1024, 768]) {
  test(`a 12-column comparison renders without layout break at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockRunner(page, 13);
    await page.goto("/o/acme/reports/profit-and-loss?compare=previous&periods=12");
    const table = page.getByRole("table", { name: "Profit and loss" });
    await expect(table.getByRole("columnheader")).toHaveCount(14);
    // The page never scrolls sideways: the table scrolls inside its region.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
    const region = page.getByRole("region", { name: "Profit and loss" });
    const scrolls = await region.evaluate((el) => el.scrollWidth > el.clientWidth);
    expect(scrolls).toBe(true);
    // The first column stays put while the figures scroll.
    const label = table.getByRole("rowheader", { name: "4000 · Sales" });
    const before = await label.boundingBox();
    await region.evaluate((el) => el.scrollBy({ left: 600 }));
    const after = await label.boundingBox();
    expect(after?.x).toBe(before?.x);
  });
}

test("Update and Enter run the report with the chosen options", async ({ page }) => {
  const runs = await mockRunner(page, 1);
  await page.goto("/o/acme/reports/profit-and-loss");
  await expect(page.getByRole("table", { name: "Profit and loss" })).toBeVisible();
  expect(runs[0]).toContain("preset=this_financial_year");
  await page.getByRole("group", { name: "Book" }).getByRole("button", { name: "Tax" }).click();
  await page.getByRole("button", { name: "Update" }).click();
  await expect.poll(() => runs.at(-1)).toContain("book=tax");
  await page.getByRole("textbox", { name: "Tracking" }).fill("region:east");
  await page.getByRole("textbox", { name: "Tracking" }).press("Enter");
  await expect.poll(() => runs.at(-1)).toContain("tracking=region%3Aeast");
  await expectAccessible(page);
});
