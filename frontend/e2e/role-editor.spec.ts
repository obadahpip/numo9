import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, expectNoHorizontalScroll, jsonBody, mockCsrf } from "./auth-helpers";
import catalogue from "./fixtures/permission-catalogue.json" with { type: "json" };
import real from "./fixtures/roles.json" with { type: "json" };

/**
 * A-03-T12 — role editor: permission matrix by module, search, copy from role, risk badges.
 * Acceptance: create a custom role in under a minute. Fixtures: the real catalogue and the real
 * roles list of an organisation (generated from the backend API, e2e/fixtures/).
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}`;
const BUYER_ID = "0b6d3c2e-1f2a-4b3c-8d4e-5f6a7b8c9d0e";
const roles = real.roles;
const byName = (name: string) => roles.find((r) => r.name === name)!;
const OWNER = real.ownerPermissions;
const ADMIN = byName("Admin").permissions;

const BUYER = {
  id: BUYER_ID,
  key: "",
  name: "Buyer",
  scope: "organisation",
  is_system: false,
  description: "Site purchases",
  editable: true,
  assignable: true,
  permissions: ["organisation.profile.view", "organisation.members.view"],
  holders: 0,
};

async function mockEditor(page: Page, { mine = OWNER }: { mine?: string[] } = {}) {
  await mockCsrf(page);
  const sent: { method: string; body: unknown }[] = [];
  await page.route("**/api/v1/permissions/catalogue", (r) => r.fulfill({ json: catalogue }));
  await page.route(`${API}/my-permissions`, (r) => r.fulfill({ json: { permissions: mine } }));
  await page.route(`${API}/members`, (r) => r.fulfill({ json: [] }));
  await page.route(`${API}/invitations`, (r) => r.fulfill({ json: [] }));
  await page.route(`${API}/roles`, async (r) => {
    if (r.request().method() === "POST") {
      const body = jsonBody(r) as { name: string; permissions: string[] };
      sent.push({ method: "POST", body });
      await r.fulfill({ status: 201, json: { ...BUYER, id: crypto.randomUUID(), ...body } });
    } else {
      await r.fulfill({ json: [...roles, BUYER] });
    }
  });
  await page.route(`${API}/roles/${BUYER_ID}`, async (r) => {
    const body = r.request().method() === "DELETE" ? null : jsonBody(r);
    sent.push({ method: r.request().method(), body });
    await r.fulfill(
      r.request().method() === "DELETE"
        ? { status: 204, body: "" }
        : { json: { ...BUYER, ...body } },
    );
  });
  return sent;
}

test("create a custom role in under a minute: copy, search, tick, save", async ({ page }) => {
  const sent = await mockEditor(page);
  const started = Date.now();
  await page.goto(`/o/${ORG}/settings/users-roles?tab=roles`);
  await page.getByRole("link", { name: "New role" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "New custom role" })).toBeVisible();

  await page.getByLabel("Name", { exact: true }).fill("Showroom");
  await page.getByRole("combobox", { name: "Copy from role" }).click();
  await page.getByRole("option", { name: "Accountant delegate" }).click();
  await expect(page.getByText("Permissions copied from Accountant delegate.")).toBeVisible();
  const delegate = byName("Accountant delegate").permissions.length;
  await expect(page.getByText(`${delegate} of 12 permissions selected`)).toBeVisible();

  await page.getByLabel("Search permissions").fill("invite");
  await expect(page.getByRole("group", { name: "Settings" })).toHaveCount(0); // filtered out
  const invite = page.getByRole("checkbox", { name: "Invite users to the organisation" });
  await invite.check();
  await expect(invite).toBeChecked();
  await expect(page.getByText(`${delegate + 1} of 12 permissions selected`)).toBeVisible();

  await page.getByRole("button", { name: "Save role" }).click();
  await expect(page).toHaveURL(/tab=roles&saved=Showroom/);
  await expect(page.getByRole("status").filter({ hasText: "Role Showroom saved" })).toBeVisible();
  expect(Date.now() - started).toBeLessThan(60_000);
  expect(sent).toHaveLength(1);
  const body = sent[0]!.body as { name: string; permissions: string[]; description: string };
  expect(body.name).toBe("Showroom");
  expect(body.permissions).toEqual(
    [...byName("Accountant delegate").permissions, "organisation.members.invite"].sort(),
  );
});

test("matrix grouped by module with risk badges, select all in a module", async ({ page }) => {
  await mockEditor(page);
  await page.goto(`/o/${ORG}/settings/users-roles/roles/new`);
  const users = page.getByRole("group", { name: "Users and roles" });
  await expect(users).toBeVisible();
  await expect(page.getByRole("group", { name: "Settings" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Practice" })).toHaveCount(0); // not grantable
  const close = page.getByRole("group", { name: "Settings" }).getByRole("listitem").filter({
    hasText: "Close the organisation",
  });
  await expect(close.getByText("Critical")).toBeVisible();
  await expect(close.getByText("Owners only by default")).toBeVisible();
  await users.getByRole("checkbox", { name: "Everything in Users and roles" }).check();
  const usersCount = catalogue.permissions.filter(
    (p) => p.module === "users" && p.scope === "organisation",
  ).length;
  await expect(page.getByText(`${usersCount} of 12 permissions selected`)).toBeVisible();
  await page.getByLabel("Search permissions").fill("nothing like this");
  await expect(page.getByText("No permission matches “nothing like this”.")).toBeVisible();
  await expectAccessible(page);
});

test("permissions the editor doesn't hold can't be ticked (no escalation)", async ({ page }) => {
  await mockEditor(page, { mine: ADMIN });
  await page.goto(`/o/${ORG}/settings/users-roles/roles/new`);
  const close = page.getByRole("checkbox", { name: "Close the organisation" });
  await expect(close).toBeDisabled();
  await expect(
    page.getByText("You don't have this permission, so you can't give it."),
  ).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Change organisation settings" })).toBeEnabled();
});

test("system role opens read-only with Copy into a custom role", async ({ page }) => {
  await mockEditor(page);
  const sales = byName("Sales");
  await page.goto(`/o/${ORG}/settings/users-roles/roles/${sales.id}`);
  await expect(page.getByRole("heading", { level: 1, name: "Sales (system role)" })).toBeVisible();
  await expect(
    page.getByRole("checkbox", { name: "View the organisation's details" }),
  ).toBeDisabled();
  await expect(page.getByRole("button", { name: "Save role" })).toHaveCount(0);
  await page.getByRole("link", { name: "Copy into a custom role" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "New custom role" })).toBeVisible();
  await expect(page.getByText("1 of 12 permissions selected")).toBeVisible();
});

for (const width of [360, 1280]) {
  test(`edit and delete a custom role (${width} px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const sent = await mockEditor(page);
    await page.goto(`/o/${ORG}/settings/users-roles/roles/${BUYER_ID}`);
    await expect(page.getByRole("heading", { level: 1, name: "Edit Buyer" })).toBeVisible();
    await expectNoHorizontalScroll(page);
    await page.getByRole("checkbox", { name: "See the organisation's users" }).uncheck();
    await page.getByRole("button", { name: "Save role" }).click();
    await expect(page).toHaveURL(/saved=Buyer/);
    expect(sent[0]).toEqual({
      method: "PATCH",
      body: {
        name: "Buyer",
        description: "Site purchases",
        permissions: ["organisation.profile.view"],
      },
    });
    await page.goto(`/o/${ORG}/settings/users-roles/roles/${BUYER_ID}`);
    await page.getByRole("button", { name: "Delete role" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Delete role" }).click();
    await expect(page).toHaveURL(/deleted=Buyer/);
    await expect(page.getByRole("status").filter({ hasText: "Role Buyer deleted" })).toBeVisible();
  });
}

test("roles tab: system and custom roles with holders", async ({ page }) => {
  await mockEditor(page);
  await page.goto(`/o/${ORG}/settings/users-roles?tab=roles`);
  const list = page.getByRole("list", { name: "Roles of this organisation" });
  const owner = list.getByRole("listitem").filter({ hasText: "Owner" }).first();
  await expect(owner.getByText("System role")).toBeVisible();
  await expect(owner.getByText("1 person · 12 permissions")).toBeVisible();
  const buyer = list.getByRole("listitem").filter({ hasText: "Buyer" });
  await expect(buyer.getByText("Custom role")).toBeVisible();
  await expect(buyer.getByText("Nobody has it · 2 permissions")).toBeVisible();
  await expect(list.getByText("Practice admin")).toHaveCount(0); // practice roles not listed
  await expectAccessible(page);
});
