import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * G-01 tax codes. T12 — list: tabs, type badges, timeline, expired hidden by default.
 * The rules are tested on the real API in backend/tests/test_tax_api.py.
 */
const ORG = "acme";
const code = (over: Record<string, unknown>) => ({
  id: "c-on",
  code: "sales.ON.standard",
  version: 1,
  name: "HST 13 % (Ontario) on sales",
  name_i18n: {},
  side: "sales",
  type: "taxable",
  type_label: "Taxable",
  province: "ON",
  effective_from: "2010-07-01",
  effective_to: null,
  expired: false,
  archived_at: null,
  itc_restriction_pct: null,
  rate: "13",
  components: [{ id: "k1", key: "hst_on", name: "HST (ON)", kind: "hst", rate: "13" }],
  usage_count: 12,
  ...over,
});
const MB8 = code({
  id: "c-mb",
  code: "sales.MB.standard",
  name: "GST 5 % + RST 8 % (Manitoba) on sales",
  effective_from: "2013-07-01",
  effective_to: "2019-06-30",
  expired: true,
});

async function mockCodes(page: Page) {
  await mockCsrf(page);
  await page.route("**/api/v1/o/acme/tax/codes*", (r) => {
    const expired = r.request().url().includes("expired=1");
    return r.fulfill({ json: { results: expired ? [code({}), MB8] : [code({})] } });
  });
}

test("list: expired rates hidden by default, shown with the toggle", async ({ page }) => {
  await mockCodes(page);
  await page.goto(`/o/${ORG}/settings/tax-codes`);
  await expect(page.getByRole("heading", { name: "Tax codes", level: 1 })).toBeVisible();
  const table = page.getByRole("table", { name: "Sales tax codes" });
  await expect(table.getByText("HST 13 % (Ontario) on sales")).toBeVisible();
  await expect(table.getByText("Taxable")).toBeVisible();
  await expect(table.getByText("RST 8 %")).toHaveCount(0);
  await page.getByRole("switch", { name: "Show expired rates" }).click();
  await expect(table.getByText("GST 5 % + RST 8 % (Manitoba) on sales")).toBeVisible();
  await expect(table.getByText("Expired")).toBeVisible();
  await expectAccessible(page);
});
