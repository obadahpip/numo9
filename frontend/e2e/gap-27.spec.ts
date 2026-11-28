import { expect, test, type Page, type Request } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";
import { CATALOGUE } from "./reports-fixtures";

/**
 * gap-27 (F-01-T16) — a new organisation with no bank account adds a chequing account, records
 * money in and spends from it with no import, feed, statement or reconciliation, and the Balance
 * Sheet shows it. The API is mocked here with the answers the real one gives for the same flow;
 * the real API and services are exercised end to end by backend/tests/test_banking_gap27.py
 * (same gap marker): Chequing 4,887.00 after a 5,000.00 deposit and a 113.00 HST-inclusive
 * spend, the input tax credit 13.00, total assets 4,900.00.
 */
const ORG = "acme";
const API = `**/api/v1/o/${ORG}`;
const BANK = "b2b2b2b2-0000-4000-8000-000000000027";
const OFFICE = "61006100-0000-4000-8000-000000000027";
const LOAN = "26002600-0000-4000-8000-000000000027";
const HST_P = "cccc0001-0000-4000-8000-000000000027";

const ledgerAccount = (
  id: string,
  code: string,
  name: string,
  type: string,
  subtype: string,
  tax = "",
) => ({
  id,
  code,
  name,
  description: "",
  type,
  type_label: type,
  subtype,
  subtype_label: subtype,
  parent: null,
  depth: 1,
  has_children: false,
  system_role: "",
  system_role_label: "",
  is_bank: subtype === "bank",
  gifi: null,
  require_contact: false,
  require_tracking: false,
  require_attachment: false,
  default_tax_key: tax,
  status: "active",
  archived_at: null,
  balance: { accounting: "0.00", tax: "0.00" },
});

const hst = {
  id: HST_P,
  code: "purchase.ON.standard",
  version: 1,
  name: "HST on purchases",
  name_i18n: {},
  side: "purchase",
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
    { id: "hst-c", key: "hst_on", name: "HST", kind: "hst", rate: "13", recoverable_pct: null },
  ],
  usage_count: 0,
};

const section = (label: string, level: number) => ({
  key: label,
  label,
  kind: "section",
  level,
  values: [],
  drill: null,
  notes: {},
});

const row = (label: string, value: string, kind = "row", level = 1) => ({
  key: label,
  label,
  kind,
  level,
  values: [value],
  drill: null,
  notes: {},
});

interface Books {
  bank: Record<string, unknown> | null;
  balance: number;
  itc: number;
  loan: number;
  posted: Record<string, unknown>[];
  noFeed: string[];
}

async function mockApi(page: Page): Promise<Books> {
  const books: Books = { bank: null, balance: 0, itc: 0, loan: 0, posted: [], noFeed: [] };
  await mockCsrf(page);
  page.on("request", (request: Request) => {
    if (/\/api\/v1\/.*(import|statement|reconcil|feed)/i.test(request.url())) {
      books.noFeed.push(request.url());
    }
  });
  const card = () => ({
    ...books.bank,
    ledger_balance: books.balance.toFixed(2),
    transaction_count: books.posted.length,
    last_activity: books.posted.length ? "2026-06-15" : null,
  });
  await page.route(`${API}/bank-accounts?*`, (r) =>
    r.fulfill({ json: { results: books.bank ? [card()] : [] } }),
  );
  await page.route(`${API}/bank-accounts`, async (r) => {
    const body = r.request().postDataJSON() as Record<string, string>;
    books.bank = {
      id: BANK,
      type: body.type,
      type_label: "Chequing",
      display_name: body.display_name,
      institution: body.institution ?? "",
      currency: "CAD",
      masked_number: "",
      ledger_account: { id: "gl-1001", code: "1001", name: body.display_name },
      ledger_balance: "0.00",
      statement_balance: null,
      statement_balance_date: null,
      is_reconciled_tracking: false,
      is_liability: false,
      archived_at: null,
      transaction_count: 0,
      last_activity: null,
    };
    await r.fulfill({ status: 201, json: books.bank });
  });
  await page.route(`${API}/bank-accounts/${BANK}/register*`, (r) =>
    r.fulfill({ json: { account: card(), results: [] } }),
  );
  await page.route(`${API}/accounts?*`, (r) =>
    r.fulfill({
      json: {
        count: 2,
        results: [
          ledgerAccount(LOAN, "2600", "Due to shareholder", "liability", "current_liability"),
          ledgerAccount(
            OFFICE,
            "6100",
            "Office supplies",
            "expense",
            "operating_expense",
            "purchase.ON.standard",
          ),
        ],
      },
    }),
  );
  await page.route(`${API}/contacts?*`, (r) =>
    r.fulfill({ json: { count: 0, next_offset: null, role_counts: {}, results: [] } }),
  );
  await page.route(`${API}/tax/codes?*`, (r) => r.fulfill({ json: { results: [hst] } }));
  await page.route(`${API}/bank-transactions/tax-default?*`, (r) =>
    r.fulfill({ json: { code: "purchase.ON.standard", name: "HST on purchases", taxes: [] } }),
  );
  await page.route(`${API}/documents/*/calculate`, (r) => r.fulfill({ status: 503, json: {} }));
  await page.route(`${API}/bank-transactions`, (r) => {
    const body = r.request().postDataJSON() as Record<string, unknown>;
    books.posted.push(body);
    const amount = Number((body.lines as { amount: string }[])[0]!.amount);
    if (body.kind === "receive") {
      books.balance += amount;
      books.loan += amount;
    } else {
      // Inclusive HST 13 %: 100.00 expense + 13.00 input tax credit out of the bank.
      books.balance -= amount;
      books.itc += Math.round((amount - amount / 1.13) * 100) / 100;
    }
    return r.fulfill({ status: 201, json: { id: `t${books.posted.length}` } });
  });
  await page.route(`${API}/reports`, (r) => r.fulfill({ json: CATALOGUE }));
  // The shape and figures the real run gives for this flow (test_banking_gap27.py).
  await page.route(`${API}/reports/balance-sheet/run*`, (r) => {
    const cash = books.balance.toFixed(2);
    const assets = (books.balance + books.itc).toFixed(2);
    const earnings = (books.balance + books.itc - books.loan).toFixed(2);
    return r.fulfill({
      json: {
        report: "balance_sheet",
        params: { as_of: "2026-06-15", book: "accounting" },
        columns: [{ key: "b0", label: "15 Jun 2026" }],
        rows: [
          section("Assets", 0),
          section("Current assets", 1),
          row("1001 · TD Business Chequing", cash, "row", 2),
          row("1400 · GST/HST receivable (ITCs)", books.itc.toFixed(2), "row", 2),
          row("Total current assets", assets, "total", 1),
          row("Total assets", assets, "total", 0),
          section("Liabilities", 0),
          section("Current liabilities", 1),
          row("2600 · Due to shareholder", books.loan.toFixed(2), "row", 2),
          row("Total current liabilities", books.loan.toFixed(2), "total", 1),
          row("Total liabilities", books.loan.toFixed(2), "total", 0),
          section("Equity", 0),
          row("Current year earnings", earnings, "row", 1),
          row("Total equity", earnings, "total", 0),
        ],
        totals: [row("Total liabilities and equity", assets, "total", 0)],
        alerts: [],
        header: {
          title: "Balance sheet",
          display_name: "Acme",
          legal_name: "",
          period_label: "As at 15 Jun 2026",
          status_label: "",
          basis_label: "Basis: Accrual (organisation default)",
          book_label: "Accounting book",
        },
        notes: "",
        unplaced_notes: [],
      },
    });
  });
  return books;
}

test.use({ viewport: { width: 1440, height: 900 } });

test("gap-27: new chequing, money spent with no import, on the Balance Sheet", async ({ page }) => {
  const books = await mockApi(page);

  // A new organisation: no bank account, nothing blocked, no feed asked for.
  await page.goto(`/o/${ORG}/banking`);
  await expect(page.getByRole("heading", { name: "No bank account yet" })).toBeVisible();
  await expect(page.getByText(/No bank feed is needed/)).toBeVisible();

  // 1. Add a chequing account.
  await page.getByRole("button", { name: "Add account" }).first().click();
  const sheet = page.getByRole("dialog", { name: "Add a bank account" });
  await sheet.getByRole("radio", { name: "Chequing" }).click();
  await sheet.getByLabel("Name").fill("TD Business Chequing");
  await page.getByRole("button", { name: "Add account" }).last().click();
  await expect(page.getByText("TD Business Chequing is ready.")).toBeVisible();

  // 2. Money in (the owner's deposit) and spend money — straight away.
  await page.goto(`/o/${ORG}/banking/receive?account=${BANK}`);
  await page.getByLabel("Amounts are").selectOption("no_tax");
  await page.getByRole("combobox", { name: "Account, line 1" }).click();
  await page.getByRole("option", { name: /Due to shareholder/ }).click();
  await page.getByRole("textbox", { name: "Amount, line 1" }).fill("5000");
  await page.getByRole("textbox", { name: "Amount, line 1" }).press("Tab");
  await page.getByRole("button", { name: "Record receipt" }).click();
  await expect(page).toHaveURL(`/o/${ORG}/banking/${BANK}`);

  await page.goto(`/o/${ORG}/banking/spend?account=${BANK}`);
  await page.getByLabel("Amounts are").selectOption("inclusive");
  await page.getByRole("combobox", { name: "Account, line 1" }).click();
  await page.getByRole("option", { name: /Office supplies/ }).click();
  await expect(page.getByRole("combobox", { name: "Tax code, line 1" })).toHaveValue(
    "HST on purchases",
  );
  await page.getByRole("textbox", { name: "Amount, line 1" }).fill("113");
  await page.getByRole("textbox", { name: "Amount, line 1" }).press("Tab");
  await page.getByRole("button", { name: "Record spend" }).click();
  await expect(page).toHaveURL(`/o/${ORG}/banking/${BANK}`);

  expect(books.posted).toHaveLength(2);
  expect(books.posted[0]).toMatchObject({
    kind: "receive",
    bank_account: BANK,
    tax_mode: "no_tax",
    lines: [{ account: LOAN, amount: "5000.00" }],
  });
  expect(books.posted[1]).toMatchObject({
    kind: "spend",
    bank_account: BANK,
    tax_mode: "inclusive",
    lines: [{ account: OFFICE, amount: "113.00", tax_code: "purchase.ON.standard" }],
  });

  // The banking home shows the ledger balance; reconciliation stays optional.
  await page.goto(`/o/${ORG}/banking`);
  const cardEl = page.getByRole("article", { name: "TD Business Chequing" });
  await expect(cardEl.getByText("$4,887.00")).toBeVisible();
  await expect(cardEl.getByText("Not reconciled — optional")).toBeVisible();

  // 3. The Balance Sheet shows it.
  await page.goto(`/o/${ORG}/reports/balance-sheet`);
  await expect(page.getByRole("row", { name: /1001 · TD Business Chequing/ })).toContainText(
    "4,887.00",
  );
  await expect(page.getByRole("row", { name: /Total assets/ })).toContainText("4,900.00");

  // Nothing ever asked for a feed, an import, a statement or a reconciliation.
  expect(books.noFeed).toEqual([]);
});
