import { expect, test } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * V-05-T03 — invite a staff member with a practice role (the A-02 invitation flow); the
 * invitation is Pending in the staff list with its expiry (14 days) and can be resent or
 * withdrawn. The 14-day expiry itself is tested on the real API: backend/tests/test_staff_invite.py.
 */
const PRACTICE = "6ca1b880-64f7-4053-80e3-0c3618895553";
const INVITE = "55555555-6666-4777-8888-999999999999";
const inFourteenDays = new Date(Date.now() + 14 * 86_400_000).toISOString();

test("invite a reviewer, see the pending line, resend and withdraw it", async ({ page }) => {
  await mockCsrf(page);
  await page.route("**/api/v1/practice/staff?*", (r) =>
    r.fulfill({
      json: {
        practice: PRACTICE,
        dormant_days: 60,
        staff: [
          {
            id: "11111111-2222-4333-8444-555555555555",
            name: "Ada Admin",
            email: "ada@cpa.ca",
            role: "practice_admin",
            role_label: "Practice admin",
            status: "active",
            organisation_count: 3,
            last_login: "2026-11-10T15:00:00Z",
            joined_at: "2026-01-05T15:00:00Z",
            suspended_at: null,
            dormant: false,
            invitation_expires_at: null,
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/practice/staff/dormant?*", (r) =>
    r.fulfill({ json: { dormant_days: 60, staff: [] } }),
  );
  const sent: Record<string, unknown>[] = [];
  const invitation = (over: Record<string, unknown> = {}) => ({
    id: INVITE,
    kind: "practice_staff",
    email: "nina@cpa.ca",
    role: "reviewer",
    status: "pending",
    expires_at: inFourteenDays,
    target_name: "Abuodeh CPA",
    target_id: PRACTICE,
    inviter_name: "Ada Admin",
    ...over,
  });
  await page.route("**/api/v1/invitations", (r) => {
    sent.push(jsonBody(r));
    return r.fulfill({ status: 201, json: invitation() });
  });
  let resent = 0;
  await page.route(`**/api/v1/invitations/${INVITE}/resend`, (r) => {
    resent += 1;
    return r.fulfill({ json: invitation() });
  });
  await page.route(`**/api/v1/invitations/${INVITE}/revoke`, (r) =>
    r.fulfill({ json: invitation({ status: "revoked" }) }),
  );

  await page.goto(`/p/${PRACTICE}/staff`);
  await page.getByRole("button", { name: "Invite staff" }).click();
  const dialog = page.getByRole("dialog", { name: "Invite a staff member" });
  await expect(dialog.getByText(/for 14 days/)).toBeVisible();
  await dialog.getByLabel("Email").fill("nina@cpa.ca");
  await dialog.getByLabel("Practice role").selectOption("reviewer");
  await dialog.getByRole("button", { name: "Send invitation" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Invitation sent to nina@cpa.ca." }),
  ).toBeVisible();
  expect(sent).toEqual([
    { kind: "practice_staff", practice: PRACTICE, email: "nina@cpa.ca", role: "reviewer" },
  ]);

  const grid = page.getByRole("grid", { name: "Staff" });
  await expect(grid.getByText("nina@cpa.ca").first()).toBeVisible();
  await expect(grid.getByText("Invitation pending", { exact: true })).toBeVisible();
  await expect(grid.getByText("Reviewer", { exact: true })).toBeVisible();
  await expectAccessible(page);

  await grid.getByRole("button", { name: "Resend the invitation to nina@cpa.ca" }).click();
  await expect(page.getByText("Sent again to nina@cpa.ca: a new link for 14 days.")).toBeVisible();
  expect(resent).toBe(1);
  await grid.getByRole("button", { name: "Withdraw the invitation to nina@cpa.ca" }).click();
  await expect(page.getByText("Invitation to nina@cpa.ca withdrawn.")).toBeVisible();
  await expect(grid.getByText("Invitation pending", { exact: true })).toHaveCount(0);
});
