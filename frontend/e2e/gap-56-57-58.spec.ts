import { expect, test, type Page } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";
import { balanceSheet, CATALOGUE } from "./reports-fixtures";

/**
 * K-02-T16 — the core statements' gaps where the screen is the gap (the data side:
 * backend/tests/test_report_k02_gaps.py):
 * - gap-56: the balance sheet opens as at today (Xero: end of last financial year, an empty
 *   sheet), prints the Liabilities section and shows overdrawn Petty Cash as a bank overdraft
 *   under current liabilities with its note;
 * - gap-58: the journal report has an order *and* a direction control, sent to the run.
 */
const JOURNAL_REPORT = {
  ...CATALOGUE.categories[0]!.reports[0]!,
  id: "journal_report",
  slug: "journal-report",
  name: "Journal report",
  description: "Posted journals of a period with their lines.",
  params: [
    { name: "date_from", kind: "date", default: null, choices: [], required: true },
    { name: "date_to", kind: "date", default: null, choices: [], required: true },
    {
      name: "book",
      kind: "choice",
      default: "accounting",
      choices: ["accounting", "tax"],
      required: false,
    },
    {
      name: "order",
      kind: "choice",
      default: "number",
      choices: ["number", "date"],
      required: false,
    },
    {
      name: "direction",
      kind: "choice",
      default: "asc",
      choices: ["asc", "desc"],
      required: false,
    },
  ],
};

const catalogue = {
  categories: CATALOGUE.categories.map((group, i) =>
    i === 0 ? { ...group, reports: [...group.reports, JOURNAL_REPORT] } : group,
  ),
};

async function mock(page: Page) {
  await mockCsrf(page);
  const runs: URL[] = [];
  await page.route("**/api/v1/o/acme/reports", (r) => r.fulfill({ json: catalogue }));
  await page.route("**/api/v1/o/acme/reports/*/run*", (r) => {
    const url = new URL(r.request().url());
    runs.push(url);
    const asOf = url.searchParams.get("as_of") ?? "2026-06-30";
    const body = balanceSheet(asOf);
    return r.fulfill({
      json: url.pathname.includes("journal-report")
        ? { ...body, report: "journal_report", rows: [], totals: [] }
        : body,
    });
  });
  return runs;
}

function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

test.use({ viewport: { width: 1440, height: 900 } });

test("gap-56: as at today, Liabilities printed, Petty Cash a bank overdraft with the note", async ({
  page,
}) => {
  const runs = await mock(page);
  await page.goto("/o/acme/reports/balance-sheet");
  await expect.poll(() => runs[0]?.searchParams.get("as_of")).toBe(today());
  const table = page.getByRole("table");
  await expect(table).toContainText("Liabilities");
  await expect(table).toContainText("Bank overdraft — Petty Cash");
  await expect(table).toContainText(
    "Overdrawn bank and cash accounts are presented as current liabilities (ASPE 1510).",
  );
  await expect(table).not.toContainText("Petty Cash (994.17)");
});

test("gap-58: the journal report's direction control goes to the run", async ({ page }) => {
  const runs = await mock(page);
  await page.goto("/o/acme/reports/journal-report");
  await expect.poll(() => runs[0]?.searchParams.get("direction")).toBe("asc");
  await page.getByRole("combobox", { name: "Direction" }).click();
  await page.getByRole("option", { name: "Descending (newest first)" }).click();
  await page.getByRole("combobox", { name: "Order by" }).click();
  await page.getByRole("option", { name: "Date" }).click();
  await page.getByRole("button", { name: "Update" }).click();
  await expect.poll(() => runs.at(-1)?.searchParams.get("direction")).toBe("desc");
  expect(runs.at(-1)?.searchParams.get("order")).toBe("date");
});
