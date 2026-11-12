import { expect, test, type Page } from "@playwright/test";

import { auditEvent } from "./audit-fixtures";
import { expectAccessible, mockCsrf } from "./auth-helpers";
import catalogue from "./fixtures/permission-catalogue.json" with { type: "json" };
import real from "./fixtures/roles.json" with { type: "json" };

/**
 * A-04-T10 — record history drawer, the component every detail page puts next to its heading
 * (`src/audit/RecordHistory.tsx`). Acceptance: the drawer on detail pages — mounted today on the
 * role editor (custom roles); the contact (B-01) and account (C-01) detail pages mount the same
 * component when they are built. The history API is answered with fixtures in its real shape
 * (backend/tests/test_audit_api.py).
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}`;
const BUYER_ID = "0b6d3c2e-1f2a-4b3c-8d4e-5f6a7b8c9d0e";
const BUYER = {
  id: BUYER_ID,
  key: "",
  name: "Buyer",
  scope: "organisation",
  is_system: false,
  description: "Site purchases",
  editable: true,
  assignable: true,
  permissions: ["organisation.profile.view"],
  holders: 0,
};
const viewer = { locale: "en-ca", time_format: "24h", time_zone: "America/Toronto" };
const record = { type: "rbac.Role", type_label: "Role", id: BUYER_ID, label: "Buyer" };

const renamed = auditEvent({
  id: "e1",
  at: "2026-11-10T21:05:00Z",
  action: "role.updated",
  action_label: "Role edited",
  record,
  changes: [{ field: "name", label: "Name", old: "Purchaser", new: "Buyer", masked: false }],
});
const created = auditEvent({
  id: "e2",
  at: "2026-06-01T13:00:00Z",
  action: "role.created",
  action_label: "Role created",
  record,
  changes: [{ field: "name", label: "Name", old: null, new: "Purchaser", masked: false }],
});

async function mockRole(page: Page, { history = true }: { history?: boolean } = {}) {
  await mockCsrf(page);
  await page.route("**/api/v1/permissions/catalogue", (r) => r.fulfill({ json: catalogue }));
  await page.route(`${API}/my-permissions`, (r) =>
    r.fulfill({ json: { permissions: real.ownerPermissions } }),
  );
  await page.route(`${API}/roles`, (r) => r.fulfill({ json: [...real.roles, BUYER] }));
  await page.route(`${API}/roles/${BUYER_ID}`, (r) => r.fulfill({ json: BUYER }));
  const asked: string[] = [];
  await page.route(`${API}/audit/records/**`, (r) => {
    const url = new URL(r.request().url());
    asked.push(url.pathname + url.search);
    if (!history)
      return r.fulfill({ status: 404, json: { detail: "Not found.", code: "not_found" } });
    if (url.searchParams.get("cursor") === "older") {
      return r.fulfill({ json: { record, results: [created], next: null, viewer } });
    }
    return r.fulfill({ json: { record, results: [renamed], next: "older", viewer } });
  });
  return asked;
}

test("History on a detail page: the record's changes, newest first, older on demand", async ({
  page,
}) => {
  const asked = await mockRole(page);
  await page.goto(`/o/${ORG}/settings/users-roles/roles/${BUYER_ID}`);
  await page.getByRole("button", { name: "History" }).click();
  const drawer = page.getByRole("dialog", { name: "History of Buyer" });
  await expect(drawer).toBeVisible();
  expect(asked[0]).toBe(`/api/v1/o/${ORG}/audit/records/rbac.Role/${BUYER_ID}`);
  const timeline = drawer.getByRole("list", { name: "Changes, newest first" });
  await expect(timeline.getByRole("listitem")).toHaveCount(1);
  // 21:05 UTC = 16:05 in Toronto; the viewer prefers 24-hour time.
  await expect(timeline.getByText("10 Nov 2026, 16:05")).toBeVisible();
  await expect(timeline.getByText("Purchaser")).toBeVisible();
  await expectAccessible(page);

  await drawer.getByRole("button", { name: "Show older changes" }).click();
  await expect(timeline.getByRole("listitem")).toHaveCount(2);
  await expect(timeline.getByRole("listitem").nth(1)).toContainText("Role created");
  await expect(drawer.getByRole("button", { name: "Show older changes" })).toHaveCount(0);

  const link = drawer.getByRole("link", { name: "Open in the audit log" });
  const href = new URL((await link.getAttribute("href"))!, "http://x");
  expect(href.pathname).toBe(`/o/${ORG}/settings/audit-log`);
  expect(href.searchParams.get("object_type")).toBe("rbac.Role");
  expect(href.searchParams.get("object_id")).toBe(BUYER_ID);
});

test("a record without history says so", async ({ page }) => {
  await mockRole(page, { history: false });
  await page.goto(`/o/${ORG}/settings/users-roles/roles/${BUYER_ID}`);
  await page.getByRole("button", { name: "History" }).click();
  await expect(page.getByText("No changes recorded for this record yet.")).toBeVisible();
});

test("system roles have no History button (they are not an organisation's records)", async ({
  page,
}) => {
  await mockRole(page);
  const owner = real.roles.find((r) => r.key === "owner")!;
  await page.goto(`/o/${ORG}/settings/users-roles/roles/${owner.id}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("button", { name: "History" })).toHaveCount(0);
});
