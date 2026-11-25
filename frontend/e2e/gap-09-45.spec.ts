import { expect, test } from "@playwright/test";

import { mockBillEditor, SUPPLIER } from "./bills-fixtures";

/**
 * gap-09 / gap-45 (G-02-T10): the bill editor's tax cell is filled for the person (no pick per
 * line) with the reason on the "auto" chip — in French too; purchases default from the expense
 * account's code. Server side: backend/tests/test_tax_gaps_place_of_supply.py.
 */
const ORG = "acme";
const HST = {
  id: "cccc0001-0000-4000-8000-000000000001",
  code: "purchase.ON.standard",
  version: 1,
  name: "HST on purchases",
  side: "purchase",
  type: "taxable",
  province: "ON",
  effective_from: "2016-07-01",
  effective_to: null,
  expired: false,
  archived_at: null,
  rate: "13",
  components: [
    { id: "c1", key: "hst_on", name: "HST", kind: "hst", rate: "13", recoverable_pct: null },
  ],
};

for (const [locale, why] of [
  ["en-CA", "The account's default tax code"],
  ["fr-CA", "Le code de taxe par défaut du compte"],
] as const) {
  test(`gap-09 / gap-45: the code is chosen for the line, with its reason (${locale})`, async ({
    browser,
    baseURL,
  }) => {
    const context = await browser.newContext();
    await context.addCookies([{ name: "numo9_locale", value: locale, url: baseURL! }]);
    const page = await context.newPage();
    await mockBillEditor(page);
    await page.route(`**/api/v1/o/${ORG}/tax/codes*`, (r) =>
      r.fulfill({ json: { results: [HST] } }),
    );
    await page.route(`**/api/v1/o/${ORG}/tax/resolve`, (r) => {
      const body = r.request().postDataJSON() as { lines: unknown[] };
      return r.fulfill({
        json: {
          lines: body.lines.map(() => ({
            key: HST.code,
            tax_code: { id: HST.id, code: HST.code, name: HST.name, version: 1 },
            source: "account",
            auto: true,
            explanation: "tax.pos.account",
            params: {},
            province: "",
            flags: [],
            warnings: [],
          })),
        },
      });
    });
    await page.goto(`/o/${ORG}/purchases/bills/new`);
    await page.locator("select").first().selectOption(SUPPLIER);
    await expect(page.locator("[data-tax-auto]")).toHaveCount(1);
    await expect(page.locator("[data-tax-why]")).toHaveAttribute("aria-description", why);
    await context.close();
  });
}
