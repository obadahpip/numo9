import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * G-03a filing periods (T18 timeline, T19 change-frequency wizard, T20 out-of-cycle dialog,
 * T21 history). The API is mocked with a small in-memory model of one registration: a change
 * is previewed (nothing stored), then confirmed (stored), and the page reads the periods
 * again. The rules themselves are tested on the real API in backend/tests/test_filing_*.py.
 */
const ORG = "acme";
const REG = "11111111-2222-4333-8444-555555555555";
const BASE = `**/api/v1/o/${ORG}/tax/registrations/${REG}`;
const URL = `/o/${ORG}/settings/tax/registrations/${REG}/filing`;

type Row = Record<string, unknown> & { id: string; start: string; end: string };
const period = (
  start: string,
  end: string,
  n: number,
  over: Record<string, unknown> = {},
): Row => ({
  id: `p-${start}`,
  start,
  end,
  kind: "regular",
  frequency: "quarterly",
  sequence_no: n,
  due_date: "2027-02-01",
  payment_due_date: "2027-02-01",
  status: "open",
  note: "",
  attention: "",
  due_rolled: false,
  instalments: [],
  ...over,
});
const Q1 = period("2026-01-01", "2026-03-31", 1, { status: "filed", due_date: "2026-04-30" });
const Q2 = period("2026-04-01", "2026-06-30", 2, {
  status: "closed",
  attention: "overdue",
  due_date: "2026-07-31",
});
const Q3 = period("2026-07-01", "2026-09-30", 3, {
  status: "closed",
  attention: "due_soon",
  due_date: "2026-11-02",
  due_rolled: true,
});
const Q4 = period("2026-10-01", "2026-12-31", 4);
const MONTHS = [
  period("2026-10-01", "2026-10-31", 4, { id: "m-10", frequency: "monthly" }),
  period("2026-11-01", "2026-11-30", 5, { id: "m-11", frequency: "monthly" }),
  period("2026-12-01", "2026-12-31", 6, { id: "m-12", frequency: "monthly" }),
];
const CUSTOM = period("2026-10-01", "2026-11-15", 4, { id: "x-1", kind: "custom" });
const STUB = period("2026-11-16", "2026-12-31", 5, { id: "x-2", kind: "stub" });
const QUARTERLY = {
  id: "c-1",
  frequency: "quarterly",
  effective_from: "2026-01-01",
  approval_ref: "",
  approval_date: null,
  note: "",
  created_by: "Dana Lee",
  created_at: "2026-01-05T15:00:00Z",
};

interface Model {
  periods: Row[];
  cycles: Record<string, unknown>[];
  posts: { path: string; body: Record<string, unknown> }[];
}

async function mockFiling(page: Page): Promise<Model> {
  const model: Model = { periods: [Q1, Q2, Q3, Q4], cycles: [QUARTERLY], posts: [] };
  await mockCsrf(page);
  await page.route(`${BASE}/periods`, (r) =>
    r.fulfill({
      json: {
        registration: {
          id: REG,
          type: "rt",
          number: "12345 6782 RT0001",
          start_date: "2026-01-01",
          stop_date: "2026-12-31",
        },
        today: "2026-10-20",
        results: model.periods,
      },
    }),
  );
  const switched = (body: Record<string, unknown>) => ({
    removed: [Q4],
    added: MONTHS,
    changed: [],
    periods: [Q1, Q2, Q3, ...MONTHS],
    warnings: [
      {
        code: "tax.filing.not_fiscal_year_start",
        message: `${String(body.effective_from)} isn't the start of your financial year.`,
      },
    ],
  });
  const customised = {
    removed: [Q4],
    added: [CUSTOM, STUB],
    changed: [],
    periods: [Q1, Q2, Q3, CUSTOM, STUB],
    warnings: [],
  };
  await page.route(`${BASE}/cycles`, (r) => {
    if (r.request().method() === "GET") return r.fulfill({ json: { results: model.cycles } });
    const body = jsonBody(r);
    model.posts.push({ path: "cycles", body });
    model.periods = [Q1, Q2, Q3, ...MONTHS];
    model.cycles = [
      ...model.cycles,
      {
        id: "c-2",
        frequency: body.frequency,
        effective_from: body.effective_from,
        approval_ref: body.approval_ref,
        approval_date: body.approval_date,
        note: body.note,
        created_by: "Sam Patel",
        created_at: "2026-10-20T14:30:00Z",
      },
    ];
    return r.fulfill({ status: 201, json: switched(body) });
  });
  await page.route(`${BASE}/preview`, (r) => {
    const body = jsonBody(r);
    model.posts.push({ path: "preview", body });
    if (body.action === "switch" && !body.approval_ref) {
      return r.fulfill({
        status: 422,
        json: {
          code: "tax.filing.approval_required",
          detail:
            "A change during the financial year needs the CRA or Revenu Québec approval reference.",
        },
      });
    }
    if (body.action === "custom" && String(body.start) < "2026-04-01") {
      return r.fulfill({
        status: 422,
        json: {
          code: "tax.filing.custom_overlaps_filed",
          detail: "The period overlaps the filed period 2026-01-01 – 2026-03-31.",
        },
      });
    }
    return r.fulfill({ json: body.action === "switch" ? switched(body) : customised });
  });
  await page.route(`${BASE}/custom-periods`, (r) => {
    model.posts.push({ path: "custom-periods", body: jsonBody(r) });
    model.periods = [Q1, Q2, Q3, CUSTOM, STUB];
    return r.fulfill({ status: 201, json: customised });
  });
  await page.route(`${BASE}/custom-periods/x-1`, (r) => {
    model.posts.push({ path: "delete", body: {} });
    model.periods = [Q1, Q2, Q3, Q4];
    return r.fulfill({
      json: {
        removed: [CUSTOM, STUB],
        added: [Q4],
        changed: [],
        periods: model.periods,
        warnings: [],
      },
    });
  });
  return model;
}

const blocks = (page: Page) =>
  page.locator("[data-filing-timeline] [data-period]").evaluateAll((items) =>
    items.map((item) => {
      const el = item as HTMLElement;
      return `${el.dataset.period}:${el.dataset.state}:${el.dataset.kind}`;
    }),
  );

test("T18 timeline matches the API periods: blocks, states, marker, hover card", async ({
  page,
}) => {
  await mockFiling(page);
  await page.goto(URL);
  await expect(page.getByRole("heading", { name: "Filing periods", level: 1 })).toBeVisible();
  expect(await blocks(page)).toEqual([
    "2026-01-01:filed:regular",
    "2026-04-01:overdue:regular",
    "2026-07-01:due_soon:regular",
    "2026-10-01:open:regular",
  ]);
  // The blocks fill the timeline side by side: no gap, no overlap.
  const boxes = await page.locator("[data-period]").evaluateAll((items) =>
    items.map((item) => {
      const box = item.getBoundingClientRect();
      return [box.left, box.right];
    }),
  );
  for (let i = 1; i < boxes.length; i += 1) {
    expect(boxes[i]![0]! - boxes[i - 1]![1]!).toBeGreaterThanOrEqual(0);
    expect(boxes[i]![0]! - boxes[i - 1]![1]!).toBeLessThanOrEqual(2);
  }
  await expect(page.locator("[data-switch]")).toHaveText("Quarterly from 1 Jan 2026");
  await page.getByRole("button", { name: /^Period 3:/ }).hover();
  const card = page.getByRole("tooltip");
  await expect(card).toContainText("1 Jul 2026 – 30 Sep 2026");
  await expect(card).toContainText("Return due 2 Nov 2026 *");
  await expectAccessible(page);
});

test("T19 wizard: refusal, preview diff, confirm creates exactly the previewed periods", async ({
  page,
}) => {
  const model = await mockFiling(page);
  await page.goto(URL);
  await page.getByRole("button", { name: "Change frequency" }).click();
  const dialog = page.getByRole("dialog", { name: "Change filing frequency" });
  await expect(dialog.getByRole("radio", { name: "Monthly" })).toBeChecked();
  await dialog.getByRole("button", { name: "Next" }).click();
  await dialog.getByLabel("Takes effect on").fill("2026-10-01");
  await dialog.getByRole("button", { name: "Next" }).click();
  await dialog.getByRole("button", { name: "Preview" }).click();
  await expect(dialog.getByRole("alert")).toContainText("needs the CRA");
  await dialog.getByLabel("CRA or Revenu Québec approval reference").fill("2026-GST-48812");
  await dialog.getByRole("button", { name: "Preview" }).click();
  await expect(dialog.locator("[data-diff='removed']")).toHaveText(
    "Removed: 1 Oct 2026 – 31 Dec 2026",
  );
  await expect(dialog.locator("[data-diff='added']")).toHaveCount(3);
  await expect(dialog.locator("[data-warning]")).toContainText("isn't the start");
  await expectAccessible(page);
  expect(await blocks(page)).toHaveLength(4); // nothing saved by the preview
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.locator("[data-period]")).toHaveCount(6);
  expect((await blocks(page)).slice(3)).toEqual([
    "2026-10-01:open:regular",
    "2026-11-01:open:regular",
    "2026-12-01:open:regular",
  ]);
  const [refused, previewed, confirmed] = model.posts;
  expect(refused!.path).toBe("preview");
  const { action, ...change } = previewed!.body;
  expect(action).toBe("switch");
  expect(confirmed).toEqual({ path: "cycles", body: change });
  await expect(page.locator("[data-switch='2026-10-01']")).toHaveText("Monthly from 1 Oct 2026");
});

test("T20 out-of-cycle: overlap preview, realignment, the stub scenario through the UI", async ({
  page,
}) => {
  const model = await mockFiling(page);
  await page.goto(URL);
  await page.getByRole("button", { name: "Add out-of-cycle period" }).click();
  const dialog = page.getByRole("dialog", { name: "Add an out-of-cycle period" });
  await dialog.getByLabel("Starts").fill("2026-03-01");
  await dialog.getByLabel("Ends").fill("2026-04-15");
  await dialog.getByRole("button", { name: "Preview" }).click();
  await expect(dialog.getByRole("alert")).toContainText("overlaps the filed period");
  await dialog.getByLabel("Starts").fill("2026-10-01");
  await dialog.getByLabel("Ends").fill("2026-11-15");
  await dialog.getByLabel("Why (kept in the history)").fill("Year-end change");
  await dialog.getByRole("button", { name: "Preview" }).click();
  await expect(dialog.locator("[data-check='ok']")).toBeVisible();
  await expect(dialog.locator("[data-realign]")).toContainText("restart on 16 Nov 2026");
  await expect(dialog.locator("[data-diff='added']")).toHaveText([
    "Added: 1 Oct 2026 – 15 Nov 2026 · Out of cycle",
    "Added: 16 Nov 2026 – 31 Dec 2026 · Stub",
  ]);
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Add period" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.locator("[data-period]")).toHaveCount(5);
  expect((await blocks(page)).slice(3)).toEqual(["2026-10-01:open:custom", "2026-11-16:open:stub"]);
  expect(model.posts.at(-1)).toEqual({
    path: "custom-periods",
    body: { start: "2026-10-01", end: "2026-11-15", note: "Year-end change" },
  });
  await page.getByRole("button", { name: /^Remove out-of-cycle period/ }).click();
  await expect(page.locator("[data-period]")).toHaveCount(4);
});

test("T21 history shows all switches: who, when, approval reference", async ({ page }) => {
  await mockFiling(page);
  await page.goto(URL);
  const table = page.getByRole("table", { name: "Filing frequency changes" });
  await expect(table.locator("tbody tr")).toHaveCount(1);
  await expect(table.locator("tbody tr")).toContainText("Dana Lee");
  await page.getByRole("button", { name: "Change frequency" }).click();
  const dialog = page.getByRole("dialog", { name: "Change filing frequency" });
  await dialog.getByRole("button", { name: "Next" }).click();
  await dialog.getByLabel("Takes effect on").fill("2026-10-01");
  await dialog.getByRole("button", { name: "Next" }).click();
  await dialog.getByLabel("CRA or Revenu Québec approval reference").fill("2026-GST-48812");
  await dialog.getByLabel("Approval date").fill("2026-09-10");
  await dialog.getByRole("button", { name: "Preview" }).click();
  await dialog.getByRole("button", { name: "Confirm change" }).click();
  await expect(table.locator("tbody tr")).toHaveCount(2);
  const newest = table.locator("tbody tr").first();
  await expect(newest).toContainText("1 Oct 2026");
  await expect(newest).toContainText("Monthly");
  await expect(newest).toContainText("Current");
  await expect(newest).toContainText("2026-GST-48812 (10 Sep 2026)");
  await expect(newest).toContainText("Sam Patel");
  await expect(table.locator("tbody tr").nth(1)).toContainText("Quarterly");
  await expectAccessible(page);
});
