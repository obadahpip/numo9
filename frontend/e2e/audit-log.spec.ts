import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, expectNoHorizontalScroll, mockCsrf } from "./auth-helpers";
import refusal from "./fixtures/refusal-members-view.json" with { type: "json" };

/**
 * A-04-T09 — Settings → Audit log: the global viewer (date presets, filters, DataGrid, DiffViewer,
 * export menu). Acceptance: filters work; a11y passes. The API is answered with fixtures in the
 * shape of the real one (backend/numo9/audit/api.py, checked by backend/tests/test_audit_api.py).
 */
export const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}/audit`;
const PAGE = `/o/${ORG}/settings/audit-log`;
const SAM = "5a1b2c3d-0000-4000-8000-000000000001";

export function auditEvent(overrides: Record<string, unknown> = {}) {
  return {
    id: "e0000000-0000-4000-8000-000000000001",
    at: "2026-10-26T20:33:00Z",
    action: "contacts.contact.updated",
    action_label: "Edited",
    verb: "updated",
    actor: {
      kind: "user",
      label: "Sam Patel (sam@refined.ca)",
      user: { id: SAM, name: "Sam Patel", email: "sam@refined.ca" },
      impersonator: null,
    },
    record: {
      type: "contacts.Contact",
      type_label: "Contact",
      id: "c0000000-0000-4000-8000-000000000001",
      label: "Maple Leaf Supply Ltd.",
    },
    changes: [
      {
        field: "credit_limit",
        label: "Credit limit",
        old: "5000.00",
        new: "7500.00",
        masked: false,
      },
      {
        field: "bank_account",
        label: "Bank account",
        old: { masked: true },
        new: { masked: true },
        masked: true,
      },
    ],
    meta: {},
    ip: "203.0.113.9",
    device: "Mozilla/5.0",
    request_id: "4f1c0e2b9a7d4c3e8b6a5d4c3b2a1f0e",
    batch_id: null,
    is_batch_summary: false,
    ...overrides,
  };
}

const jobEvent = auditEvent({
  id: "e0000000-0000-4000-8000-000000000002",
  at: "2026-10-26T12:05:00Z",
  action: "contacts.contact.created",
  action_label: "Created",
  verb: "created",
  actor: { kind: "system", label: "System: Import contacts", user: null, impersonator: null },
  record: {
    type: "contacts.Contact",
    type_label: "Contact",
    id: "c2",
    label: "Refined Interiors Inc.",
  },
  changes: [
    { field: "name", label: "Name", old: null, new: "Refined Interiors Inc.", masked: false },
  ],
  meta: {
    job: { id: "j1", task: "numo9.contacts.import", started_by: { id: SAM, label: "Sam Patel" } },
  },
});

const page2Event = auditEvent({
  id: "e0000000-0000-4000-8000-000000000003",
  at: "2026-09-01T14:00:00Z",
  action: "role.updated",
  action_label: "Role edited",
  record: { type: "rbac.Role", type_label: "Role", id: "r1", label: "Buyer" },
  changes: [{ field: "name", label: "Name", old: "Buyer", new: "Senior buyer", masked: false }],
});

const viewer = { locale: "en-ca", time_format: "12h", time_zone: "America/Toronto" };
const defaultRange = {
  from: "2026-08-15",
  to: "2026-11-12",
  default: true,
  time_zone: "America/Toronto",
};

async function mockAudit(page: Page, { denied = false }: { denied?: boolean } = {}) {
  await mockCsrf(page);
  const requests: URL[] = [];
  await page.route(`${API}/filters`, (r) =>
    r.fulfill({
      json: {
        users: [
          { value: "system", label: "System" },
          { value: SAM, label: "Sam Patel (sam@refined.ca)" },
        ],
        types: [
          { value: "contacts.Contact", label: "Contact" },
          { value: "rbac.Role", label: "Role" },
        ],
        actions: [
          { value: "created", label: "Created" },
          { value: "updated", label: "Edited" },
          { value: "deleted", label: "Deleted" },
          { value: "restored", label: "Restored" },
        ],
      },
    }),
  );
  await page.route(`${API}/events?*`, (r) => {
    const url = new URL(r.request().url());
    requests.push(url);
    if (denied) {
      return r.fulfill({
        status: 403,
        json: {
          ...refusal,
          detail: "You don't have permission to see the audit log and the history of records.",
        },
      });
    }
    if (url.searchParams.get("cursor") === "page-2") {
      return r.fulfill({
        json: { results: [page2Event], next: null, range: defaultRange, viewer },
      });
    }
    const user = url.searchParams.get("user");
    const results = user === "system" ? [jobEvent] : [auditEvent(), jobEvent];
    return r.fulfill({
      json: { results, next: user ? null : "page-2", range: defaultRange, viewer },
    });
  });
  await page.route(`${API}/events/*`, (r) => {
    const id = new URL(r.request().url()).pathname.split("/").pop();
    const found = [auditEvent(), jobEvent, page2Event].find((e) => e.id === id);
    return r.fulfill({ json: { ...found, hash: "a".repeat(64), prev_hash: "b".repeat(64) } });
  });
  return requests;
}

test("default range, rows with the person's time format, a11y", async ({ page }) => {
  const requests = await mockAudit(page);
  await page.goto(PAGE);
  await expect(page.getByRole("heading", { level: 1, name: "Audit log" })).toBeVisible();
  const grid = page.getByRole("grid", { name: "Audit log events" });
  await expect(grid.getByRole("row", { name: /Maple Leaf Supply Ltd\./ })).toBeVisible();
  // 20:33 UTC = 4:33 p.m. in Toronto, 12-hour preference — never "16:33PM" (gap-44).
  await expect(grid.getByText("26 Oct 2026, 4:33 p.m.")).toBeVisible();
  await expect(grid.getByText("System: Import contacts")).toBeVisible();
  await expect(
    page.getByText("15 Aug 2026 to 12 Nov 2026 · times in America/Toronto"),
  ).toBeVisible();
  // No dates in the first request: the API's default, the last 90 days.
  expect(requests[0]!.searchParams.has("from")).toBe(false);
  await expectAccessible(page);
});

test("filters reach the API and the export links carry them", async ({ page }) => {
  const requests = await mockAudit(page);
  await page.goto(PAGE);
  await expect(page.getByRole("row", { name: /Maple Leaf Supply Ltd\./ })).toBeVisible();
  const filters = page.getByRole("form", { name: "Filters" });
  await filters.getByRole("combobox", { name: "Dates" }).click();
  await page.getByRole("option", { name: "Last 7 days" }).click();
  await filters.getByRole("combobox", { name: "User" }).click();
  await page.getByRole("option", { name: "System" }).click();
  await filters.getByText("All record types").click();
  await filters.getByRole("checkbox", { name: "Contact" }).click();
  await filters.getByRole("combobox", { name: "Action" }).click();
  await page.getByRole("option", { name: "Created" }).click();
  await filters.getByRole("searchbox", { name: "Search" }).fill("Refined");
  await filters.getByRole("button", { name: "Show" }).click();

  await expect.poll(() => requests.length).toBeGreaterThan(1);
  const last = requests.at(-1)!.searchParams;
  expect(last.get("user")).toBe("system");
  expect(last.getAll("type")).toEqual(["contacts.Contact"]);
  expect(last.get("action")).toBe("created");
  expect(last.get("q")).toBe("Refined");
  expect(last.get("from")).toBeTruthy();
  expect(last.get("to")).toBeTruthy();
  const grid = page.getByRole("grid", { name: "Audit log events" });
  await expect(grid.getByRole("row", { name: /Maple Leaf Supply Ltd\./ })).toHaveCount(0);
  await expect(grid.getByRole("row", { name: /Refined Interiors Inc\./ })).toBeVisible();

  await page.getByText("Export", { exact: true }).click();
  const csv = await page.getByRole("link", { name: "CSV (every row)" }).getAttribute("href");
  const url = new URL(csv!, "http://x");
  expect(url.pathname).toBe(`/api/v1/o/${ORG}/audit/export/csv`);
  for (const key of ["from", "to", "user", "action", "q"]) {
    expect(url.searchParams.get(key)).toBe(last.get(key));
  }
  expect(url.searchParams.getAll("type")).toEqual(["contacts.Contact"]);
  for (const name of ["Excel (XLSX)", "PDF (up to 2,000 rows)"]) {
    await expect(page.getByRole("link", { name })).toHaveAttribute(
      "href",
      /\/audit\/export\/(xlsx|pdf)\?/,
    );
  }

  await filters.getByRole("button", { name: "Reset filters" }).click();
  await expect.poll(() => requests.at(-1)!.search).toBe("");
});

test("custom dates are sent as typed", async ({ page }) => {
  const requests = await mockAudit(page);
  await page.goto(PAGE);
  const filters = page.getByRole("form", { name: "Filters" });
  await filters.getByRole("combobox", { name: "Dates" }).click();
  await page.getByRole("option", { name: "Custom dates" }).click();
  await filters.getByRole("textbox", { name: "From" }).fill("1 Sep 2026");
  await filters.getByRole("textbox", { name: "From" }).press("Tab");
  await filters.getByRole("textbox", { name: "To" }).fill("30 Sep 2026");
  await filters.getByRole("textbox", { name: "To" }).press("Tab");
  await filters.getByRole("button", { name: "Show" }).click();
  await expect.poll(() => requests.at(-1)!.searchParams.get("from")).toBe("2026-09-01");
  expect(requests.at(-1)!.searchParams.get("to")).toBe("2026-09-30");
});

test("an event's DiffViewer: before and after in words, masked values hidden", async ({ page }) => {
  await mockAudit(page);
  await page.goto(PAGE);
  await page.getByRole("row", { name: /Maple Leaf Supply Ltd\./ }).click();
  const drawer = page.getByRole("dialog", { name: "Edited: Maple Leaf Supply Ltd." });
  await expect(drawer).toBeVisible();
  const diff = drawer.getByRole("definition").filter({ hasText: "5000.00" });
  await expect(diff).toContainText("Before");
  await expect(drawer.getByRole("definition").filter({ hasText: "7500.00" })).toContainText(
    "After",
  );
  await expect(drawer.getByText("Changed — the value is hidden for privacy")).toBeVisible();
  await expect(drawer.getByText("203.0.113.9")).toBeVisible();
  await expect(drawer.getByText("4f1c0e2b9a7d4c3e8b6a5d4c3b2a1f0e")).toBeVisible();
  await expectAccessible(page);
  await drawer.getByRole("button", { name: "Close" }).click();
  await expect(drawer).toBeHidden();

  await page.getByRole("row", { name: /Refined Interiors Inc\./ }).click();
  const job = page.getByRole("dialog", { name: "Created: Refined Interiors Inc." });
  await expect(job.getByText("started by Sam Patel")).toBeVisible();
  await expect(job.getByText("numo9.contacts.import")).toBeVisible();
});

test("older events load page by page", async ({ page }) => {
  await mockAudit(page);
  await page.goto(PAGE);
  await expect(page.getByText("2 events shown")).toBeVisible();
  await page.getByRole("button", { name: "Show older events" }).click();
  await expect(page.getByRole("row", { name: /Buyer/ })).toBeVisible();
  await expect(page.getByText("3 events shown")).toBeVisible();
  await expect(page.getByText("That's every event in this range.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Show older events" })).toHaveCount(0);
});

test("someone who may not see the log is told why", async ({ page }) => {
  await mockAudit(page, { denied: true });
  await page.goto(PAGE);
  await expect(
    page.getByText("You don't have permission to see the audit log and the history of records."),
  ).toBeVisible();
  await expect(page.locator("[data-explain=permission]")).toBeVisible();
  await expectAccessible(page);
});

test("phone width: no horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await mockAudit(page);
  await page.goto(PAGE);
  await expect(page.getByRole("heading", { level: 1, name: "Audit log" })).toBeVisible();
  await expectNoHorizontalScroll(page);
});
