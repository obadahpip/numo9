import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * B-02-T10 activity tab (filter by type, add a note), B-02-T11 statements tab (preview, PDF link,
 * send, history) and B-02-T12 supplier reconciliation (two columns, totals, manual match, note).
 * Rules are tested on the real API in backend/tests/test_contacts_activity_api.py.
 */
const ORG = "acme";
const C1 = "11111111-1111-4111-8111-111111111111";
const S1 = "33333333-3333-4333-8333-333333333333";
const L1 = "44444444-4444-4444-8444-444444444444";
const BASE = `**/api/v1/o/acme/contacts/${C1}`;

const contact = {
  id: C1,
  number: "C-0001",
  display_name: "Maple Leaf Supply Ltd.",
  legal_name: "",
  roles: ["supplier", "customer"],
  email: "dana@mapleleaf.ca",
  phone: "",
  person: "",
  province: "ON",
  city: "Toronto",
  currency: "CAD",
  bn: "",
  status: "active",
  archived: false,
  tax_id: "",
  credit_limit: null,
  credit_mode: "warn",
  t4a_flag: false,
  portal_enabled: false,
  statement_pref: "email",
  language: "en-ca",
  sales_account: null,
  purchase_account: null,
  sales_amounts_are: "tax_exclusive",
  purchase_amounts_are: "tax_exclusive",
  people: [],
  addresses: [],
  merged_into: null,
};

async function mockContact(page: Page) {
  await mockCsrf(page);
  await page.route(`**/api/v1/o/acme/contacts/${C1}`, (r) => r.fulfill({ json: contact }));
  await page.route("**/api/v1/o/acme/contacts/duplicates?*", (r) =>
    r.fulfill({ json: { results: [] } }),
  );
  await page.route("**/api/v1/o/acme/accounts?*", (r) =>
    r.fulfill({ json: { results: [], count: 0 } }),
  );
}

const types = [
  { value: "invoice_sent", label: "Invoice sent" },
  { value: "payment_received", label: "Payment received" },
  { value: "note", label: "Note" },
];

test("activity: timeline newest first, filter by type, add a note", async ({ page }) => {
  await mockContact(page);
  const notes: string[] = [];
  const requested: string[] = [];
  await page.route(`${BASE}/activity*`, async (r) => {
    if (r.request().method() === "POST") {
      notes.push(String(jsonBody(r).title));
      return r.fulfill({ status: 201, json: { id: "n1" } });
    }
    const type = new URL(r.request().url()).searchParams.get("type");
    requested.push(type ?? "");
    const all = [
      {
        id: "e2",
        type: "payment_received",
        title: "Payment received",
        amount: "250.00",
        currency: "CAD",
        occurred_at: "2026-11-10T15:00:00Z",
        by: "Dana",
      },
      {
        id: "e1",
        type: "invoice_sent",
        title: "Invoice INV-0001 sent",
        amount: "1130.00",
        currency: "CAD",
        occurred_at: "2026-11-01T15:00:00Z",
        by: "",
      },
    ];
    return r.fulfill({
      json: { results: type ? all.filter((e) => e.type === type) : all, types },
    });
  });
  await page.goto(`/o/${ORG}/contacts/${C1}`);
  await page.getByRole("tab", { name: "Activity" }).click();
  const items = page.locator("[data-activity-tab] li");
  await expect(items).toHaveCount(2);
  await expect(items.first()).toContainText("Payment received");
  await expect(items.first()).toContainText("by Dana");
  await page.getByRole("combobox", { name: "Show" }).click();
  await page.getByRole("option", { name: "Invoice sent" }).click();
  await expect(items).toHaveCount(1);
  await expect(items.first()).toContainText("Invoice INV-0001 sent");
  expect(requested).toContain("invoice_sent");
  await page.getByRole("textbox", { name: "Add a note" }).fill("Called about the late payment");
  await page.getByRole("button", { name: "Save note" }).click();
  await expect.poll(() => notes).toEqual(["Called about the late payment"]);
  await expectAccessible(page);
});

test("statements: preview, PDF link, send and history", async ({ page }) => {
  await mockContact(page);
  const history: Record<string, unknown>[] = [];
  let sent: Record<string, unknown> = {};
  await page.route(`${BASE}/statements`, (r) => r.fulfill({ json: { results: history } }));
  await page.route(`${BASE}/statement?*`, (r) =>
    r.fulfill({
      json: {
        kind: "outstanding",
        as_at: "2026-11-18",
        period_start: null,
        currency: "CAD",
        contact: "Maple Leaf Supply Ltd.",
        opening_balance: "0.00",
        lines: [
          {
            date: "2026-10-01",
            document: "INV-0001",
            description: "",
            due_date: "2026-10-31",
            amount: "1130.00",
            balance: "1130.00",
          },
          {
            date: "2026-11-01",
            document: "INV-0002",
            description: "",
            due_date: "2026-12-01",
            amount: "565.00",
            balance: "1695.00",
          },
        ],
        aging: {},
        amount_due: "1695.00",
      },
    }),
  );
  await page.route(`${BASE}/statement/send`, async (r) => {
    sent = jsonBody(r);
    const row = {
      id: "s1",
      kind: "outstanding",
      as_at: "2026-11-18",
      amount_due: "1695.00",
      currency: "CAD",
      recipients: ["dana@mapleleaf.ca"],
      sent_at: "2026-11-18T14:00:00Z",
    };
    history.push(row);
    await r.fulfill({ status: 201, json: row });
  });
  await page.goto(`/o/${ORG}/contacts/${C1}`);
  await page.getByRole("tab", { name: "Statements", exact: true }).click();
  await page.getByLabel("As at").fill("2026-11-18");
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.locator("[data-statement-preview] li")).toHaveCount(3);
  await expect(page.locator("[data-amount-due]")).toContainText("1,695.00");
  await expect(page.getByRole("link", { name: "Open the PDF" })).toHaveAttribute(
    "href",
    new RegExp(`/contacts/${C1}/statement\\.pdf\\?kind=outstanding&as_at=2026-11-18`),
  );
  await page.getByRole("button", { name: "Email the statement" }).click();
  await expect(page.getByRole("tabpanel").getByRole("status")).toHaveText(
    "Statement sent to dana@mapleleaf.ca.",
  );
  expect(sent).toMatchObject({ kind: "outstanding", as_at: "2026-11-18" });
  await expect(page.getByText("Sent before")).toBeVisible();
  await expectAccessible(page);
});

test("supplier statements: two columns, totals, match by hand and a note", async ({ page }) => {
  await mockContact(page);
  const changes: Record<string, unknown>[] = [];
  let matched = false;
  await page.route(`${BASE}/supplier-statements`, (r) =>
    r.fulfill({
      json: { results: [{ id: S1, statement_date: "2026-10-31", file_name: "s.pdf" }] },
    }),
  );
  const theirs = (note = "") => ({
    id: L1,
    date: "2026-10-05",
    invoice_number: "ML-77",
    reference: "",
    description: "",
    amount: "300.00",
    note,
    manual_ref: matched ? "bill:b2" : "",
  });
  const paired = {
    theirs: { ...theirs(), id: "l0", invoice_number: "ML-70", amount: "500.00" },
    ours: {
      ref: "bill:b1",
      date: "2026-10-01",
      document: "ML-70",
      amount: "500.00",
      description: "",
    },
    how: "number",
    difference: "0.00",
  };
  const ourB2 = {
    ref: "bill:b2",
    date: "2026-10-06",
    document: "B-0002",
    amount: "300.00",
    description: "",
  };
  await page.route(`${BASE}/supplier-statements/${S1}/reconciliation`, (r) =>
    r.fulfill({
      json: matched
        ? {
            statement_date: "2026-10-31",
            pairs: [paired, { theirs: theirs(), ours: ourB2, how: "manual", difference: "0.00" }],
            unmatched_theirs: [],
            unmatched_ours: [],
            their_total: "800.00",
            our_total: "800.00",
            difference: "0.00",
          }
        : {
            statement_date: "2026-10-31",
            pairs: [paired],
            unmatched_theirs: [theirs()],
            unmatched_ours: [ourB2],
            their_total: "800.00",
            our_total: "800.00",
            difference: "0.00",
          },
    }),
  );
  await page.route(`${BASE}/supplier-statements/${S1}/lines/${L1}`, async (r) => {
    const change = jsonBody(r);
    changes.push(change);
    if (change.manual_ref) matched = true;
    await r.fulfill({ json: theirs(String(change.note ?? "")) });
  });
  await page.goto(`/o/${ORG}/contacts/${C1}`);
  await page.getByRole("tab", { name: "Supplier statements" }).click();
  await expect(page.locator("[data-recon-totals]")).toContainText("They say");
  await expect(page.getByText("ML-70 ↔ ML-70 (by number)")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Their statement — not matched" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Our bills and payments — not matched" }),
  ).toBeVisible();
  await expect(page.locator("[data-our-item='B-0002']")).toBeVisible();
  await page.getByRole("textbox", { name: /Note on .*ML-77/ }).fill("Credit note to come");
  await page.getByRole("button", { name: "Save note" }).click();
  await expect.poll(() => changes).toContainEqual({ note: "Credit note to come" });
  await expectAccessible(page);
  await page.getByRole("combobox", { name: /Match .*ML-77/ }).click();
  await page.getByRole("option", { name: /B-0002/ }).click();
  await expect.poll(() => changes).toContainEqual({ manual_ref: "bill:b2" });
  await expect(page.getByText("ML-77 ↔ B-0002 (by hand)")).toBeVisible();
});
