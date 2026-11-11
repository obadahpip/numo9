import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, expectNoHorizontalScroll, jsonBody, mockCsrf } from "./auth-helpers";
import real from "./fixtures/roles.json" with { type: "json" };

/**
 * A-03-T13 — approval-limit editor per person / role per document type. Acceptance: a limit is
 * saved and enforced. The UI half here (fixtures in the API's shape; "Verify an amount" shows the
 * server's assert_can_approve answer); the enforcement itself is proven against the real service
 * in backend/tests/test_rbac_api.py::test_limit_saved_through_the_api_is_enforced_by_the_check.
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}`;
const people = [
  { id: "a1b2c3d4-0000-4000-8000-000000000001", name: "Avery Owner" },
  { id: "a1b2c3d4-0000-4000-8000-000000000002", name: "Sam Patel" },
].map((p) => ({
  ...p,
  email: `${p.name.split(" ")[0]!.toLowerCase()}@refined.ca`,
  kind: "member",
  main_role: null,
  practices: [],
  roles: [],
}));
const SAM = people[1]!;
const AVERY = people[0]!;
const ADMIN = real.roles.find((r) => r.key === "admin")!;

interface Row {
  id: string;
  doc_type: string;
  max_amount: string;
  user: { id: string; name: string } | null;
  role: { id: string; name: string } | null;
  updated_at: string;
}

async function mockLimits(page: Page, { manage = true }: { manage?: boolean } = {}) {
  await mockCsrf(page);
  const rows: Row[] = [
    {
      id: "l-avery",
      doc_type: "bill",
      max_amount: "100000.00",
      user: { id: AVERY.id, name: AVERY.name },
      role: null,
      updated_at: "2026-11-01T10:00:00Z",
    },
  ];
  const sent: { method: string; body: unknown }[] = [];
  const permissions = [
    "organisation.members.view",
    "organisation.profile.view",
    "roles.limit.view",
    "roles.role.view",
    ...(manage ? ["roles.limit.manage"] : []),
  ];
  await page.route(`${API}/my-permissions`, (r) => r.fulfill({ json: { permissions } }));
  await page.route(`${API}/roles`, (r) => r.fulfill({ json: real.roles }));
  await page.route(`${API}/members`, (r) => r.fulfill({ json: people }));
  await page.route(`${API}/invitations`, (r) => r.fulfill({ json: [] }));
  await page.route(`${API}/approval-limits`, async (r) => {
    if (r.request().method() === "POST") {
      const body = jsonBody(r) as {
        doc_type: string;
        max_amount: string;
        user?: string;
        role?: string;
      };
      sent.push({ method: "POST", body });
      const person = people.find((p) => p.id === body.user);
      const role = real.roles.find((x) => x.id === body.role);
      const row: Row = {
        id: `l-${rows.length}`,
        doc_type: body.doc_type,
        max_amount: Number(body.max_amount).toFixed(2),
        user: person ? { id: person.id, name: person.name } : null,
        role: role ? { id: role.id, name: role.name } : null,
        updated_at: "2026-11-11T10:00:00Z",
      };
      rows.push(row);
      await r.fulfill({ status: 201, json: row });
    } else await r.fulfill({ json: rows });
  });
  await page.route(`${API}/approval-limits/l-*`, async (r) => {
    const id = r.request().url().split("/").pop()!;
    const row = rows.find((x) => x.id === id)!;
    if (r.request().method() === "DELETE") {
      rows.splice(rows.indexOf(row), 1);
      sent.push({ method: "DELETE", body: id });
      return r.fulfill({ status: 204, body: "" });
    }
    const body = jsonBody(r) as { max_amount: string };
    sent.push({ method: "PATCH", body });
    row.max_amount = Number(body.max_amount).toFixed(2);
    return r.fulfill({ json: row });
  });
  // The server's answer (assert_can_approve) for the limits in `rows`.
  await page.route(`${API}/approval-limits/check?*`, (r) => {
    const query = new URL(r.request().url()).searchParams;
    const mine = rows.find(
      (x) => x.user?.id === query.get("user") && x.doc_type === query.get("doc_type"),
    );
    const amount = Number(query.get("amount"));
    if (mine && amount <= Number(mine.max_amount)) {
      return r.fulfill({
        json: { allowed: true, limit: mine.max_amount, code: null, detail: null, approvers: [] },
      });
    }
    return r.fulfill({
      json: {
        allowed: false,
        limit: mine?.max_amount ?? null,
        code: "approval.limit_exceeded",
        detail:
          "This bill is for $5,001.00, above your approval limit of $5,000.00. Ask Avery Owner to approve it.",
        approvers: [{ id: AVERY.id, name: AVERY.name, limit: "100000.00" }],
      },
    });
  });
  return { rows, sent };
}

const PAGE = `/o/${ORG}/settings/users-roles?tab=limits`;

test("limits per document type, lowest-applies explanation, empty types", async ({ page }) => {
  await mockLimits(page);
  await page.goto(PAGE);
  await expect(page.getByRole("tab", { name: "Approval limits", selected: true })).toBeVisible();
  const bills = page.getByRole("table", { name: "Approval limits for Bills" });
  await expect(bills.getByRole("row", { name: /Avery Owner/ })).toContainText("$100,000.00");
  await expect(page.getByText("No limits yet, so nobody can approve pay runs.")).toBeVisible();
  await expect(
    page.getByText("When a person has several limits, the lowest applies."),
  ).toBeVisible();
  await expectAccessible(page);
});

for (const width of [360, 1280]) {
  test(`limit saved, then enforced by Verify an amount (${width} px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const { sent } = await mockLimits(page);
    await page.goto(PAGE);
    const add = page.getByRole("region", { name: "Add a limit" });
    await add.getByRole("combobox", { name: "For" }).click();
    await page.getByRole("option", { name: "Sam Patel" }).click();
    await add.getByLabel("Up to (CAD)").fill("5,000");
    await add.getByRole("button", { name: "Save limit" }).click();
    await expect(
      page.getByText("Limit saved: Sam Patel can approve bills up to $5,000.00", { exact: true }),
    ).toBeVisible();
    expect(sent[0]).toEqual({
      method: "POST",
      body: { doc_type: "bill", max_amount: "5000.00", user: SAM.id },
    });
    const bills = page.getByRole("table", { name: "Approval limits for Bills" });
    await expect(bills.getByRole("row", { name: /Sam Patel/ })).toContainText("$5,000.00");
    await expectNoHorizontalScroll(page);
    // The toast sits over the bottom of the page until it closes (10 s) — close it like a user.
    await page
      .getByRole("region", { name: /Notifications/ })
      .getByRole("button", { name: "Close" })
      .click();

    const check = page.getByRole("region", { name: "Verify an amount" });
    await check.getByRole("combobox", { name: "Person" }).click();
    await page.getByRole("option", { name: "Sam Patel" }).click();
    await check.getByLabel("Up to (CAD)").fill("5001");
    await check.getByRole("button", { name: "Verify" }).click();
    await expect(check.getByRole("status")).toHaveText(
      "This bill is for $5,001.00, above your approval limit of $5,000.00. Ask Avery Owner to approve it.",
    );
    await check.getByLabel("Up to (CAD)").fill("4999.99");
    await check.getByRole("button", { name: "Verify" }).click();
    await expect(check.getByRole("status")).toHaveText(
      "Sam Patel can approve this: their limit is $5,000.00.",
    );
  });
}

test("a limit for a role, change and remove a limit", async ({ page }) => {
  const { sent } = await mockLimits(page);
  await page.goto(PAGE);
  const add = page.getByRole("region", { name: "Add a limit" });
  await add.getByRole("combobox", { name: "Document type" }).click();
  await page.getByRole("option", { name: "Purchase orders" }).click();
  await add.getByRole("combobox", { name: "For" }).click();
  await page.getByRole("option", { name: "Admin", exact: true }).click();
  await add.getByLabel("Up to (CAD)").fill("25000");
  await add.getByRole("button", { name: "Save limit" }).click();
  const pos = page.getByRole("table", { name: "Approval limits for Purchase orders" });
  await expect(pos.getByText("Everyone with Admin")).toBeVisible();
  expect(sent[0]!.body).toEqual({
    doc_type: "purchase_order",
    max_amount: "25000.00",
    role: ADMIN.id,
  });

  const bills = page.getByRole("table", { name: "Approval limits for Bills" });
  await bills.getByRole("button", { name: "Change the limit of Avery Owner" }).click();
  await bills.getByLabel("Change the limit of Avery Owner").fill("90000");
  await bills.getByRole("button", { name: "Save limit" }).click();
  await expect(bills.getByRole("row", { name: /Avery Owner/ })).toContainText("$90,000.00");
  expect(sent[1]).toEqual({ method: "PATCH", body: { max_amount: "90000.00" } });
  await bills.getByRole("button", { name: "Remove the limit of Avery Owner" }).click();
  await expect(page.getByText("No limits yet, so nobody can approve bills.")).toBeVisible();
});

test("validation and the API's refusal are shown", async ({ page }) => {
  await mockLimits(page);
  await page.route(`${API}/approval-limits`, (r) =>
    r.request().method() === "POST"
      ? r.fulfill({
          status: 409,
          json: {
            detail:
              "Sam Patel already has an approval limit for this document type. Change that one instead.",
            code: "limits.duplicate",
          },
        })
      : r.fallback(),
  );
  await page.goto(PAGE);
  const add = page.getByRole("region", { name: "Add a limit" });
  await add.getByRole("button", { name: "Save limit" }).click();
  await expect(add.getByRole("alert")).toHaveText("Choose who this limit is for.");
  await add.getByRole("combobox", { name: "For" }).click();
  await page.getByRole("option", { name: "Sam Patel" }).click();
  await add.getByRole("button", { name: "Save limit" }).click();
  await expect(add.getByRole("alert")).toHaveText("Enter an amount like 5,000.00.");
  await add.getByLabel("Up to (CAD)").fill("10");
  await add.getByRole("button", { name: "Save limit" }).click();
  await expect(add.getByRole("alert")).toContainText("already has an approval limit");
});

test("view-only: no add, change or remove", async ({ page }) => {
  await mockLimits(page, { manage: false });
  await page.goto(PAGE);
  await expect(page.getByRole("table", { name: "Approval limits for Bills" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Add a limit" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Change the limit/ })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Verify an amount" })).toBeVisible();
});
