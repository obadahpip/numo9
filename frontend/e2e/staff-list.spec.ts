import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * V-05-T09 — staff list and a staff member's page: loading, error with retry, empty, every status
 * (active, dormant, suspended, pending with its expiry), opening a person, suspend and the server's
 * last-admin refusal shown as is. The rules themselves are tested on the real API in
 * backend/tests/test_staff_members.py and test_staff_list.py.
 */
const PRACTICE = "6ca1b880-64f7-4053-80e3-0c3618895553";
const SAM = "11111111-2222-4333-8444-555555555555";
const DANA = "22222222-3333-4444-8555-666666666666";

const line = (over: Record<string, unknown>) => ({
  id: SAM,
  name: "Sam Patel",
  email: "sam@cpa.ca",
  role: "accountant",
  role_label: "Accountant",
  status: "active",
  organisation_count: 4,
  last_login: "2026-11-10T15:00:00Z",
  joined_at: "2026-01-05T15:00:00Z",
  suspended_at: null,
  dormant: false,
  invitation_expires_at: null,
  ...over,
});

const STAFF = [
  line({}),
  line({
    id: DANA,
    name: "Dana Lee",
    email: "dana@cpa.ca",
    role: "admin",
    role_label: "Practice admin",
    last_login: "2026-08-01T15:00:00Z",
    dormant: true,
  }),
  line({
    id: "33333333-4444-4555-8666-777777777777",
    name: "Alex Roy",
    email: "alex@cpa.ca",
    status: "suspended",
    organisation_count: 0,
  }),
  line({
    id: "44444444-5555-4666-8777-888888888888",
    name: "",
    email: "new@cpa.ca",
    status: "pending",
    organisation_count: 0,
    last_login: null,
    joined_at: null,
    invitation_expires_at: "2026-11-30T15:00:00Z",
  }),
];

async function mockStaff(page: Page, staff: unknown[] | "error") {
  await mockCsrf(page);
  await page.route("**/api/v1/practice/staff?*", (r) =>
    staff === "error"
      ? r.fulfill({ status: 500, json: { detail: "boom" } })
      : r.fulfill({ json: { practice: PRACTICE, dormant_days: 60, staff } }),
  );
  await page.route("**/api/v1/practice/staff/dormant?*", (r) =>
    r.fulfill({ json: { dormant_days: 60, staff: [] } }),
  );
}

test("staff list shows every status and opens a person", async ({ page }) => {
  await mockStaff(page, STAFF);
  await page.goto(`/p/${PRACTICE}/staff`);
  await expect(page.getByRole("heading", { name: "Staff", level: 1 })).toBeVisible();
  const grid = page.getByRole("grid", { name: "Staff" });
  await expect(grid.getByRole("link", { name: "Sam Patel" })).toBeVisible();
  await expect(grid.getByText("Dormant", { exact: true })).toBeVisible();
  await expect(grid.getByText("Suspended", { exact: true })).toBeVisible();
  await expect(grid.getByText("Invitation pending")).toBeVisible();
  await expect(grid.getByText("Expires 30 Nov 2026")).toBeVisible();
  await expect(grid.getByText("Never signed in")).toBeVisible();
  // A pending invitation has no page yet.
  await expect(grid.getByRole("link", { name: "new@cpa.ca" })).toHaveCount(0);
  await expectAccessible(page);
  await page.route(`**/api/v1/practice/staff/${SAM}/**`, (r) =>
    r.fulfill({ json: { organisations: [], groups: [] } }),
  );
  await grid.getByRole("link", { name: "Sam Patel" }).click();
  await expect(page).toHaveURL(new RegExp(`/p/${PRACTICE}/staff/${SAM}$`));
});

test("staff list: empty, then error with retry", async ({ page }) => {
  await mockStaff(page, []);
  await page.goto(`/p/${PRACTICE}/staff`);
  await expect(page.getByRole("heading", { name: "Nobody here yet" })).toBeVisible();

  await page.unrouteAll();
  await mockStaff(page, "error");
  await page.reload();
  await expect(page.getByRole("heading", { name: "We couldn't load your staff" })).toBeVisible();
  await page.unroute("**/api/v1/practice/staff?*");
  await page.route("**/api/v1/practice/staff?*", (r) =>
    r.fulfill({ json: { practice: PRACTICE, dormant_days: 60, staff: STAFF } }),
  );
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("link", { name: "Sam Patel" })).toBeVisible();
});

test("staff member: suspend, and the last-admin refusal is explained", async ({ page }) => {
  await mockStaff(page, STAFF);
  await page.route(`**/api/v1/practice/staff/*/assignments*`, (r) =>
    r.fulfill({ json: { organisations: [], groups: [] } }),
  );
  await page.route(`**/api/v1/practice/staff/*/activity*`, (r) =>
    r.fulfill({ json: { from: "2025-11-19", to: "2026-11-18", total: 0, days: [] } }),
  );
  await page.route("**/api/v1/practice/groups?*", (r) =>
    r.fulfill({ json: { practice: PRACTICE, groups: [] } }),
  );
  await page.route(`**/api/v1/practice/staff/${SAM}/suspend*`, (r) =>
    r.fulfill({ json: line({ status: "suspended", suspended_at: "2026-11-18T15:00:00Z" }) }),
  );
  await page.route(`**/api/v1/practice/staff/${DANA}/suspend*`, (r) =>
    r.fulfill({
      status: 409,
      json: {
        code: "staff.last_admin",
        detail:
          "Dana Lee is the practice's only active practice admin. Make someone else a practice admin first.",
      },
    }),
  );

  await page.goto(`/p/${PRACTICE}/staff/${SAM}`);
  await expect(page.getByRole("heading", { name: "Sam Patel", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Suspend access" }).click();
  await expect(
    page.getByRole("status").getByText("Sam Patel's access is suspended."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Lift suspension" })).toBeVisible();
  await expectAccessible(page);

  await page.goto(`/p/${PRACTICE}/staff/${DANA}`);
  await page.getByRole("button", { name: "Suspend access" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Dana Lee" })).toContainText(
    "only active practice admin",
  );
  await page.getByRole("button", { name: "Remove from practice" }).click();
  await expect(
    page.getByRole("dialog", { name: "Remove Dana Lee from the practice?" }),
  ).toBeVisible();
});
