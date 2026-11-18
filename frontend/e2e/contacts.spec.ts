import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * B-01-T14 contacts list (the title names the role's list — gap-19 —, counts, search, saved view,
 * archive), B-01-T15 contact form (sections, people, address with province and postal code,
 * server errors on their fields) and B-01-T17 merge dialog (field chooser, records that move).
 * Rules are tested on the real API in backend/tests/test_contacts_api.py and test_contacts_merge.py.
 */
const ORG = "acme";
const C1 = "11111111-1111-4111-8111-111111111111";
const C2 = "22222222-2222-4222-8222-222222222222";
const summary = (
  id: string,
  name: string,
  roles: string[],
  over: Record<string, unknown> = {},
) => ({
  id,
  number: id === C1 ? "C-0001" : "C-0002",
  display_name: name,
  legal_name: "",
  roles,
  email: "",
  phone: "",
  person: "",
  province: "ON",
  city: "Toronto",
  currency: "CAD",
  bn: "",
  status: "active",
  archived: false,
  ...over,
});
const detail = (id: string, name: string, over: Record<string, unknown> = {}) => ({
  ...summary(id, name, ["supplier"]),
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
  ...over,
});

async function mockList(page: Page) {
  await mockCsrf(page);
  await page.route("**/api/v1/o/acme/contacts?*", (r) => {
    const params = new URL(r.request().url()).searchParams;
    const all = [
      summary(C1, "Maple Leaf Supply Ltd.", ["supplier"], { email: "dana@mapleleaf.ca" }),
      summary(C2, "Birch Bakery Co.", ["customer"]),
    ];
    const role = params.get("role");
    const results = role ? all.filter((c) => c.roles.includes(role)) : all;
    return r.fulfill({
      json: {
        results,
        count: results.length,
        next_offset: null,
        role_counts: { customer: 1, supplier: 1, contractor: 0, government_agency: 0, employee: 0 },
      },
    });
  });
  await page.route("**/api/v1/o/acme/accounts?*", (r) =>
    r.fulfill({ json: { results: [], count: 0 } }),
  );
}

test("list: the title names the role's list, search and a saved view", async ({ page }) => {
  await mockList(page);
  await page.goto(`/o/${ORG}/contacts`);
  await expect(page.getByRole("heading", { name: "Contacts", level: 1 })).toBeVisible();
  await page.getByRole("tab", { name: /Suppliers/ }).click();
  await expect(page.getByRole("heading", { name: "Suppliers", level: 1 })).toBeVisible();
  const grid = page.getByRole("grid", { name: "Contacts" });
  await expect(grid.getByRole("link", { name: "Maple Leaf Supply Ltd." })).toBeVisible();
  await expect(grid.getByRole("link", { name: "Birch Bakery Co." })).toHaveCount(0);
  await page.getByRole("tab", { name: /Customers/ }).click();
  await expect(page.getByRole("heading", { name: "Customers", level: 1 })).toBeVisible();
  await page.getByRole("tab", { name: /All/ }).click();
  await page.getByRole("searchbox").fill("dana@");
  await expect(grid.getByRole("link", { name: "Birch Bakery Co." })).toHaveCount(0);
  await page.getByLabel("View name").fill("Dana's suppliers");
  await page.getByRole("button", { name: "Save view" }).click();
  await expect(page.getByRole("combobox", { name: "Saved views" })).toContainText(
    "Dana's suppliers",
  );
  await expectAccessible(page);
});

test("list: archive the selected contacts", async ({ page }) => {
  await mockList(page);
  await page.route(`**/api/v1/o/acme/contacts/${C2}/archive`, (r) =>
    r.fulfill({ json: detail(C2, "Birch Bakery Co.", { status: "archived" }) }),
  );
  await page.goto(`/o/${ORG}/contacts`);
  await page.getByRole("checkbox", { name: "Select Birch Bakery Co." }).click();
  await page.getByRole("button", { name: "Archive", exact: true }).click();
  await expect(page.getByText("1 contact archived.")).toBeVisible();
});

test("form: create with a person and an address; server errors land on their fields", async ({
  page,
}) => {
  await mockList(page);
  await page.route("**/api/v1/o/acme/contacts/duplicates?*", (r) =>
    r.fulfill({ json: { results: [] } }),
  );
  let attempts = 0;
  let sent: Record<string, unknown> = {};
  await page.route("**/api/v1/o/acme/contacts", async (r) => {
    attempts += 1;
    sent = r.request().postDataJSON() as Record<string, unknown>;
    if (attempts === 1) {
      await r.fulfill({
        status: 400,
        json: { "addresses[0].postal_code": ["Postal code should look like 'M5V 2T6'."] },
      });
    } else {
      await r.fulfill({ status: 201, json: detail(C1, "Maple Leaf Supply Ltd.") });
    }
  });
  await page.route(`**/api/v1/o/acme/contacts/${C1}`, (r) =>
    r.fulfill({ json: detail(C1, "Maple Leaf Supply Ltd.") }),
  );
  await page.goto(`/o/${ORG}/contacts/new`);
  await expect(page.getByRole("heading", { name: "New contact", level: 1 })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Sections" }).getByRole("link")).toHaveCount(5);
  await page.getByLabel("Name", { exact: true }).fill("Maple Leaf Supply Ltd.");
  await page.getByRole("checkbox", { name: "Supplier" }).click();
  await page.getByLabel("First name").fill("Dana");
  await page.getByLabel("Email").fill("dana@mapleleaf.ca");
  await page.getByLabel("Street address or PO box").first().fill("1 King St W");
  await page.getByLabel("Postal code").first().fill("M5V2T");
  await expectAccessible(page);
  await page.getByRole("button", { name: "Save contact" }).click();
  await expect(page.getByText("Postal code should look like 'M5V 2T6'.").first()).toBeVisible();
  expect(sent).toMatchObject({
    display_name: "Maple Leaf Supply Ltd.",
    roles: ["customer", "supplier"],
  });
  await page.getByLabel("Postal code").first().fill("M5V2T6");
  await page.getByRole("button", { name: "Save contact" }).click();
  await expect(page).toHaveURL(new RegExp(`/o/acme/contacts/${C1}$`));
});

test("merge dialog: choose fields, see what moves, merge", async ({ page }) => {
  await mockList(page);
  await page.route(`**/api/v1/o/acme/contacts/${C1}`, (r) =>
    r.fulfill({ json: detail(C1, "Maple Leaf Supply Ltd.") }),
  );
  await page.route("**/api/v1/o/acme/contacts/duplicates?*", (r) =>
    r.fulfill({
      json: {
        results: [
          {
            contact: summary(C2, "Maple Leaf Suply", ["supplier"]),
            reasons: ["name"],
            similarity: 0.82,
            exact: false,
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/o/acme/contacts/merge/preview?*", (r) =>
    r.fulfill({
      json: {
        survivor: detail(C1, "Maple Leaf Supply Ltd.", { legal_name: "Maple Leaf Supply" }),
        merged: detail(C2, "Maple Leaf Suply", { legal_name: "Maple Leaf Supply Limited" }),
        records: [
          { records: "people", count: 2, moves: true },
          { records: "journal lines", count: 4, moves: false },
        ],
      },
    }),
  );
  let body: Record<string, unknown> = {};
  await page.route("**/api/v1/o/acme/contacts/merge", async (r) => {
    body = r.request().postDataJSON() as Record<string, unknown>;
    await r.fulfill({
      json: {
        survivor: detail(C1, "Maple Leaf Supply Ltd.", { legal_name: "Maple Leaf Supply Limited" }),
      },
    });
  });
  await page.goto(`/o/${ORG}/contacts/${C1}`);
  await page.getByRole("button", { name: /Merge/ }).first().click();
  const dialog = page.getByRole("dialog", {
    name: "Merge Maple Leaf Suply into Maple Leaf Supply Ltd.",
  });
  await expect(
    dialog.getByText("2 records of people move to Maple Leaf Supply Ltd."),
  ).toBeVisible();
  await expect(dialog.getByText(/4 records of journal lines stay on the alias/)).toBeVisible();
  await dialog
    .getByRole("radiogroup", { name: "Keep for Legal name" })
    .getByRole("radio", { name: "Maple Leaf Supply Limited" })
    .click();
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Merge contacts" }).click();
  await expect(
    page.getByText("Maple Leaf Suply was merged into Maple Leaf Supply Ltd."),
  ).toBeVisible();
  expect(body).toMatchObject({ survivor: C1, merged: C2, field_sources: { legal_name: "merged" } });
});
