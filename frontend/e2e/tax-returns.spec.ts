import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * G-03-T11, T12 — the GST/HST return: the periods list prepares a return and opens the
 * worksheet; a line drills to its documents in a drawer; the changed-since banner recalculates;
 * mark as filed with the confirmation number locks the period (lock icon in the list); amend
 * starts version 2. Server side: backend/tests/test_tax_returns_api.py.
 */
const ORG = "acme";
const REG = "11111111-1111-4111-8111-111111111111";
const PERIOD = "22222222-2222-4222-8222-222222222222";
const ID = "33333333-3333-4333-8333-333333333333";
const V2 = "44444444-4444-4444-8444-444444444444";

const LABELS: [string, string, string][] = [
  ["101", "Sales and other revenue", "1200.00"],
  ["103", "GST/HST collected or collectible", "130.00"],
  ["104", "Adjustments to be added to the net tax", "0.00"],
  ["105", "Total GST/HST and adjustments for period", "130.00"],
  ["106", "Input tax credits (ITCs) for the current period", "63.50"],
  ["107", "Adjustments to be deducted", "0.00"],
  ["108", "Total ITCs and adjustments", "63.50"],
  ["109", "Net tax", "66.50"],
  ["110", "Instalments and other annual filer payments", "0.00"],
  ["111", "Rebates", "0.00"],
  ["112", "Total other credits", "0.00"],
  ["113A", "Balance (line 109 minus line 112)", "66.50"],
  ["113B", "Other debits", "0.00"],
  ["113C", "Balance (line 113 A plus line 113 B)", "66.50"],
  ["114", "Refund claimed", "0.00"],
  ["115", "Payment enclosed", "66.50"],
];
const DRILL = ["101", "103", "104", "106", "107"];
const ENTRY = ["104", "107", "110", "111", "113B"];

function period(status = "open") {
  return {
    id: PERIOD,
    start: "2026-06-01",
    end: "2026-06-30",
    kind: "regular",
    frequency: "monthly",
    sequence_no: 6,
    due_date: "2026-07-31",
    payment_due_date: "2026-07-31",
    status,
    note: "",
  };
}

function taxReturn(over: Record<string, unknown> = {}) {
  return {
    id: ID,
    registration: REG,
    period: { ...period(), label: "2026-06-01 – 2026-06-30", locked: false },
    version: 1,
    status: "draft",
    method: "regular",
    is_current: true,
    lines: LABELS.map(([line, label, amount]) => ({
      line,
      label,
      amount,
      drill: DRILL.includes(line),
      entry: ENTRY.includes(line),
    })),
    entries: {},
    prepared_by: { id: "u1", name: "Dana Lee" },
    prepared_at: "2026-07-02T10:00:00Z",
    reviewed_by: null,
    filed_by: null,
    filed_on: null,
    confirmation_no: "",
    amend_reason: "",
    versions: [{ id: ID, version: 1, status: "draft", current: true }],
    changed: [],
    ...over,
  };
}

interface State {
  current: Record<string, unknown> | null;
  periodStatus: string;
  posts: { path: string; body: Record<string, unknown> }[];
}

async function mock(page: Page, initial: Record<string, unknown> | null) {
  const state: State = { current: initial, periodStatus: "open", posts: [] };
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/tax/registrations`, (r) =>
    r.fulfill({
      json: {
        results: [
          {
            id: REG,
            type: "rt",
            type_label: "GST/HST",
            number: "123456782RT0001",
            display_number: "123456782 RT 0001",
            files_returns: true,
          },
        ],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/tax/registrations/${REG}/periods`, (r) =>
    r.fulfill({
      json: {
        registration: { id: REG, type: "rt", number: "123456782RT0001" },
        today: "2026-07-02",
        results: [period(state.periodStatus)],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/tax/returns**`, (r) => {
    const url = new URL(r.request().url());
    const path = url.pathname.replace(`/api/v1/o/${ORG}/tax/returns`, "");
    if (r.request().method() === "POST") {
      const body = jsonBody(r);
      state.posts.push({ path, body });
      if (path === "") {
        state.current = taxReturn();
        return r.fulfill({ status: 201, json: state.current });
      }
      const action = path.split("/").at(-1);
      if (action === "recalculate") state.current = taxReturn();
      if (action === "review")
        state.current = taxReturn({
          status: "reviewed",
          reviewed_by: { id: "u2", name: "Sam Patel" },
        });
      if (action === "file") {
        state.periodStatus = "filed";
        state.current = taxReturn({
          status: "filed",
          reviewed_by: { id: "u2", name: "Sam Patel" },
          filed_by: { id: "u1", name: "Dana Lee" },
          filed_on: body.filed_on,
          confirmation_no: body.confirmation_no,
          period: { ...period("filed"), label: "", locked: true },
        });
      }
      if (action === "amend") {
        state.current = taxReturn({
          id: V2,
          version: 2,
          amend_reason: body.reason,
          versions: [
            { id: V2, version: 2, status: "draft", current: true },
            { id: ID, version: 1, status: "filed", current: false },
          ],
        });
        return r.fulfill({ status: 201, json: state.current });
      }
      return r.fulfill({ json: state.current });
    }
    if (path.endsWith("/drill")) {
      return r.fulfill({
        json: {
          line: url.searchParams.get("line"),
          documents: [
            {
              entry: "e1",
              number: "INV-0001",
              contact: "Maple Leaf Supply Ltd.",
              date: "2026-06-10",
              url: `/o/${ORG}/sales/invoices/i-1`,
              amount: "130.00",
            },
          ],
        },
      });
    }
    if (path === "") return r.fulfill({ json: { returns: state.current ? [state.current] : [] } });
    return r.fulfill({ json: state.current });
  });
  return state;
}

test.use({ viewport: { width: 1440, height: 900 } });

test("prepare a return, then drill a line to its documents in a drawer", async ({ page }) => {
  const state = await mock(page, null);
  await page.goto(`/o/${ORG}/tax/returns`);
  const row = page.locator('tr[data-period="2026-06-01"]');
  await expect(row).toContainText("Not started");
  await expectAccessible(page);
  await row.getByRole("button", { name: "Prepare return" }).click();
  await expect(page).toHaveURL(new RegExp(`/o/${ORG}/tax/returns/${ID}$`));
  expect(state.posts[0]).toEqual({ path: "", body: { period: PERIOD } });

  const worksheet = page.getByTestId("return-worksheet");
  await expect(worksheet.locator('tr[data-line="109"]')).toContainText("$66.50");
  await expect(page.getByText("Prepare (current step)")).toBeVisible();
  await page.getByRole("button", { name: "Show the documents behind line 103" }).click();
  const drawer = page.getByRole("dialog", { name: "Line 103: GST/HST collected or collectible" });
  await expect(drawer.getByRole("link", { name: "INV-0001" })).toHaveAttribute(
    "href",
    `/o/${ORG}/sales/invoices/i-1`,
  );
  await expect(drawer.getByTestId("drill-documents")).toContainText("Maple Leaf Supply Ltd.");
  await expectAccessible(page);
});

test("the changed-since banner recalculates from the books", async ({ page }) => {
  const state = await mock(
    page,
    taxReturn({ changed: [{ line: "103", was: "130.00", now: "156.00" }] }),
  );
  await page.goto(`/o/${ORG}/tax/returns/${ID}`);
  const banner = page.getByTestId("return-changed");
  await expect(banner).toContainText("Line 103: $130.00 → $156.00");
  await banner.getByRole("button", { name: "Recalculate" }).click();
  await expect(banner).toBeHidden();
  expect(state.posts.at(-1)?.path).toBe(`/${ID}/recalculate`);
});

test("review, mark as filed: the period is locked; amend starts version 2", async ({ page }) => {
  const state = await mock(page, taxReturn());
  await page.goto(`/o/${ORG}/tax/returns/${ID}`);
  await page.getByRole("button", { name: "Mark as reviewed" }).click();
  await expect(page.getByText("Review (current step)")).toBeVisible();

  await page.getByRole("button", { name: "Mark as filed" }).click();
  const dialog = page.getByRole("dialog", { name: "Mark the return as filed" });
  await dialog.getByRole("button", { name: "Mark as filed" }).click();
  await expect(dialog.getByRole("alert")).toHaveText("Required");
  await dialog.getByRole("textbox", { name: "Confirmation number" }).fill("GH-2026-0001");
  await dialog.getByLabel("Filed on").fill("2026-07-20");
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Mark as filed" }).click();
  await expect(dialog).toBeHidden();
  expect(state.posts.at(-1)).toEqual({
    path: `/${ID}/file`,
    body: { confirmation_no: "GH-2026-0001", filed_on: "2026-07-20" },
  });
  const filed = page.getByTestId("return-filed");
  await expect(filed).toContainText("Filed on 20 Jul 2026 · confirmation GH-2026-0001");
  await expect(filed.getByRole("img", { name: "Locked: filed" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Amount for line 110" })).toHaveCount(0);

  await page.getByRole("button", { name: "Amend" }).click();
  const amend = page.getByRole("dialog", { name: "Amend the filed return" });
  await amend.getByRole("textbox", { name: "Why is it amended?" }).fill("Missed a bill");
  await amend.getByRole("button", { name: "Amend" }).click();
  await expect(page).toHaveURL(new RegExp(`/tax/returns/${V2}$`));
  expect(state.posts.at(-1)).toEqual({ path: `/${ID}/amend`, body: { reason: "Missed a bill" } });
  await expect(page.getByTestId("return-versions")).toContainText("Filed · version 1");

  await page.goto(`/o/${ORG}/tax/returns`);
  await expect(
    page.locator('tr[data-period="2026-06-01"]').getByTestId("period-lock"),
  ).toBeVisible();
});

test("the filing timeline shows the lock on a filed period", async ({ page }) => {
  await mock(page, null);
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/tax/registrations/${REG}/periods`, (r) =>
    r.fulfill({
      json: {
        registration: { id: REG, type: "rt", number: "123456782RT0001", start_date: "2026-01-01" },
        today: "2026-07-25",
        results: [period("filed")],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/tax/registrations/${REG}/cycles`, (r) =>
    r.fulfill({ json: { results: [] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/tax/registrations/${REG}/events`, (r) =>
    r.fulfill({ json: { events: [], gaps: [], stopped: false, stop_date: null } }),
  );
  await page.goto(`/o/${ORG}/settings/tax/registrations/${REG}/filing`);
  await expect(page.getByTestId("period-lock")).toHaveCount(1);
});
