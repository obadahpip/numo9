import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * F-02-T13 — the bank account page: statement lines with status filters and the "Uncoded" count
 * badge (= the count of UNCODED lines), a per-row actions menu, and the import history with
 * Undo. The counts and filters are tested on the real API in
 * backend/tests/test_banking_statement_lines_api.py.
 */
const ORG = "acme";
const ID = "6ca1b880-64f7-4053-80e3-0c3618895553";
const BASE = `**/api/v1/o/${ORG}/bank-accounts/${ID}`;
type Status = "uncoded" | "coded" | "matched" | "ignored";
const line = (id: string, status: Status, description: string, amount: string) => ({
  id,
  date: `2026-06-${id.padStart(2, "0")}`,
  amount,
  description,
  payee: "",
  reference: "",
  fitid: "",
  status,
  status_label: { uncoded: "Uncoded", coded: "Coded", matched: "Matched", ignored: "Ignored" }[
    status
  ],
  import: { id: "imp1", file_name: "rbc.csv" },
});
const LINES = [
  line("3", "uncoded", "Tim Hortons #1234", "-4.25"),
  line("4", "uncoded", "Tim Hortons #1234", "-4.25"),
  line("5", "coded", "PAYROLL DEPOSIT", "2500.00"),
  line("10", "matched", "CHEQUE", "-800.00"),
  line("15", "uncoded", "Hydro One", "-132.48"),
  line("16", "ignored", "Bank fee reversal", "0.00"),
];

async function mockPage(page: Page, state: { undone: boolean; urls: string[] }) {
  await mockCsrf(page);
  await page.route(`${BASE}/register*`, (r) =>
    r.fulfill({
      json: {
        account: {
          id: ID,
          type: "chequing",
          type_label: "Chequing",
          display_name: "RBC Chequing",
          institution: "RBC Royal Bank",
          currency: "CAD",
          masked_number: "",
          ledger_account: { id: "a1", code: "1000", name: "RBC Chequing" },
          ledger_balance: "0.00",
          statement_balance: "1563.27",
          statement_balance_date: "2026-06-30",
          is_reconciled_tracking: false,
          is_liability: false,
          archived_at: null,
          transaction_count: 0,
          last_activity: null,
        },
        results: [],
      },
    }),
  );
  await page.route(`${BASE}/statement-lines*`, async (r) => {
    state.urls.push(r.request().url());
    const all = state.undone ? [] : LINES;
    const wanted = new URL(r.request().url()).searchParams.get("status");
    const counts = { all: all.length, uncoded: 0, coded: 0, matched: 0, ignored: 0 };
    for (const l of all) counts[l.status] += 1;
    const results = wanted ? all.filter((l) => l.status === wanted) : all;
    await r.fulfill({ json: { counts, count: results.length, results } });
  });
  await page.route(`${BASE}/imports`, (r) =>
    r.fulfill({
      json: {
        results: [
          {
            id: "imp1",
            bank_account: ID,
            file_name: "rbc.csv",
            file_format: "csv",
            source: "file",
            status: state.undone ? "undone" : "committed",
            status_label: state.undone ? "Undone" : "Committed",
            mapping: { id: "m", name: "RBC Royal Bank" },
            counts: { total: 6, new: 6, duplicate: 0, error: 0 },
            created_at: "2026-07-01T12:00:00Z",
            created_by: { name: "Dana Lee" },
            committed_at: "2026-07-01T12:00:00Z",
            undone_at: null,
            in_use: 0,
            can_undo: !state.undone,
          },
        ],
      },
    }),
  );
  await page.route(`${BASE}/imports/imp1/undo`, async (r) => {
    state.undone = true;
    await r.fulfill({ json: { import: { id: "imp1", status: "undone" } } });
  });
}

test("the Uncoded badge equals the count of uncoded lines, with status filters", async ({
  page,
}) => {
  const state = { undone: false, urls: [] as string[] };
  await mockPage(page, state);
  await page.goto(`/o/${ORG}/banking/${ID}`);
  const uncoded = LINES.filter((l) => l.status === "uncoded").length;
  await expect(page.locator("[data-uncoded-badge]")).toHaveText(`Uncoded: ${uncoded}`);
  const table = page.getByRole("table", { name: "Statement lines" });
  await expect(table.locator("tbody tr")).toHaveCount(LINES.length);
  await page.getByRole("button", { name: `Uncoded (${uncoded})` }).click();
  await expect(table.locator("tbody tr")).toHaveCount(uncoded);
  await expect(table.locator('tbody tr[data-statement-line="uncoded"]')).toHaveCount(uncoded);
  await expect(page.locator("[data-uncoded-badge]")).toHaveText(`Uncoded: ${uncoded}`);
  expect(state.urls.some((u) => u.includes("status=uncoded"))).toBe(true);
  await page.getByRole("button", { name: "Matched (1)" }).click();
  await expect(table.locator("tbody tr")).toHaveCount(1);
  await expectAccessible(page);
});

test("row actions menu and undo from the import history", async ({ page }) => {
  const state = { undone: false, urls: [] as string[] };
  await mockPage(page, state);
  await page.goto(`/o/${ORG}/banking/${ID}`);
  const table = page.getByRole("table", { name: "Statement lines" });
  await table.getByRole("button", { name: /Actions for .* Hydro One/ }).click();
  await page.getByRole("button", { name: "Show the lines of this import" }).click();
  await expect(page.getByText("Showing the lines of rbc.csv.")).toBeVisible();
  expect(state.urls.some((u) => u.includes("import=imp1"))).toBe(true);
  await expectAccessible(page);

  const history = page.getByRole("table", { name: "Import history" });
  await expect(history).toContainText("rbc.csv");
  await history.getByRole("button", { name: "Undo the import of rbc.csv" }).click();
  await expect(page.getByText("rbc.csv undone: its lines were removed.")).toBeVisible();
  await expect(page.locator("[data-uncoded-badge]")).toHaveText("Uncoded: 0");
  await expect(history.getByText("Undone")).toBeVisible();
});
