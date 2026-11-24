import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * F-01-T10 — spend money from a brand-new chequing account: the D-01 grid in bank mode, purchase
 * tax codes only, the account's default code filled in, and the transaction posted straight away
 * — no feed, import or reconciliation (gap-27). Posting itself is tested on the real API in
 * backend/tests/test_banking_tax_defaults.py.
 */
const ORG = "acme";
const BANK = "b1b1b1b1-0000-4000-8000-000000000001";
const OFFICE = "61006100-0000-4000-8000-000000000002";
const HST_P = "cccc0001-0000-4000-8000-000000000001";
const HST_S = "cccc0002-0000-4000-8000-000000000002";

const bank = {
  id: BANK,
  type: "chequing",
  type_label: "Chequing",
  display_name: "TD Business Chequing",
  institution: "TD Canada Trust",
  currency: "CAD",
  masked_number: "",
  ledger_account: { id: "gl-bank", code: "1000", name: "TD Business Chequing" },
  ledger_balance: "0.00",
  statement_balance: null,
  statement_balance_date: null,
  is_reconciled_tracking: false,
  is_liability: false,
  archived_at: null,
  transaction_count: 0,
  last_activity: null,
};

const office = {
  id: OFFICE,
  code: "6100",
  name: "Office supplies",
  description: "",
  type: "expense",
  type_label: "Expense",
  subtype: "operating_expense",
  subtype_label: "Operating expense",
  parent: null,
  depth: 1,
  has_children: false,
  system_role: "",
  system_role_label: "",
  is_bank: false,
  gifi: null,
  require_contact: false,
  require_tracking: false,
  require_attachment: false,
  default_tax_key: "purchase.ON.standard",
  status: "active",
  archived_at: null,
  balance: { accounting: "0.00", tax: "0.00" },
};

const code = (id: string, key: string, name: string, side: string) => ({
  id,
  code: key,
  version: 1,
  name,
  name_i18n: {},
  side,
  type: "taxable",
  type_label: "Taxable",
  province: "ON",
  effective_from: "2016-07-01",
  effective_to: null,
  expired: false,
  archived_at: null,
  itc_restriction_pct: null,
  rate: "13",
  components: [
    { id: `${id}c`, key: "hst_on", name: "HST", kind: "hst", rate: "13", recoverable_pct: null },
  ],
  usage_count: 0,
});

async function mockApi(page: Page): Promise<Record<string, unknown>[]> {
  const posted: Record<string, unknown>[] = [];
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/bank-accounts?*`, (r) =>
    r.fulfill({ json: { results: [bank] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/accounts?*`, (r) =>
    r.fulfill({ json: { count: 1, results: [office] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/contacts?*`, (r) =>
    r.fulfill({ json: { count: 0, next_offset: null, role_counts: {}, results: [] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/tax/codes?*`, (r) =>
    r.fulfill({
      json: {
        results: [
          code(HST_P, "purchase.ON.standard", "HST on purchases", "purchase"),
          code(HST_S, "sales.ON.standard", "HST on sales", "sales"),
        ],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/bank-transactions/tax-default?*`, (r) =>
    r.fulfill({ json: { code: "purchase.ON.standard", name: "HST on purchases", taxes: [] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/documents/purchases/calculate`, (r) =>
    r.fulfill({ status: 503, json: {} }),
  );
  await page.route(`**/api/v1/o/${ORG}/bank-transactions`, (r) => {
    posted.push(r.request().postDataJSON() as Record<string, unknown>);
    return r.fulfill({ status: 201, json: { id: "t1" } });
  });
  await page.route(`**/api/v1/o/${ORG}/bank-accounts/${BANK}*`, (r) =>
    r.fulfill({ status: 404, json: {} }),
  );
  return posted;
}

test.use({ viewport: { width: 1440, height: 900 } });

test("spend money: purchase codes only, posted with no import", async ({ page }) => {
  const posted = await mockApi(page);
  await page.goto(`/o/${ORG}/banking/spend?account=${BANK}`);
  await expect(page.getByRole("heading", { name: "Spend money", level: 1 })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Qty" })).toHaveCount(0);

  await page.getByRole("combobox", { name: "Account, line 1" }).click();
  await page.getByRole("option", { name: /Office supplies/ }).click();
  const tax = page.getByRole("combobox", { name: "Tax code, line 1" });
  await expect(tax).toHaveValue("HST on purchases");
  await tax.click();
  await expect(page.getByRole("listbox")).not.toContainText("HST on sales");
  await page.keyboard.press("Escape");

  await page.getByRole("textbox", { name: "Amount, line 1" }).fill("100");
  await page.getByRole("textbox", { name: "Amount, line 1" }).press("Tab");
  // The mirror's figures while the server is away: HST 13.00 on 100.00.
  await expect(page.locator("[data-total='total']")).toContainText("$113.00");
  await expectAccessible(page);

  await page.getByRole("button", { name: "Record spend" }).click();
  await expect(page).toHaveURL(`/o/${ORG}/banking/${BANK}`);
  expect(posted).toHaveLength(1);
  expect(posted[0]).toMatchObject({
    kind: "spend",
    bank_account: BANK,
    lines: [{ account: OFFICE, amount: "100.00", tax_code: "purchase.ON.standard" }],
  });
});
