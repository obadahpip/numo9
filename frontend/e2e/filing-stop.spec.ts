import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * G-03b-T10 — stop filing in the danger zone: the impact preview, Stop filing disabled until the
 * registration number is typed; then the "Not registered" band and Restart filing (wizard with a
 * preview). The rules are tested on the real API: backend/tests/test_filing_stop*.py.
 */
const ORG = "acme";
const REG = "11111111-2222-4333-8444-555555555555";
const BASE = `**/api/v1/o/${ORG}/tax/registrations/${REG}`;
const URL = `/o/${ORG}/settings/tax/registrations/${REG}/filing`;

const period = (start: string, end: string, n: number, over: Record<string, unknown> = {}) => ({
  id: `p-${start}`,
  start,
  end,
  kind: "regular",
  frequency: "quarterly",
  sequence_no: n,
  due_date: "2026-07-31",
  payment_due_date: "2026-07-31",
  status: "open",
  note: "",
  attention: "",
  due_rolled: false,
  instalments: [],
  ...over,
});
const Q1 = period("2026-01-01", "2026-03-31", 1, { status: "filed" });
const Q2 = period("2026-04-01", "2026-06-30", 2, { status: "closed" });
const Q3 = period("2026-07-01", "2026-09-30", 3);
const Q4 = period("2026-10-01", "2026-12-31", 4);
const Q1N = period("2027-01-01", "2027-03-31", 3);
const STOP_EVENT = {
  id: "e1",
  action: "stop",
  date: "2026-06-30",
  reason_code: "deregistration",
  reason_label: "Registration cancelled",
  reason_text: "Business sold",
  frequency: "",
  by: { id: "u1", name: "Dana Lee" },
  at: "2026-07-02T14:14:00Z",
};

async function mock(page: Page) {
  const model = {
    periods: [Q1, Q2, Q3, Q4],
    status: {
      events: [] as unknown[],
      gaps: [] as unknown[],
      stopped: false,
      stop_date: null as string | null,
      last_filed_end: "2026-03-31",
    },
    posts: [] as { path: string; body: Record<string, unknown> }[],
  };
  await mockCsrf(page);
  await page.route(`${BASE}/periods`, (r) =>
    r.fulfill({
      json: {
        registration: {
          id: REG,
          type: "rt",
          number: "123456782RT0001",
          start_date: "2026-01-01",
          stop_date: model.status.stop_date,
        },
        today: "2026-07-02",
        results: model.periods,
      },
    }),
  );
  await page.route(`${BASE}/cycles`, (r) =>
    r.fulfill({
      json: {
        results: [
          {
            id: "c-1",
            frequency: "quarterly",
            effective_from: "2026-01-01",
            approval_ref: "",
            approval_date: null,
            note: "",
            created_by: "Dana Lee",
            created_at: "2026-01-05T15:00:00Z",
          },
        ],
      },
    }),
  );
  await page.route(`${BASE}/events`, (r) =>
    r.fulfill({ json: { ...model.status, documents: [] } }),
  );
  const stopImpact = {
    removed: [Q3, Q4],
    added: [],
    changed: [],
    periods: [Q1, Q2],
    warnings: [],
    documents: [
      {
        kind: "invoice",
        id: "i1",
        number: "INV-0043",
        date: "2026-07-15",
        total: "113.00",
        url: `/o/${ORG}/sales/invoices/i1`,
      },
    ],
    out_of_scope_default: true,
    stopped: true,
  };
  const restartImpact = {
    removed: [],
    added: [Q1N],
    changed: [],
    periods: [Q1, Q2, Q1N],
    warnings: [],
    documents: [],
    out_of_scope_default: false,
    stopped: false,
  };
  await page.route(`${BASE}/preview`, (r) => {
    const body = jsonBody(r);
    model.posts.push({ path: "preview", body });
    return r.fulfill({ json: body.action === "stop" ? stopImpact : restartImpact });
  });
  await page.route(`${BASE}/stop`, (r) => {
    model.posts.push({ path: "stop", body: jsonBody(r) });
    model.periods = [Q1, Q2];
    model.status = {
      events: [STOP_EVENT],
      gaps: [{ start: "2026-07-01", end: null }],
      stopped: true,
      stop_date: "2026-06-30",
      last_filed_end: "2026-03-31",
    };
    return r.fulfill({ status: 201, json: { ...stopImpact, ...model.status } });
  });
  await page.route(`${BASE}/restart`, (r) => {
    model.posts.push({ path: "restart", body: jsonBody(r) });
    model.periods = [Q1, Q2, Q1N];
    model.status = {
      events: [
        STOP_EVENT,
        {
          ...STOP_EVENT,
          id: "e2",
          action: "restart",
          date: "2027-01-01",
          reason_code: "",
          reason_label: "",
          reason_text: "",
          frequency: "quarterly",
        },
      ],
      gaps: [{ start: "2026-07-01", end: "2026-12-31" }],
      stopped: false,
      stop_date: null,
      last_filed_end: "2026-03-31",
    };
    return r.fulfill({ status: 201, json: { ...restartImpact, ...model.status } });
  });
  return model;
}

test.use({ viewport: { width: 1440, height: 900 } });

test("stop requires typing the registration number, then restart", async ({ page }) => {
  const model = await mock(page);
  await page.goto(URL);
  const zone = page.locator("[data-danger-zone]");
  await expect(zone.getByRole("heading", { name: "Stop filing" })).toBeVisible();
  await zone.getByLabel("Last day registered").fill("2026-06-30");
  await zone.getByRole("button", { name: "Review the impact" }).click();
  await expect(zone.getByText("Your final return covers 1 Apr 2026 – 30 Jun 2026.")).toBeVisible();
  await expect(zone.getByText("2 periods after 30 Jun 2026 will be removed.")).toBeVisible();
  await expect(zone.getByRole("link", { name: "INV-0043 (15 Jul 2026)" })).toBeVisible();
  await expectAccessible(page);
  const confirm = zone.getByRole("button", { name: "Stop filing" });
  await expect(confirm).toBeDisabled();
  const typed = zone.getByLabel(/Type the registration number/);
  await typed.fill("123456782RT0009");
  await expect(confirm).toBeDisabled();
  await typed.fill("123456782RT0001");
  await expect(confirm).toBeEnabled();
  await confirm.click();
  await expect(
    page.getByText("Filing stopped: the last day registered is 30 Jun 2026."),
  ).toBeVisible();
  expect(model.posts.find((p) => p.path === "stop")?.body).toMatchObject({
    date: "2026-06-30",
    reason_code: "deregistration",
    confirm_number: "123456782RT0001",
  });
  await expect(page.getByRole("img", { name: "Not registered: From 1 Jul 2026" })).toBeVisible();
  await expect(page.locator("[data-danger-zone]")).toHaveCount(0);

  await page.getByRole("button", { name: "Restart filing" }).click();
  const dialog = page.getByRole("dialog", { name: "Restart filing" });
  await dialog.getByLabel("Registered again from").fill("2027-01-01");
  await dialog.getByRole("button", { name: "Preview" }).click();
  await dialog.getByRole("button", { name: "Restart" }).click();
  await expect(dialog).toBeHidden();
  await expect(
    page.getByRole("img", { name: "Not registered: 1 Jul 2026 – 31 Dec 2026" }),
  ).toBeVisible();
  await expect(page.getByText(/1 Jan 2027: restarted — Quarterly — Dana Lee/)).toBeVisible();
  expect(model.posts.find((p) => p.path === "restart")?.body).toEqual({
    date: "2027-01-01",
    frequency: "quarterly",
  });
});
