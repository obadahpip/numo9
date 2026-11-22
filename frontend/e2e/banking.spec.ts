import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * F-01 banking screens. T08 — home: card balance = API ledger balance, liability "owed",
 * optional reconciliation chip, empty state with 0 accounts. The balances and rules are tested
 * on the real API in backend/tests/test_banking_api.py.
 */
const ORG = "acme";
const account = (over: Record<string, unknown>) => ({
  id: "b1",
  type: "chequing",
  type_label: "Chequing",
  display_name: "TD Business Chequing",
  institution: "TD Canada Trust",
  currency: "CAD",
  masked_number: "•••• 4821",
  ledger_account: { id: "a1", code: "1000", name: "TD Business Chequing" },
  ledger_balance: "12450.30",
  statement_balance: null,
  statement_balance_date: null,
  is_reconciled_tracking: false,
  is_liability: false,
  archived_at: null,
  transaction_count: 4,
  last_activity: "2026-06-15",
  ...over,
});

async function mockAccounts(page: Page, results: unknown[]) {
  await mockCsrf(page);
  await page.route("**/api/v1/o/acme/bank-accounts?*", (r) => r.fulfill({ json: { results } }));
}

test("home: cards show the ledger balance and the optional reconciliation chip", async ({
  page,
}) => {
  await mockAccounts(page, [
    account({}),
    account({
      id: "b2",
      type: "credit_card",
      display_name: "Visa Business",
      ledger_balance: "-1200.00",
      is_liability: true,
    }),
  ]);
  await page.goto(`/o/${ORG}/banking`);
  await expect(page.getByRole("heading", { name: "Banking", level: 1 })).toBeVisible();
  const td = page.getByRole("article", { name: "TD Business Chequing" });
  await expect(td.getByText("$12,450.30")).toBeVisible();
  await expect(td.getByText("Not reconciled — optional")).toBeVisible();
  await expect(
    page.getByRole("article", { name: "Visa Business" }).getByText("$1,200.00 owed"),
  ).toBeVisible();
  await expectAccessible(page);
});

test("home: empty state with no account", async ({ page }) => {
  await mockAccounts(page, []);
  await page.goto(`/o/${ORG}/banking`);
  await expect(page.getByRole("heading", { name: "No bank account yet" })).toBeVisible();
  await expect(page.getByText(/No bank feed is needed/)).toBeVisible();
});

test("add account: side-sheet creates a usable account in one step", async ({ page }) => {
  await mockCsrf(page);
  let results: unknown[] = [];
  await page.route("**/api/v1/o/acme/bank-accounts?*", (r) => r.fulfill({ json: { results } }));
  await page.route("**/api/v1/o/acme/bank-accounts", async (r) => {
    const body = r.request().postDataJSON() as Record<string, string>;
    const made = account({ id: "new", display_name: body.display_name, type: body.type });
    results = [made];
    await r.fulfill({ status: 201, json: made });
  });
  const started = Date.now();
  await page.goto(`/o/${ORG}/banking`);
  await page.getByRole("button", { name: "Add account" }).first().click();
  const sheet = page.getByRole("dialog", { name: "Add a bank account" });
  await sheet.getByRole("radio", { name: "Cash / petty cash" }).click();
  await expect(sheet.getByText("Notes and coins on hand")).toBeVisible();
  await sheet.getByLabel("Name").fill("Petty Cash");
  await page.getByRole("button", { name: "Add account" }).last().click();
  await expect(page.getByText("Petty Cash is ready.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Record a transaction" })).toHaveAttribute(
    "href",
    `/o/${ORG}/banking/spend?account=new`,
  );
  await expect(page.getByRole("article", { name: "Petty Cash" })).toBeVisible();
  expect(Date.now() - started).toBeLessThan(30_000);
});
