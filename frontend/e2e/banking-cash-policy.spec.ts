import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * F-07-T08 — Banking settings: the negative-balance policy per account type, with an
 * explanation. Changing Chequing to Block takes effect on the next post: the mocked API answers
 * the spend from the rule it holds (the real API is tested in
 * backend/tests/test_banking_cash_policy_api.py), so the spend after saving meets the block panel
 * instead of the warning.
 */
const ORG = "acme";
const BANK = "b1b1b1b1-0000-4000-8000-000000000001";
const OFFICE = "61006100-0000-4000-8000-000000000002";

const policies = () => [
  {
    account_type: "chequing",
    label: "Chequing",
    standard: "warn",
    adviser: "warn",
    default: { standard: "warn", adviser: "warn" },
    explanation:
      "A chequing account can be overdrawn when you have an overdraft: by default you are warned and give a reason.",
  },
  {
    account_type: "cash",
    label: "Cash / petty cash",
    standard: "block",
    adviser: "warn",
    default: { standard: "block", adviser: "warn" },
    explanation: "Cash on hand can't be negative.",
  },
];

const bank = {
  id: BANK,
  type: "chequing",
  type_label: "Chequing",
  display_name: "TD Chequing",
  institution: "",
  currency: "CAD",
  masked_number: "",
  ledger_account: { id: "gl-bank", code: "1000", name: "TD Chequing" },
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
  default_tax_key: "",
  status: "active",
  archived_at: null,
  balance: { accounting: "0.00", tax: "0.00" },
};

test.use({ viewport: { width: 1440, height: 900 } });

test("changing Chequing to Block applies to the next spend", async ({ page }) => {
  const stored = policies();
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/bank-settings/cash-policies`, async (r) => {
    if (r.request().method() === "PUT") {
      const body = r.request().postDataJSON() as { policies: typeof stored };
      for (const change of body.policies) {
        const row = stored.find((p) => p.account_type === change.account_type);
        if (row) Object.assign(row, { standard: change.standard, adviser: change.adviser });
      }
    }
    return r.fulfill({ json: { policies: stored, actions: [] } });
  });
  await page.route(`**/api/v1/o/${ORG}/bank-accounts?*`, (r) =>
    r.fulfill({ json: { results: [bank] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/accounts?*`, (r) =>
    r.fulfill({ json: { count: 1, results: [office] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/contacts?*`, (r) =>
    r.fulfill({ json: { count: 0, next_offset: null, role_counts: {}, results: [] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/tax/codes?*`, (r) => r.fulfill({ json: { results: [] } }));
  await page.route(`**/api/v1/o/${ORG}/bank-transactions/tax-default?*`, (r) =>
    r.fulfill({ json: { code: "", name: "", taxes: [] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/documents/purchases/calculate`, (r) =>
    r.fulfill({ status: 503, json: {} }),
  );
  await page.route(`**/api/v1/o/${ORG}/bank-transactions`, (r) => {
    const block = stored[0]?.standard === "block";
    return r.fulfill({
      status: block ? 409 : 422,
      json: {
        code: block ? "ledger.journal.negative_cash" : "ledger.journal.override_reason_required",
        detail: "",
        adviser: !block,
        shortfalls: [
          {
            account: { id: "gl-bank", label: "1000 TD Chequing" },
            message: "TD Chequing would be −75.00 on 15 Jun 2026",
            action: block ? "block" : "warn",
          },
        ],
      },
    });
  });

  await page.goto(`/o/${ORG}/banking/settings`);
  await expect(page.getByRole("heading", { name: "Banking settings", level: 1 })).toBeVisible();
  const chequing = page.locator("[data-policy='chequing']");
  await expect(chequing).toContainText("overdraft");
  await expectAccessible(page);
  await page.getByLabel("Chequing: everyone else").selectOption("block");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Saved. The next posting follows the new rule.")).toBeVisible();

  await page.goto(`/o/${ORG}/banking/spend?account=${BANK}`);
  await page.getByRole("combobox", { name: "Account, line 1" }).click();
  await page.getByRole("option", { name: /Office supplies/ }).click();
  await page.getByRole("textbox", { name: "Amount, line 1" }).fill("75");
  await page.getByRole("textbox", { name: "Amount, line 1" }).press("Tab");
  await page.getByRole("button", { name: "Record spend" }).click();
  await expect(page.locator("[data-negative-balance='block']")).toContainText(
    "TD Chequing would be −75.00 on 15 Jun 2026",
  );
});
