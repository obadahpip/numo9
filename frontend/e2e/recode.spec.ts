import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * C-07-T11 – T13 — find & recode: the results grid selects all 500 lines across pages and lists
 * excluded lines with their reason; the preview shows before / after per line and the confirm
 * dialog the numbers; a background recode shows its progress; the history offers Undo (disabled
 * with the reason when a period is locked) and the report. Server side:
 * backend/tests/test_recode_*.py.
 */
const ORG = "acme";
const API = `**/api/v1/o/${ORG}/recode`;
const TOTAL = 500;
const PAGE = 50;

const OFFICE = { id: "acc-office", label: "6100 · Office supplies" };
const RENT = { id: "acc-rent", label: "6200 · Rent" };

function line(i: number) {
  return {
    entry: `e-${Math.floor(i / 4)}`,
    number: `JE-${String(1000 + Math.floor(i / 4)).padStart(6, "0")}`,
    date: "2026-05-01",
    type: "manual",
    narration: `Bulk ${Math.floor(i / 4)}`,
    line_no: (i % 4) + 1,
    book: "both",
    account: OFFICE,
    debit: `${i + 1}.00`,
    credit: "0.00",
    tax_code: "",
    contact: null,
    tracking: {},
    description: "",
    fingerprint: `f${i}`,
  };
}

const LINES = Array.from({ length: TOTAL }, (_, i) => line(i));
const EXCLUDED = [
  {
    ...line(9999),
    entry: "e-locked",
    number: "JE-000001",
    line_no: 1,
    reason: {
      code: "locked",
      message: "Locked: 31 Mar 2026 (general ledger) — no changes on or before that date.",
    },
  },
];

export async function mockRecode(page: Page) {
  const sent: { url: string; body: Record<string, unknown> }[] = [];
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/accounts?status=active`, (r) =>
    r.fulfill({
      json: {
        count: 2,
        results: [
          { id: OFFICE.id, code: "6100", name: "Office supplies" },
          { id: RENT.id, code: "6200", name: "Rent" },
        ],
      },
    }),
  );
  await page.route(`${API}/search`, (r) => {
    const body = jsonBody(r);
    sent.push({ url: "search", body });
    const pageNo = Number(body.page ?? 1);
    return r.fulfill({
      json: {
        count: TOTAL,
        accounts: 1,
        page: pageNo,
        page_size: PAGE,
        lines: LINES.slice((pageNo - 1) * PAGE, pageNo * PAGE),
        keys: LINES.map((l) => ({
          entry: l.entry,
          line_no: l.line_no,
          fingerprint: l.fingerprint,
        })),
        excluded_count: EXCLUDED.length,
        excluded: EXCLUDED,
      },
    });
  });
  return sent;
}

test.use({ viewport: { width: 1440, height: 900 } });

async function findOffice(page: Page) {
  await page.goto(`/o/${ORG}/accounting/recode`);
  const builder = page.locator("[data-condition-builder]");
  await builder.getByLabel("Value").selectOption(OFFICE.id);
  await page.getByRole("button", { name: "Find lines" }).click();
  await expect(page.locator("[data-recode-summary]")).toHaveText(
    "500 lines · 1 account · 1 excluded",
  );
}

test("select all 500 lines across pages; excluded lines with their reason", async ({ page }) => {
  const sent = await mockRecode(page);
  await findOffice(page);
  expect(sent[0]?.body.criteria).toEqual({
    match: "all",
    conditions: [{ field: "account", op: "is", value: OFFICE.id }],
  });
  const grid = page.locator("[data-recode-results]");
  await expect(grid.locator("tbody tr")).toHaveCount(PAGE);
  await grid.getByRole("checkbox", { name: "Select the lines on this page" }).click();
  await expect(grid.locator("[data-selected-count]")).toHaveText("50 lines selected");
  await grid.getByRole("button", { name: "Select all 500 lines" }).click();
  await expect(grid.locator("[data-selected-count]")).toHaveText("500 lines selected");
  await grid.getByRole("button", { name: "Next" }).click();
  await expect(grid.getByText("Page 2 of 10")).toBeVisible();
  await expect(grid.getByRole("checkbox", { name: "Select JE-001012 line 3" })).toBeChecked();
  await grid.getByRole("checkbox", { name: "Select JE-001012 line 3" }).click();
  await expect(grid.locator("[data-selected-count]")).toHaveText("499 lines selected");
  await expectAccessible(page);

  await page.getByRole("tab", { name: /Excluded/ }).click();
  const excluded = page.locator("[data-recode-excluded]");
  await expect(excluded.locator('[data-excluded="locked"]')).toContainText("Locked: 31 Mar 2026");
});
