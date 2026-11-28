import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * F-07-T07 — the inline negative-balance panel (design system, not a modal) in the spend form:
 * a WARN shows the shortfall, the remedy button and the reason field, and the reason is sent on
 * the next try; a BLOCK names who can override and keeps saving off. (The journal form's panel is
 * checked in journal-controls.spec.ts; the policy itself on the real API in
 * backend/tests/test_banking_cash_hook.py and test_banking_override_reason.py.)
 */
const ORG = "acme";
const PETTY = "b1b1b1b1-0000-4000-8000-000000000003";
const OFFICE = "61006100-0000-4000-8000-000000000002";

const petty = {
  id: PETTY,
  type: "cash",
  type_label: "Cash / petty cash",
  display_name: "Petty Cash",
  institution: "",
  currency: "CAD",
  masked_number: "",
  ledger_account: { id: "gl-petty", code: "1010", name: "Petty Cash" },
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

const SHORTFALL = {
  account: { id: "gl-petty", label: "1010 Petty Cash" },
  message: "Petty Cash would be −994.17 on 15 Jun 2026",
};

async function mockApi(
  page: Page,
  answers: { status: number; json: unknown }[],
): Promise<Record<string, unknown>[]> {
  const posted: Record<string, unknown>[] = [];
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/bank-accounts?*`, (r) =>
    r.fulfill({ json: { results: [petty] } }),
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
    posted.push(r.request().postDataJSON() as Record<string, unknown>);
    const answer = answers.shift() ?? { status: 201, json: { id: "t1" } };
    return r.fulfill(answer);
  });
  await page.route(`**/api/v1/o/${ORG}/bank-accounts/${PETTY}*`, (r) =>
    r.fulfill({ status: 404, json: {} }),
  );
  return posted;
}

async function spend(page: Page) {
  await page.goto(`/o/${ORG}/banking/spend?account=${PETTY}`);
  await expect(page.getByRole("heading", { name: "Spend money", level: 1 })).toBeVisible();
  await page.getByRole("combobox", { name: "Account, line 1" }).click();
  await page.getByRole("option", { name: /Office supplies/ }).click();
  await page.getByRole("textbox", { name: "Amount, line 1" }).fill("994.17");
  await page.getByRole("textbox", { name: "Amount, line 1" }).press("Tab");
  await page.getByRole("button", { name: "Record spend" }).click();
}

test.use({ viewport: { width: 1440, height: 900 } });

test("warn: inline panel with the reason, sent with the spend", async ({ page }) => {
  const posted = await mockApi(page, [
    {
      status: 422,
      json: {
        code: "ledger.journal.override_reason_required",
        detail: "",
        adviser: true,
        shortfalls: [{ ...SHORTFALL, action: "warn" }],
      },
    },
  ]);
  await spend(page);
  const panel = page.locator("[data-negative-balance='warn']");
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("Petty Cash would be −994.17 on 15 Jun 2026");
  await expect(page.getByRole("dialog")).toHaveCount(0); // inline, not a modal
  await expect(panel.getByRole("button", { name: "Record money coming in" })).toBeVisible();
  const save = page.getByRole("button", { name: "Record spend" });
  await expect(save).toBeDisabled();
  await panel.getByLabel("Reason for saving it anyway").fill("Owner tops the float up Monday.");
  await expectAccessible(page);
  await save.click();
  await expect(page).toHaveURL(`/o/${ORG}/banking/${PETTY}`);
  expect(posted).toHaveLength(2);
  expect(posted[1]).toMatchObject({ override_reason: "Owner tops the float up Monday." });
});

test("block: who can override, no reason field, saving stays off", async ({ page }) => {
  const posted = await mockApi(page, [
    {
      status: 409,
      json: {
        code: "ledger.journal.negative_cash",
        detail: "",
        adviser: false,
        shortfalls: [{ ...SHORTFALL, action: "block" }],
      },
    },
  ]);
  await spend(page);
  const panel = page.getByRole("alert").filter({ hasText: "Petty Cash would be" });
  await expect(panel).toHaveAttribute("data-negative-balance", "block");
  await expect(panel).toContainText("Who can override: your adviser");
  await expect(panel.getByLabel("Reason for saving it anyway")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Record spend" })).toBeDisabled();
  await expectAccessible(page);
  await panel.getByRole("button", { name: "Record money coming in" }).click();
  await expect(page).toHaveURL(`/o/${ORG}/banking/receive?account=${PETTY}`);
  expect(posted).toHaveLength(1);
});
