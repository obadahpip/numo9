import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * F-02-T12 — statement import wizard: Upload (drag-and-drop) → Map → Preview → Confirm.
 * Usability task "import RBC CSV" done in < 90 s; the detection message, the mapping grid (first 5
 * rows, a dropdown per column), the preview tabs with counts and "Skip errors", the result toast
 * with Undo. The parsing, detection and import rules are tested on the real API in
 * backend/tests/test_banking_statement_*.py.
 */
const ORG = "acme";
const ID = "6ca1b880-64f7-4053-80e3-0c3618895553";
const BASE = `**/api/v1/o/${ORG}/bank-accounts/${ID}`;
const RBC = [
  [
    "Account Type",
    "Account Number",
    "Transaction Date",
    "Cheque Number",
    "Description 1",
    "Description 2",
    "CAD$",
    "USD$",
  ],
  ["Chequing", "01234-5678901", "6/3/2026", "", "Tim Hortons #1234", "Toronto ON", "-4.25", ""],
  ["Chequing", "01234-5678901", "6/3/2026", "", "Tim Hortons #1234", "Toronto ON", "-4.25", ""],
  ["Chequing", "01234-5678901", "6/5/2026", "", "PAYROLL DEPOSIT", "ACME INC", "2500.00", ""],
  ["Chequing", "01234-5678901", "6/10/2026", "123", "CHEQUE", "", "-800.00", ""],
  ["Chequing", "01234-5678901", "6/15/2026", "", "Hydro One", "Bill payment", "-132.48", ""],
  ["Chequing", "01234-5678901", "13/40/2026", "", "Broken", "", "-1.00", ""],
];
const LAYOUT = {
  columns: [
    "ignore",
    "ignore",
    "date",
    "reference",
    "description",
    "description",
    "amount",
    "ignore",
  ],
  date_format: "MM/DD/YYYY",
  sign: "signed",
  has_header: true,
  skip_rows: 0,
  decimal_separator: ".",
};
const importRow = (over: Record<string, unknown> = {}) => ({
  id: "imp1",
  bank_account: ID,
  file_name: "rbc.csv",
  file_format: "csv",
  source: "file",
  status: "pending",
  status_label: "Pending",
  mapping: { id: "m-rbc", name: "RBC Royal Bank" },
  counts: { total: 6, new: 0, duplicate: 0, error: 0 },
  created_at: "2026-07-01T12:00:00Z",
  created_by: { name: "Dana Lee" },
  committed_at: null,
  undone_at: null,
  ...over,
});
const previewLine = (row: number, status: string, over: Record<string, unknown> = {}) => ({
  row,
  date: "2026-06-03",
  amount: "-4.25",
  description: "Tim Hortons #1234 Toronto ON",
  payee: "",
  reference: "",
  fitid: "",
  status,
  reasons: [],
  ...over,
});
const PREVIEW = {
  import: importRow(),
  counts: { total: 6, new: 5, duplicate: 0, error: 1 },
  balances: { opening: null, closing: null },
  warnings: [],
  layout: LAYOUT,
  count: 6,
  results: [
    previewLine(2, "new"),
    previewLine(3, "new"),
    previewLine(4, "new", { amount: "2500.00", description: "PAYROLL DEPOSIT ACME INC" }),
    previewLine(5, "new", { amount: "-800.00", description: "CHEQUE", reference: "123" }),
    previewLine(6, "new", { amount: "-132.48", description: "Hydro One Bill payment" }),
    previewLine(7, "error", {
      date: null,
      amount: null,
      description: "Broken",
      reasons: [
        {
          code: "banking.statement.row.date_format",
          message:
            "Row 7: date '13/40/2026' doesn't match MM/DD/YYYY. Choose the date format your bank uses on the Map step, or correct the row.",
        },
      ],
    }),
  ],
};

async function mockApi(page: Page, calls: string[]) {
  await mockCsrf(page);
  await page.route(BASE, (r) =>
    r.fulfill({
      json: {
        id: ID,
        type: "chequing",
        type_label: "Chequing",
        display_name: "RBC Chequing",
        institution: "RBC Royal Bank",
        currency: "CAD",
        masked_number: "",
        ledger_account: { id: "a1", code: "1000", name: "RBC Chequing" },
        ledger_balance: "0.00",
        statement_balance: null,
        statement_balance_date: null,
        is_reconciled_tracking: false,
        is_liability: false,
        archived_at: null,
        transaction_count: 0,
        last_activity: null,
      },
    }),
  );
  await page.route(`${BASE}/imports`, async (r) => {
    calls.push(`upload:${r.request().headers()["content-type"]?.split(";")[0]}`);
    await r.fulfill({
      status: 201,
      json: {
        import: importRow(),
        format: "csv",
        encoding: "utf-8",
        delimiter: ",",
        warnings: [],
        tabular: true,
        lines: 6,
        sample: { width: 8, rows: RBC.map((cells, i) => ({ row: i + 1, cells })) },
        layout: LAYOUT,
        mapping: {
          id: "m-rbc",
          name: "RBC Royal Bank",
          institution: "RBC Royal Bank",
          builtin: true,
          layout: LAYOUT,
          score: 1,
        },
        mappings: [
          {
            id: "m-rbc",
            name: "RBC Royal Bank",
            institution: "RBC Royal Bank",
            builtin: true,
            layout: LAYOUT,
            score: 1,
          },
          {
            id: "m-td",
            name: "TD Canada Trust",
            institution: "TD Canada Trust",
            builtin: true,
            layout: {
              ...LAYOUT,
              has_header: false,
              sign: "debit_credit",
              columns: ["date", "description", "debit", "credit", "balance"],
            },
            score: 0.1,
          },
        ],
        date_formats: ["MM/DD/YYYY"],
        date_ambiguous: false,
        choices: {
          roles: [
            "date",
            "description",
            "payee",
            "reference",
            "fitid",
            "amount",
            "debit",
            "credit",
            "balance",
            "ignore",
          ],
          signs: ["signed", "inverted", "debit_credit"],
          date_formats: ["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"],
        },
      },
    });
  });
  await page.route(`${BASE}/imports/imp1/preview`, async (r) => {
    calls.push(`preview:${JSON.stringify(r.request().postDataJSON())}`);
    await r.fulfill({ json: PREVIEW });
  });
  await page.route(`${BASE}/imports/imp1/commit`, async (r) => {
    calls.push(`commit:${JSON.stringify(r.request().postDataJSON())}`);
    await r.fulfill({
      json: {
        import: importRow({
          status: "committed",
          counts: { total: 6, new: 5, duplicate: 0, error: 1 },
        }),
      },
    });
  });
  await page.route(`${BASE}/imports/imp1/undo`, async (r) => {
    calls.push("undo");
    await r.fulfill({ json: { import: importRow({ status: "undone" }) } });
  });
}

async function dropFile(page: Page, name: string, text: string) {
  const transfer = await page.evaluateHandle(
    ([fileName, content]) => {
      const data = new DataTransfer();
      data.items.add(new File([content ?? ""], fileName ?? "file.csv", { type: "text/csv" }));
      return data;
    },
    [name, text],
  );
  await page.dispatchEvent("[data-dropzone]", "dragover", { dataTransfer: transfer });
  await page.dispatchEvent("[data-dropzone]", "drop", { dataTransfer: transfer });
}

test("usability: import an RBC CSV in under 90 seconds, with Undo", async ({ page }) => {
  const calls: string[] = [];
  await mockApi(page, calls);
  const started = Date.now();
  await page.goto(`/o/${ORG}/banking/${ID}/import`);
  await expect(page.getByRole("heading", { name: "Import a statement", level: 1 })).toBeVisible();
  const stepper = page.getByRole("list", { name: "Import steps" });
  await expect(stepper.locator('[aria-current="step"]')).toHaveText("1. Upload");
  await expect(page.getByText("Where to find the file")).toBeVisible();
  await expectAccessible(page);

  await dropFile(page, "rbc.csv", RBC.map((r) => r.join(",")).join("\n"));
  await expect(page.locator("[data-detection]")).toHaveText(
    "Read as CSV (UTF-8, comma-separated) — 6 lines.",
  );
  await expect(stepper.locator('[aria-current="step"]')).toHaveText("2. Map");
  await expect(page.getByText("Mapping: RBC Royal Bank (recognised automatically).")).toBeVisible();
  const grid = page.getByRole("table", { name: "First rows of the file" });
  await expect(grid.locator("tbody tr")).toHaveCount(5);
  await expect(grid.getByLabel("Column 3")).toHaveValue("date");
  await expect(grid.getByLabel("Column 7")).toHaveValue("amount");
  await expectAccessible(page);

  await page.getByRole("button", { name: "Preview" }).click();
  await expect(stepper.locator('[aria-current="step"]')).toHaveText("3. Preview");
  const tabs = page.getByRole("tablist", { name: "Lines by status" });
  await expect(tabs.getByRole("tab", { name: /New/ })).toContainText("5");
  await expect(tabs.getByRole("tab", { name: /Errors/ })).toContainText("1");
  await tabs.getByRole("tab", { name: /Errors/ }).click();
  await expect(
    page.getByText("Row 7: date '13/40/2026' doesn't match MM/DD/YYYY", { exact: false }),
  ).toBeVisible();
  await page.getByRole("switch", { name: "Skip errors and import valid lines" }).click();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByText("5 new lines will be imported into RBC Chequing.")).toBeVisible();
  await page.getByRole("button", { name: "Import 5 lines" }).click();
  const toast = page.getByText("5 lines imported from rbc.csv", { exact: true });
  await expect(toast).toBeVisible();
  const elapsed = Date.now() - started;
  expect(elapsed).toBeLessThan(90_000);
  expect(calls[0]).toBe("upload:multipart/form-data");
  expect(calls.find((c) => c.startsWith("commit:"))).toContain('"skip_errors":true');
  await expectAccessible(page);

  await page.getByRole("button", { name: "Undo import" }).click();
  await expect(page.getByText("Import undone: its lines were removed")).toBeVisible();
  expect(calls).toContain("undo");
});

test("editing a column and the date format sends the edited layout", async ({ page }) => {
  const calls: string[] = [];
  await mockApi(page, calls);
  await page.goto(`/o/${ORG}/banking/${ID}/import`);
  await page.getByLabel("Choose a file").setInputFiles({
    name: "rbc.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(RBC.map((r) => r.join(",")).join("\n")),
  });
  const grid = page.getByRole("table", { name: "First rows of the file" });
  await grid.getByLabel("Column 6").selectOption("payee");
  await page.getByLabel("Date format").selectOption("DD/MM/YYYY");
  await expect(page.getByLabel("Saved mapping")).toHaveValue("");
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByRole("tablist", { name: "Lines by status" })).toBeVisible();
  const sent = JSON.parse(calls.find((c) => c.startsWith("preview:"))!.slice("preview:".length));
  expect(sent.layout.columns[5]).toBe("payee");
  expect(sent.layout.date_format).toBe("DD/MM/YYYY");
  expect(sent.mapping).toBe("m-rbc");
});
