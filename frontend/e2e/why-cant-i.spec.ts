import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, expectNoHorizontalScroll, jsonBody, mockCsrf } from "./auth-helpers";
import refusal from "./fixtures/refusal-members-view.json" with { type: "json" };

/**
 * A-03-T14 — "Why can't I?" ExplainPanel and request access. Acceptance: the refusal shows names.
 * The refusal fixture is the real backend answer (403 permission.denied with its explain payload)
 * for a Sales user opening Users and roles (generated from the API, e2e/fixtures/).
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}`;
const PAGE = `/o/${ORG}/settings/users-roles`;

async function mockRefused(page: Page, explain: unknown = refusal.explain) {
  await mockCsrf(page);
  await page.route(`${API}/my-permissions`, (r) =>
    r.fulfill({ json: { permissions: ["organisation.profile.view"] } }),
  );
  await page.route(`${API}/members`, (r) =>
    r.fulfill({ status: 403, json: { ...refusal, explain } }),
  );
  const asked: unknown[] = [];
  await page.route(`${API}/access-requests`, async (r) => {
    asked.push(jsonBody(r));
    await r.fulfill({
      status: asked.length === 1 ? 201 : 200,
      json: {
        id: "0d9c8b7a-6f5e-4d3c-8b2a-190807060504",
        requester: { id: "u-sam", name: "Sam Patel" },
        permission: refusal.explain.permission,
        note: "",
        created_at: "2026-11-11T15:00:00Z",
        notified: 2,
        already_open: asked.length > 1,
      },
    });
  });
  return asked;
}

for (const width of [360, 1280]) {
  test(`the refusal names the permission, who has it and who can give it (${width} px)`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockRefused(page);
    await page.goto(PAGE);
    const panel = page.locator("[data-explain=permission]");
    await expect(panel.getByRole("heading", { name: "You can't do this here yet" })).toBeVisible();
    await expect(panel).toContainText(
      "You don't have permission to see the organisation's users. Ask someone who manages roles here",
    );
    await expect(panel).toContainText(
      "It needs the permission “See the organisation's users” (Users and roles, low risk).",
    );
    await expect(panel).toContainText(
      "Who has it here: Avery Owner (Owner), Bo Books (Accountant delegate), Dana Admin (Admin).",
    );
    await expect(panel).toContainText(
      "Avery Owner, Dana Admin can give you a role that allows it.",
    );
    await expectNoHorizontalScroll(page);
    await expectAccessible(page);
  });
}

test("request access: sent to the people who can give it, then waiting", async ({ page }) => {
  const asked = await mockRefused(page);
  await page.goto(PAGE);
  await page.getByLabel("Note for them (optional)").fill("I need to see who is on the team");
  await page.getByRole("button", { name: "Request access" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Request sent." })).toHaveText(
    "Request sent. 2 people were emailed; you'll get access when one of them gives you a role.",
  );
  expect(asked).toEqual([
    { permission: "organisation.members.view", note: "I need to see who is on the team" },
  ]);
  await expect(page.getByRole("button", { name: "Request access" })).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: "Request access" }).click();
  await expect(
    page.getByText("You already asked for this. It's waiting for an answer."),
  ).toBeVisible();
});

test("nobody to ask: no button, ask the owner", async ({ page }) => {
  await mockRefused(page, {
    ...refusal.explain,
    holders: [],
    holders_total: 0,
    managers: [],
    can_request: false,
  });
  await page.goto(PAGE);
  const panel = page.locator("[data-explain=permission]");
  await expect(panel).toContainText("Nobody else here has it yet.");
  await expect(panel).toContainText(
    "Ask the organisation's owner to give you a role that allows it.",
  );
  await expect(page.getByRole("button", { name: "Request access" })).toHaveCount(0);
});

test("more holders than listed are counted", async ({ page }) => {
  await mockRefused(page, { ...refusal.explain, holders_total: 7 });
  await page.goto(PAGE);
  await expect(page.locator("[data-explain=permission]")).toContainText(
    "Dana Admin (Admin) and 4 others.",
  );
});

test("managers see open access requests on the Users tab and can close them", async ({ page }) => {
  await mockCsrf(page);
  const request = {
    id: "0d9c8b7a-6f5e-4d3c-8b2a-190807060504",
    requester: { id: "u-sam", name: "Sam Patel" },
    permission: refusal.explain.permission,
    note: "I need to see who is on the team",
    created_at: "2026-11-11T15:00:00Z",
    notified: 2,
    already_open: false,
  };
  let open = [request];
  await page.route(`${API}/my-permissions`, (r) =>
    r.fulfill({
      json: {
        permissions: [
          "organisation.members.view",
          "organisation.profile.view",
          "roles.assignment.manage",
          "roles.role.view",
        ],
      },
    }),
  );
  await page.route(`${API}/roles`, (r) => r.fulfill({ json: [] }));
  await page.route(`${API}/invitations`, (r) => r.fulfill({ json: [] }));
  await page.route(`${API}/members`, (r) =>
    r.fulfill({
      json: [
        {
          id: "u-sam",
          name: "Sam Patel",
          email: "sam@refined.ca",
          kind: "member",
          main_role: {
            id: "r",
            key: "sales",
            name: "Sales",
            scope: "organisation",
            is_system: true,
          },
          practices: [],
          roles: [],
        },
      ],
    }),
  );
  await page.route(`${API}/access-requests`, (r) => r.fulfill({ json: open }));
  await page.route(`${API}/access-requests/${request.id}`, async (r) => {
    open = [];
    await r.fulfill({ status: 204, body: "" });
  });
  await page.goto(PAGE);
  const box = page.getByRole("region", { name: "Access requests" });
  await expect(box).toContainText("Sam Patel asks for “See the organisation's users”");
  await expect(box).toContainText("Note: I need to see who is on the team");
  await expect(box.getByRole("button", { name: "Give a role to Sam Patel" })).toBeVisible();
  await box.getByRole("button", { name: "Close the request of Sam Patel" }).click();
  await expect(page.getByRole("region", { name: "Access requests" })).toHaveCount(0);
});
