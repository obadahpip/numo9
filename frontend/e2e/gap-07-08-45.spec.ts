import { expect, test } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";

/**
 * gap-07, gap-08, gap-45 (G-01-T17) on the tax codes screen: the Sales tab never lists purchase
 * codes (gap-07); ended rates are hidden on a later date and shown greyed only with the toggle
 * (gap-08); zero-rated, exempt and out-of-scope are distinct types and purchase codes show their
 * claimable ITC % (gap-45). The API half is backend/tests/test_tax_gaps.py.
 */
const ORG = "acme";
const row = (over: Record<string, unknown>) => ({
  id: String(over.code),
  version: 1,
  name_i18n: {},
  type: "taxable",
  type_label: "Taxable",
  province: "",
  effective_from: "1991-01-01",
  effective_to: null,
  expired: false,
  archived_at: null,
  itc_restriction_pct: null,
  rate: "0",
  components: [],
  usage_count: 0,
  ...over,
});
const LIVE = [
  row({ code: "sales.ON.standard", name: "HST 13 % (Ontario) on sales", side: "sales" }),
  row({
    code: "sales.zero_rated",
    name: "Zero-rated on sales (0 %)",
    side: "sales",
    type: "zero_rated",
  }),
  row({ code: "sales.exempt", name: "Exempt on sales", side: "sales", type: "exempt" }),
  row({
    code: "sales.out_of_scope",
    name: "Out of scope on sales",
    side: "sales",
    type: "out_of_scope",
  }),
  row({
    code: "purchase.ON.standard.itc50",
    name: "HST 13 % (Ontario) on purchases, 50 % ITC",
    side: "purchase",
    itc_restriction_pct: "50",
  }),
];
const ENDED = row({
  code: "sales.NS.standard",
  name: "HST 15 % (Nova Scotia) on sales",
  side: "sales",
  effective_to: "2025-03-31",
  expired: true,
});

test("gap-07 / gap-08 / gap-45: sides never mix, ended rates hidden, distinct types", async ({
  page,
}) => {
  await mockCsrf(page);
  await page.route("**/api/v1/o/acme/tax/codes*", (r) =>
    r.fulfill({
      json: { results: r.request().url().includes("expired=1") ? [...LIVE, ENDED] : LIVE },
    }),
  );
  await page.goto(`/o/${ORG}/settings/tax-codes`);
  const sales = page.getByRole("table", { name: "Sales tax codes" });
  await expect(sales.getByText("HST 13 % (Ontario) on sales")).toBeVisible();
  await expect(sales.getByText(/on purchases/)).toHaveCount(0); // gap-07
  await expect(sales.getByText("HST 15 % (Nova Scotia) on sales")).toHaveCount(0); // gap-08
  for (const type of ["Zero-rated", "Exempt", "Out of scope"]) {
    await expect(sales.getByText(type, { exact: true })).toBeVisible(); // gap-45
  }
  await page.getByRole("switch", { name: "Show expired rates" }).click();
  await expect(sales.getByText("HST 15 % (Nova Scotia) on sales")).toBeVisible();
  await expect(sales.locator("[data-expired]")).toHaveCount(1);
  await page.getByRole("tab", { name: /Purchases/ }).click();
  const purchases = page.getByRole("table", { name: "Purchases tax codes" });
  await expect(purchases.getByText("50 % claimable")).toBeVisible();
  await expect(purchases.getByText(/on sales/)).toHaveCount(0);
});
