import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { pickAccount } from "./journal-helpers";

/**
 * C-04-T09 — journal editor grid: account autocomplete, the difference meter ("Out of balance by
 * $12.50"), Post disabled until $0.00, Tab past the last cell adds a line.
 */
const ORG = "acme";
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
  depth: 1,
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

test.use({ viewport: { width: 1440, height: 900 } });

test("difference meter, Post disabled until balanced, Tab adds a line", async ({ page }) => {
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/accounts?*`, (route) =>
    route.fulfill({
      json: {
        count: 2,
        results: [
          account(
            "54005400-0000-4000-8000-000000000001",
            "5400",
            "Rent",
            "expense",
            "operating_expense",
          ),
          account("10001000-0000-4000-8000-000000000002", "1000", "Chequing", "asset", "bank"),
        ],
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
  await page.goto(`/o/${ORG}/accounting/journals/new`);
  const post = page.getByRole("button", { name: "Post journal" });
  const meter = page.locator("[data-difference]");
  await expect(meter).toHaveText("Enter the debits and credits");
  await expect(post).toBeDisabled();

  await pickAccount(page, 1, "5400", /Rent/);
  await page.getByLabel("Debit, line 1").fill("1250.00");
  await pickAccount(page, 2, "cheq", /Chequing/);
  await page.getByLabel("Credit, line 2").fill("1237.50");
  await expect(meter).toHaveText("Out of balance by $12.50");
  await expect(post).toBeDisabled();
  await page.getByLabel("Credit, line 2").fill("1250.00");
  await expect(meter).toHaveText("Balanced");
  await expect(post).toBeEnabled();

  await page.getByLabel("Description, line 2").focus();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("combobox", { name: "Account, line 3" })).toBeFocused();
  await expectAccessible(page);
});
