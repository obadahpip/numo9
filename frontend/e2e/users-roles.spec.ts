import { expect, test, type Page, type Route } from "@playwright/test";

import { expectAccessible, expectNoHorizontalScroll, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * A-03-T11 — Settings → Users and roles: members list, role chips, give/take roles, invite
 * (A-02 invitation API). Acceptance: assign a role via the UI. The API is answered with fixtures
 * in the shape of the real one (backend/tests/test_rbac_api.py checks those shapes); the screen
 * was also run against the real backend when built.
 */
export const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}`;

const role = (id: string, key: string, name: string, extra: Record<string, unknown> = {}) => ({
  id,
  key,
  name,
  scope: "organisation",
  is_system: key !== "",
  description: "",
  editable: key === "",
  assignable: true,
  permissions: ["organisation.profile.view"],
  holders: 0,
  ...extra,
});

export const ROLES = [
  role("r-owner", "owner", "Owner", { holders: 1 }),
  role("r-admin", "admin", "Admin"),
  role("r-sales", "sales", "Sales"),
  role("r-purchasing", "purchasing", "Purchasing", { holders: 1 }),
  role("r-employee", "employee", "Employee"),
  role("r-buyer", "", "Buyer"),
  role("r-accountant", "accountant", "Accountant", { scope: "practice", assignable: false }),
];

const ref = (r: (typeof ROLES)[number]) => ({
  id: r.id,
  key: r.key,
  name: r.name,
  scope: r.scope,
  is_system: r.is_system,
});

const AVERY = {
  id: "u-avery",
  name: "Avery Owner",
  email: "avery@refined.ca",
  kind: "member",
  main_role: ref(ROLES[0]!),
  practices: [],
  roles: [],
};
const SAM = {
  id: "u-sam",
  name: "Sam Patel",
  email: "sam@refined.ca",
  kind: "member",
  main_role: ref(ROLES[3]!),
  practices: [],
  roles: [] as ReturnType<typeof ref>[],
};
const ALI = {
  id: "u-ali",
  name: "Ali Accountant",
  email: "ali@profitex.ca",
  kind: "practice",
  main_role: null,
  practices: [{ id: "p-1", name: "Profitex", role: "accountant", role_name: "Accountant" }],
  roles: [],
};

export const OWNER_PERMISSIONS = [
  "organisation.members.view",
  "organisation.members.invite",
  "organisation.profile.view",
  "roles.assignment.manage",
  "roles.limit.manage",
  "roles.limit.view",
  "roles.role.manage",
  "roles.role.view",
];

export async function mockScreen(
  page: Page,
  { permissions = OWNER_PERMISSIONS }: { permissions?: string[] } = {},
) {
  await mockCsrf(page);
  const state = { sam: { ...SAM, roles: [...SAM.roles] }, posted: [] as unknown[] };
  await page.route(`${API}/my-permissions`, (r) => r.fulfill({ json: { permissions } }));
  await page.route(`${API}/roles`, (r) => r.fulfill({ json: ROLES }));
  await page.route(`${API}/members`, (r) => r.fulfill({ json: [AVERY, state.sam, ALI] }));
  await page.route(`${API}/invitations`, (r) =>
    r.fulfill({
      json: [
        {
          id: "i-1",
          email: "new@refined.ca",
          role: "sales",
          expires_at: "2026-11-18T15:00:00Z",
          inviter_name: "Avery Owner",
        },
      ],
    }),
  );
  await page.route(`${API}/members/u-sam/roles`, async (r: Route) => {
    const body = jsonBody(r);
    state.posted.push(body);
    const chosen = ROLES.find((x) => x.id === body.role)!;
    if (chosen.is_system) state.sam.main_role = ref(chosen);
    else state.sam.roles = [...state.sam.roles, ref(chosen)];
    await r.fulfill({ status: chosen.is_system ? 200 : 201, json: state.sam });
  });
  await page.route(`${API}/members/u-sam/roles/r-buyer`, async (r) => {
    state.sam.roles = state.sam.roles.filter((x) => x.id !== "r-buyer");
    await r.fulfill({ status: 204, body: "" });
  });
  return state;
}

const PAGE = `/o/${ORG}/settings/users-roles`;

test("members, their role chips and access, pending invitations", async ({ page }) => {
  await mockScreen(page);
  await page.goto(PAGE);
  await expect(page.getByRole("heading", { level: 1, name: "Users and roles" })).toBeVisible();
  const table = page.getByRole("table", { name: "People who can work in this organisation" });
  const sam = table.getByRole("row", { name: /Sam Patel/ });
  await expect(sam.getByText("Purchasing (main role)")).toBeVisible();
  await expect(sam.getByText("Member", { exact: true })).toBeVisible();
  const ali = table.getByRole("row", { name: /Ali Accountant/ });
  await expect(ali.getByText("Through Profitex (Accountant)")).toBeVisible();
  await expect(
    page.getByText("new@refined.ca · Sales · invited by Avery Owner · expires 18 Nov 2026"),
  ).toBeVisible();
  await expectAccessible(page);
});

for (const width of [360, 1280]) {
  test(`give a custom role, then take it away (${width} px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const state = await mockScreen(page);
    await page.goto(PAGE);
    await expect(page.getByRole("row", { name: /Sam Patel/ })).toBeVisible();
    await expectNoHorizontalScroll(page);
    await page.getByRole("button", { name: "Give a role to Sam Patel" }).click();
    const dialog = page.getByRole("dialog", { name: "Give a role to Sam Patel" });
    await dialog.getByRole("combobox", { name: "Role" }).click();
    await page.getByRole("option", { name: "Buyer" }).click();
    await dialog.getByRole("button", { name: "Give role" }).click();
    await expect(dialog).toBeHidden();
    expect(state.posted).toEqual([{ role: "r-buyer" }]);
    const sam = page.getByRole("row", { name: /Sam Patel/ });
    await expect(sam.getByText("Buyer", { exact: true })).toBeVisible();
    await expect(page.getByText("Sam Patel now has the role Buyer", { exact: true })).toBeVisible();

    await sam.getByRole("button", { name: "Take Buyer away from Sam Patel" }).click();
    await expect(sam.getByText("Buyer", { exact: true })).toBeHidden();
    await expect(page.getByText("Buyer taken away from Sam Patel", { exact: true })).toBeVisible();
  });
}

test("a main role replaces the member's main role", async ({ page }) => {
  const state = await mockScreen(page);
  await page.goto(PAGE);
  await page.getByRole("button", { name: "Give a role to Sam Patel" }).click();
  const dialog = page.getByRole("dialog", { name: "Give a role to Sam Patel" });
  await expect(
    dialog.getByText("A main role replaces the one they have. A custom role is added"),
  ).toBeVisible();
  await dialog.getByRole("combobox", { name: "Role" }).click();
  await expect(page.getByRole("option", { name: "Purchasing" })).toHaveCount(0); // already held
  await expect(page.getByRole("option", { name: "Accountant" })).toHaveCount(0); // practice role
  await page.getByRole("option", { name: "Admin" }).click();
  await dialog.getByRole("button", { name: "Give role" }).click();
  await expect(dialog).toBeHidden();
  expect(state.posted).toEqual([{ role: "r-admin" }]);
  await expect(
    page.getByRole("row", { name: /Sam Patel/ }).getByText("Admin (main role)"),
  ).toBeVisible();
});

test("a refused change shows the API's reason in the dialog", async ({ page }) => {
  await mockScreen(page);
  await page.route(`${API}/members/u-sam/roles`, (r) =>
    r.fulfill({
      status: 403,
      json: {
        detail:
          "You can only give permissions you have yourself. You don't have: Close the organisation. Ask an owner to do this.",
        code: "roles.grant_exceeds_own",
        permissions: ["organisation.close"],
      },
    }),
  );
  await page.goto(PAGE);
  await page.getByRole("button", { name: "Give a role to Sam Patel" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("combobox", { name: "Role" }).click();
  await page.getByRole("option", { name: "Owner" }).click();
  await dialog.getByRole("button", { name: "Give role" }).click();
  await expect(dialog.getByRole("alert")).toContainText("You can only give permissions you have");
  await expectAccessible(page);
});

test("invite a user (A-02 invitation API)", async ({ page }) => {
  await mockScreen(page);
  const sent: unknown[] = [];
  await page.route("**/api/v1/invitations", async (r) => {
    sent.push(jsonBody(r));
    await r.fulfill({ status: 201, json: {} });
  });
  await page.goto(PAGE);
  await page.getByRole("button", { name: "Invite a user" }).click();
  const dialog = page.getByRole("dialog", { name: "Invite a user" });
  await dialog.getByLabel("Email").fill("not-an-email");
  await dialog.getByRole("button", { name: "Send invitation" }).click();
  await expect(dialog.getByRole("alert")).toHaveText(
    "Enter an email address like 'sam@refined.ca'.",
  );
  await dialog.getByLabel("Email").fill("lee@refined.ca");
  await dialog.getByRole("combobox", { name: "Role" }).click();
  await page.getByRole("option", { name: "Sales" }).click();
  await dialog.getByRole("button", { name: "Send invitation" }).click();
  await expect(dialog).toBeHidden();
  expect(sent).toEqual([
    { kind: "organisation_user", email: "lee@refined.ca", role: "sales", organisation: ORG },
  ]);
  await expect(page.getByText("Invitation sent to lee@refined.ca", { exact: true })).toBeVisible();
});

test("people who may only look see no buttons", async ({ page }) => {
  await mockScreen(page, {
    permissions: ["organisation.members.view", "organisation.profile.view", "roles.role.view"],
  });
  await page.goto(PAGE);
  await expect(page.getByRole("row", { name: /Sam Patel/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Give a role/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Invite a user" })).toHaveCount(0);
});

test("an organisation the user can't access answers like an unknown one", async ({ page }) => {
  await mockCsrf(page);
  await page.route(`${API}/my-permissions`, (r) =>
    r.fulfill({ status: 404, json: { detail: "Not found.", code: "not_found" } }),
  );
  await page.goto(PAGE);
  await expect(
    page.getByRole("heading", { name: "This organisation isn't available" }),
  ).toBeVisible();
});
