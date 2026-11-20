import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * C-03-T13 / T14 — manual journal controls. The teardown scenario (REFINED): Petty Cash at zero,
 * a 994.17 journal crediting it. Someone who isn't an adviser sees the chip on the Petty Cash line
 * ("Petty Cash would be −994.17 on 15 Jun 2026"), the block message, and Post disabled; an adviser
 * posts through a dialog that needs a reason of at least 10 characters (sent with the journal).
 */
const ORG = "acme";
const PETTY = "10101010-0000-4000-8000-000000000001";
const OFFICE = "61006100-0000-4000-8000-000000000002";
const JOURNAL = "99999999-0000-4000-8000-000000000009";

const account = (id: string, code: string, name: string, type: string, subtype: string) => ({
  id,
  code,
  name,
  description: "",
  type,
  type_label: type,
  subtype,
  subtype_label: subtype,
  parent: null,
  depth: 0,
  has_children: false,
  system_role: "",
  system_role_label: "",
  is_bank: subtype === "bank",
  gifi: null,
  require_contact: false,
  require_tracking: false,
  require_attachment: false,
  default_tax_key: "",
  status: "active",
  archived_at: null,
  balance: { accounting: "0.00", tax: "0.00" },
});

const SHORTFALL = {
  account: { id: PETTY, label: "1010 · Petty Cash" },
  change: "-994.17",
  at_date: "-994.17",
  date: "2026-06-15",
  at_today: "-994.17",
  today: "2026-06-20",
  lowest: "-994.17",
  lowest_on: "2026-06-15",
  message: "Petty Cash would be −994.17 on 15 Jun 2026",
};

async function mockJournalApi(
  page: Page,
  check: Record<string, unknown>,
): Promise<Record<string, unknown>[]> {
  const posted: Record<string, unknown>[] = [];
  await page.route(`**/api/v1/o/${ORG}/accounts?*`, (route) =>
    route.fulfill({
      json: {
        count: 2,
        results: [
          account(PETTY, "1010", "Petty Cash", "asset", "bank"),
          account(OFFICE, "6100", "Office supplies", "expense", "operating_expense"),
        ],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/journals/check`, (route) =>
    route.fulfill({
      json: {
        ok: false,
        errors: [],
        shortfalls: [SHORTFALL],
        adviser: false,
        needs: { attachment: false, contact_lines: [] },
        ...check,
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

async function fillTeardownJournal(page: Page) {
  await page.goto(`/o/${ORG}/accounting/journals/new`);
  await page.getByLabel("Account, line 1").selectOption(OFFICE);
  await page.getByLabel("Debit, line 1").fill("994.17");
  await page.getByLabel("Account, line 2").selectOption(PETTY);
  await page.getByLabel("Credit, line 2").fill("994.17");
}

test.use({ viewport: { width: 1440, height: 900 } });

test("non-adviser: chip on the bank line, block message, Post disabled", async ({ page }) => {
  await mockCsrf(page);
  const posted = await mockJournalApi(page, { adviser: false });
  await fillTeardownJournal(page);
  const pettyLine = page.locator("tr[data-line='2']");
  await expect(pettyLine.locator("[data-chip='negative-cash']")).toHaveText(
    "Petty Cash would be −994.17 on 15 Jun 2026",
  );
  await expect(page.locator("[data-blocked]")).toContainText(
    "A journal can't take a bank or cash account below zero",
  );
  await expect(page.getByRole("button", { name: "Post journal" })).toBeDisabled();
  await expectAccessible(page);
  expect(posted).toEqual([]);
});

test("adviser: the override dialog needs a reason, sent with the journal", async ({ page }) => {
  await mockCsrf(page);
  const posted = await mockJournalApi(page, { adviser: true });
  await fillTeardownJournal(page);
  await expect(page.locator("[data-chip='negative-cash']")).toBeVisible();
  await page.getByRole("button", { name: "Post journal" }).click();
  const dialog = page.getByRole("dialog", { name: "Post below zero?" });
  await expect(dialog).toContainText("Petty Cash would be −994.17 on 15 Jun 2026");
  const confirm = dialog.getByRole("button", { name: "Post with this reason" });
  const reason = dialog.getByLabel("Reason (at least 10 characters)");
  await reason.fill("too short");
  await expect(confirm).toBeDisabled();
  await reason.fill("Owner reimbursed the float on Monday.");
  await expect(confirm).toBeEnabled();
  await expectAccessible(page);
  await confirm.click();
  await expect(page).toHaveURL(`/o/${ORG}/accounting/journals/${JOURNAL}`);
  expect(posted).toHaveLength(1);
  expect(posted[0]).toMatchObject({
    post: true,
    override_reason: "Owner reimbursed the float on Monday.",
    lines: [
      { account: OFFICE, debit: "994.17" },
      { account: PETTY, credit: "994.17" },
    ],
  });
});
