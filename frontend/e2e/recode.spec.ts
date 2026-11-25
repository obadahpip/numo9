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

const CODING = { account: OFFICE.id, tax_code: "", tracking: {}, contact: null };

function previewBody(lines: number) {
  return {
    summary: {
      lines,
      entries: 125,
      accounts: 1,
      excluded: 1,
      unchanged: 0,
      totals_unchanged: true,
      tax_delta: "0.00",
      needs_confirmation: false,
    },
    count: lines,
    page: 1,
    page_size: 100,
    lines: LINES.slice(0, 2).map((l) => ({
      entry: l.entry,
      number: l.number,
      date: l.date,
      line_no: l.line_no,
      book: "both",
      debit: l.debit,
      credit: l.credit,
      before: CODING,
      after: { ...CODING, account: RENT.id, tracking: { region: "east" } },
      changed: ["account", "tracking"],
      fingerprint: l.fingerprint,
    })),
    excluded: EXCLUDED,
    totals_before: { accounting: { debit: "125250.00", credit: "0.00" } },
    totals_after: { accounting: { debit: "125250.00", credit: "0.00" } },
    accounts: {},
    tax_impact: [],
  };
}

test("preview diff, confirm with the numbers, background progress", async ({ page }) => {
  const sent = await mockRecode(page);
  await page.route(`${API}/preview`, (r) => {
    sent.push({ url: "preview", body: jsonBody(r) });
    return r.fulfill({ json: previewBody(TOTAL) });
  });
  const batch = {
    id: "b-1",
    name: "Office to rent",
    label: "Office to rent",
    status: "running",
    criteria: {},
    changes: {},
    line_count: TOTAL,
    excluded_count: 1,
    progress: 0,
    problem_count: 0,
    created_at: "2026-11-26T10:00:00Z",
    executed_by: { id: "u1", name: "Dana Lee" },
    executed_at: "2026-11-26T10:00:00Z",
    undone_by: null,
    undone_at: null,
    undo_reason: "",
    job: "job-1",
    error: "",
  };
  await page.route(`${API}/execute`, (r) => {
    sent.push({ url: "execute", body: jsonBody(r) });
    return r.fulfill({ status: 202, json: batch });
  });
  let polls = 0;
  await page.route(`${API}/batches/b-1`, (r) => {
    polls += 1;
    return r.fulfill({
      json:
        polls < 2
          ? { ...batch, progress: 240 }
          : { ...batch, status: "completed", progress: TOTAL, problems: [] },
    });
  });

  await findOffice(page);
  const changes = page.locator("[data-recode-changes]");
  await changes.getByLabel("New account").selectOption(RENT.id);
  await changes.getByLabel("Category").fill("region");
  await changes.getByLabel("Option").fill("east");
  await page.getByRole("button", { name: "Preview the recode" }).click();
  const diff = page.locator("[data-diff]");
  await expect(page.locator("[data-preview-summary]")).toHaveText(
    "500 lines change · totals unchanged",
  );
  const first = diff.locator("tbody tr").first();
  await expect(first.locator('[data-field="account"] [data-after]')).toHaveText(RENT.label);
  await expect(first.locator('[data-field="tracking"] [data-after]')).toHaveText("region: east");
  await expect(first.locator('[data-field="tax_code"] [data-after]')).toHaveCount(0);
  expect(sent.find((s) => s.url === "preview")?.body).toMatchObject({
    changes: { account: RENT.id, tracking: { region: "east" } },
    selection: null,
  });
  await expectAccessible(page);

  await page.getByLabel("Name of this recode (optional)").fill("Office to rent");
  await page.getByRole("button", { name: "Recode 500 lines" }).click();
  const dialog = page.getByRole("dialog", { name: "Recode 500 lines?" });
  await expect(dialog.locator("[data-confirm-numbers]")).toContainText(
    "125 entries are reversed and posted again",
  );
  await expect(dialog.locator("[data-confirm-numbers]")).toContainText("$125,250.00");
  await expect(dialog.locator("[data-confirm-numbers]")).toContainText("1 excluded line");
  await dialog.getByRole("button", { name: "Recode" }).click();
  await expect(page.locator("[data-recode-progress]")).toHaveText(/Recoding (0|240) of 500 lines/);
  await expect(page.locator("[data-recode-progress]")).toBeHidden({ timeout: 10_000 });
  await expect(page.getByText("500 lines recoded").first()).toBeVisible();
  expect(sent.find((s) => s.url === "execute")?.body).toMatchObject({
    name: "Office to rent",
    selection: null,
    confirm_tax: false,
  });
});

test("a tax change asks for the acknowledgement", async ({ page }) => {
  await mockRecode(page);
  const body = previewBody(2);
  body.summary = { ...body.summary, lines: 2, needs_confirmation: true, tax_delta: "-130.00" };
  await page.route(`${API}/preview`, (r) => r.fulfill({ json: body }));
  await findOffice(page);
  await page.locator("[data-recode-changes]").getByLabel("New tax code").fill("sales.ON.zero");
  await page.getByRole("button", { name: "Preview the recode" }).click();
  await expect(page.locator("[data-tax-impact]")).toContainText("-$130.00");
  await page.getByRole("button", { name: "Recode 2 lines" }).click();
  const dialog = page.getByRole("dialog");
  const confirm = dialog.getByRole("button", { name: "Recode" });
  await expect(confirm).toBeDisabled();
  await dialog.getByRole("checkbox", { name: /tax these lines carry changes by/ }).click();
  await expect(confirm).toBeEnabled();
});
