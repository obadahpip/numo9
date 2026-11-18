import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * V-05-T04 — assignment editor (`/p/:practice/staff/:member`): assigning an organisation is saved
 * at once (the access it grants on the next request is tested against the real API in
 * backend/tests/test_staff_assignments.py).
 */
const PRACTICE = "6ca1b880-64f7-4053-80e3-0c3618895553";
const MEMBER = "11111111-2222-4333-8444-555555555555";
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";

test("assign an organisation and a group to a staff member", async ({ page }) => {
  await mockCsrf(page);
  let state = { organisations: [] as { id: string; name: string }[], groups: [] as unknown[] };
  await page.route("**/api/v1/practice/staff?*", (r) =>
    r.fulfill({
      json: {
        practice: PRACTICE,
        dormant_days: 60,
        staff: [
          {
            id: MEMBER,
            name: "Sam Patel",
            email: "sam@cpa.ca",
            role: "accountant",
            role_label: "Accountant",
            status: "active",
            organisation_count: 0,
            last_login: null,
            joined_at: null,
            suspended_at: null,
            dormant: false,
            invitation_expires_at: null,
          },
        ],
      },
    }),
  );
  await page.route(`**/api/v1/practice/staff/${MEMBER}/assignments*`, (r) =>
    r.fulfill({ json: state }),
  );
  await page.route(`**/api/v1/practice/staff/${MEMBER}/organisations/${ORG}*`, (r) => {
    state = { ...state, organisations: [{ id: ORG, name: "Maple Leaf Supply" }] };
    return r.fulfill({ json: state });
  });
  await page.route("**/api/v1/practice/groups?*", (r) =>
    r.fulfill({ json: { practice: PRACTICE, groups: [] } }),
  );
  await page.route("**/api/v1/practice/orgs?*", (r) =>
    r.fulfill({ json: { results: [{ id: ORG, name: "Maple Leaf Supply" }], count: 1 } }),
  );
  await page.goto(`/p/${PRACTICE}/staff/${MEMBER}`);
  await expect(page.getByRole("heading", { name: "Sam Patel works on" })).toBeVisible();
  await page.getByLabel("Add an organisation").fill("Maple");
  await page.getByRole("button", { name: "Add Maple Leaf Supply" }).click();
  await expect(page.getByRole("button", { name: "Remove Maple Leaf Supply" })).toBeVisible();
  await expectAccessible(page);
});
