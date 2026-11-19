import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * C-01-T11 — chart tree table (tabs, indented sub-accounts, collapse, inline renumber with the
 * server's conflict message, bulk archive with each account's outcome) and C-01-T12 — account
 * drawer (balances per book, posting rules, GIFI search by number and description, save). The
 * rules are tested on the real API in backend/tests/test_ledger_accounts_api.py.
 */
const ORG = "acme";
const row = (over: Record<string, unknown>) => ({
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
  gifi: { code: "8811", description: "Office stationery and supplies" },
  require_contact: false,
  require_tracking: false,
  require_attachment: false,
  default_tax_key: "",
  status: "active",
  archived_at: null,
  balance: { accounting: "0.00", tax: "0.00" },
  ...over,
});
const ACCOUNTS = [
  row({
    id: "a1",
    code: "1000",
    name: "Chequing",
    type: "asset",
    type_label: "Asset",
    subtype: "bank",
    subtype_label: "Bank",
    gifi: { code: "1001", description: "Cash and deposits" },
    balance: { accounting: "2500.00", tax: "2500.00" },
  }),
  row({
    id: "a2",
    code: "1100",
    name: "Accounts receivable",
    type: "asset",
    type_label: "Asset",
    subtype: "current_asset",
    subtype_label: "Current asset",
    system_role: "ar",
    system_role_label: "Accounts receivable",
  }),
  row({ id: "e1", code: "6000", name: "Office", has_children: true }),
  row({ id: "e2", code: "6010", name: "Stationery", parent: "e1", depth: 2 }),
];

async function mockChart(page: Page) {
  await mockCsrf(page);
  await page.route("**/api/v1/o/acme/accounts?*", (r) =>
    r.fulfill({ json: { results: ACCOUNTS, count: ACCOUNTS.length } }),
  );
}

test("tree, tabs, collapse and inline renumber with the conflict message", async ({ page }) => {
  await mockChart(page);
  await page.route("**/api/v1/o/acme/accounts/e2/renumber", async (r) => {
    const { code } = r.request().postDataJSON() as { code: string };
    if (code === "1000") {
      await r.fulfill({
        status: 400,
        json: {
          code: "ledger.account.code_taken",
          detail: "1000 Chequing already has the code 1000.",
        },
      });
    } else {
      await r.fulfill({ json: { ...ACCOUNTS[3], code } });
    }
  });
  await page.goto(`/o/${ORG}/accounting/chart-of-accounts`);
  await expect(page.getByRole("heading", { name: "Chart of accounts", level: 1 })).toBeVisible();
  const grid = page.getByRole("grid", { name: "Accounts" });
  await expect(grid.getByRole("button", { name: "Stationery" })).toBeVisible();
  await expect(grid.getByText("System: Accounts receivable")).toBeVisible();

  await grid.getByRole("button", { name: "Hide sub-accounts of Office" }).click();
  await expect(grid.getByRole("button", { name: "Stationery" })).toHaveCount(0);
  await grid.getByRole("button", { name: "Show sub-accounts of Office" }).click();

  await page.getByRole("tab", { name: /Assets/ }).click();
  await expect(grid.getByRole("button", { name: "Office" })).toHaveCount(0);
  await page.getByRole("tab", { name: /All/ }).click();

  await page.getByRole("button", { name: "Change code 6010" }).click();
  const field = page.getByLabel("New code for Stationery");
  await field.fill("1000");
  await field.press("Enter");
  await expect(page.getByRole("alert").filter({ hasText: "already" })).toContainText(
    "already has the code 1000",
  );
  await field.fill("6020");
  await field.press("Enter");
  await expect(page.getByText("Stationery is now 6020.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Change code 6020" })).toBeVisible();
  await expectAccessible(page);
});

test("bulk archive reports every account's outcome", async ({ page }) => {
  await mockChart(page);
  await page.route("**/api/v1/o/acme/accounts/bulk", (r) =>
    r.fulfill({
      json: {
        action: "archive",
        done: 1,
        failed: 1,
        results: [
          { id: "e2", code: "6010", ok: true },
          {
            id: "a1",
            code: "1000",
            ok: false,
            detail: "1000 Chequing has a balance of 2,500.00 in the accounting book.",
          },
        ],
      },
    }),
  );
  await page.goto(`/o/${ORG}/accounting/chart-of-accounts`);
  await page.getByRole("checkbox", { name: "Select 1000 Chequing" }).click();
  await page.getByRole("checkbox", { name: "Select 6010 Stationery" }).click();
  await page.getByRole("button", { name: "Archive", exact: true }).click();
  await expect(page.getByText("1 account done, 1 failed.")).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "1000:" })).toContainText(
    "1000: 1000 Chequing has a balance",
  );
});

test("account drawer: balances, rules, GIFI search and save", async ({ page }) => {
  await mockChart(page);
  let saved: Record<string, unknown> = {};
  await page.route("**/api/v1/o/acme/gifi?*", (r) => {
    const q = new URL(r.request().url()).searchParams.get("q") ?? "";
    const all = [
      { code: "1001", description: "Cash and deposits", section: "current_assets" },
      { code: "1002", description: "Cash and deposits — foreign", section: "current_assets" },
    ];
    return r.fulfill({
      json: {
        results: all.filter((g) => g.code.startsWith(q) || g.description.includes(q)),
      },
    });
  });
  await page.route("**/api/v1/o/acme/accounts/a1", async (r) => {
    saved = r.request().postDataJSON() as Record<string, unknown>;
    await r.fulfill({
      json: {
        ...ACCOUNTS[0],
        require_contact: true,
        gifi: { code: "1002", description: "Cash and deposits — foreign" },
      },
    });
  });
  await page.goto(`/o/${ORG}/accounting/chart-of-accounts`);
  await page.getByRole("button", { name: "Chequing" }).click();
  const drawer = page.getByRole("dialog", { name: "1000 Chequing" });
  await expect(drawer.locator("[data-balance=accounting]")).toHaveText("$2,500.00");
  await expect(drawer.getByText("1001 — Cash and deposits")).toBeVisible();
  await drawer.getByLabel("Search GIFI by number or description").fill("1002");
  await drawer.getByRole("button", { name: "Use 1002 — Cash and deposits — foreign" }).click();
  await drawer.getByLabel("Search GIFI by number or description").fill("deposits");
  await expect(drawer.getByRole("button", { name: /Use 1001/ })).toBeVisible();
  await drawer.getByRole("checkbox", { name: "Every line needs a contact" }).click();
  await expectAccessible(page);
  await drawer.getByRole("button", { name: "Save account" }).click();
  await expect(drawer.getByText("Saved")).toBeVisible();
  expect(saved).toMatchObject({ gifi: "1002", require_contact: true });
});
