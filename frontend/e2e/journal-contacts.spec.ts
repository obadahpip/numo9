import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * C-03-T12 — contact column on journal lines: hidden by default; choosing an account that
 * requires a contact (Accounts receivable) reveals the column and focuses that line's contact
 * cell; the contact chosen is posted with the line.
 */
const ORG = "acme";
const AR = "11001100-0000-4000-8000-000000000001";
const SALES = "40004000-0000-4000-8000-000000000002";
const CUSTOMER = "c0c0c0c0-0000-4000-8000-000000000003";
const JOURNAL = "99999999-0000-4000-8000-00000000000c";

const account = (
  id: string,
  code: string,
  name: string,
  type: string,
  requireContact: boolean,
) => ({
  id,
  code,
  name,
  description: "",
  type,
  type_label: type,
  subtype: "",
  subtype_label: "",
  parent: null,
  depth: 0,
  has_children: false,
  system_role: "",
  system_role_label: "",
  is_bank: false,
  gifi: null,
  require_contact: requireContact,
  require_tracking: false,
  require_attachment: false,
  default_tax_key: "",
  status: "active",
  archived_at: null,
  balance: { accounting: "0.00", tax: "0.00" },
});

async function mockApi(page: Page): Promise<Record<string, unknown>[]> {
  const posted: Record<string, unknown>[] = [];
  await page.route(`**/api/v1/o/${ORG}/accounts?*`, (route) =>
    route.fulfill({
      json: {
        count: 2,
        results: [
          account(AR, "1100", "Accounts receivable", "asset", true),
          account(SALES, "4000", "Sales", "revenue", false),
        ],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/contacts?*`, (route) =>
    route.fulfill({
      json: {
        count: 1,
        next_offset: null,
        role_counts: { customer: 1, supplier: 0 },
        results: [{ id: CUSTOMER, display_name: "Maple Leaf Ltd", roles: ["customer"] }],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/journals/check`, (route) =>
    route.fulfill({
      json: {
        ok: true,
        errors: [],
        shortfalls: [],
        adviser: false,
        needs: { attachment: false, contact_lines: [] },
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/journals`, (route) => {
    posted.push(route.request().postDataJSON() as Record<string, unknown>);
    return route.fulfill({ status: 201, json: { id: JOURNAL, status: "posted" } });
  });
  await page.route(`**/api/v1/o/${ORG}/journals/${JOURNAL}`, (route) =>
    route.fulfill({ status: 404, json: {} }),
  );
  return posted;
}

test.use({ viewport: { width: 1440, height: 900 } });

test("a require-contact account reveals and focuses the contact cell", async ({ page }) => {
  await mockCsrf(page);
  const posted = await mockApi(page);
  await page.goto(`/o/${ORG}/accounting/journals/new`);
  await expect(page.getByRole("columnheader", { name: "Contact" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Show contact column" })).toBeVisible();

  await page.getByLabel("Account, line 1").selectOption(AR);
  const contact = page.getByLabel("Contact, line 1");
  await expect(page.getByRole("columnheader", { name: "Contact" })).toBeVisible();
  await expect(contact).toBeFocused();
  await expect(contact).toHaveAttribute("aria-required", "true");
  await expect(page.locator("tr[data-line='1'] [data-contact-required]")).toHaveText(
    "This account needs a contact.",
  );
  await expect(page.getByRole("button", { name: "Hide contact column" })).toBeDisabled();
  await expectAccessible(page);

  await contact.selectOption(CUSTOMER);
  await page.getByLabel("Debit, line 1").fill("113.00");
  await page.getByLabel("Account, line 2").selectOption(SALES);
  await page.getByLabel("Credit, line 2").fill("113.00");
  await expect(page.locator("[data-contact-required]")).toHaveCount(0);
  await page.getByRole("button", { name: "Post journal" }).click();
  await expect(page).toHaveURL(`/o/${ORG}/accounting/journals/${JOURNAL}`);
  expect(posted[0]).toMatchObject({
    lines: [
      { account: AR, debit: "113.00", contact: CUSTOMER },
      { account: SALES, credit: "113.00", contact: null },
    ],
  });
});
