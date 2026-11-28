import { expect, test, type Page } from "@playwright/test";

import { TEARDOWN_FINDINGS, TEARDOWN_SUMMARY } from "../src/accounting/assurance/fixtures";
import { mockCsrf } from "./auth-helpers";

/**
 * gap-36 · gap-53 · gap-59 (K-09-T25), the browser half: on the teardown organisation (REFINED)
 * the Assurance page shows a finding group for every teardown issue — negative petty cash,
 * journal-only expenses (to cash, no contact, no attachment), all-exempt lines, no BN, no lock
 * date, 0 GIFI, the backdated journal, the dormant admin, no opening balances — the Accounting
 * item carries the open critical + warning count, the negative cash comes with its correcting
 * entry (Dr 1000 Petty Cash / Cr 2900 Shareholder Loan 994.17) and the Activity tab shows the
 * dormant owner. The API is mocked with what the engine returns for the fixture; the engine
 * itself is backend/tests/test_assurance_teardown.py (same gap markers).
 */
const ORG = "refined";
const API = `**/api/v1/o/${ORG}`;
const TEARDOWN_RULES = [
  "NEG_CASH",
  "JOURNAL_TO_CASH",
  "EXPENSE_JOURNAL_NO_CONTACT",
  "EXPENSE_JOURNAL_NO_ATTACHMENT",
  "EXEMPT_ON_TAXABLE_ACCOUNT",
  "MISSING_BN",
  "MISSING_LOCK_DATE",
  "UNMAPPED_GIFI",
  "BACKDATED",
  "DORMANT_USER_WITH_ADMIN",
  "UNBALANCED_CONVERSION",
];

async function mockApi(page: Page) {
  await mockCsrf(page);
  await page.route(`${API}/assurance/`, (r) => r.fulfill({ json: TEARDOWN_SUMMARY }));
  await page.route(`${API}/assurance/findings*`, (r) =>
    r.fulfill({ json: { count: TEARDOWN_FINDINGS.length, findings: TEARDOWN_FINDINGS } }),
  );
  await page.route(`${API}/assurance/findings/neg-cash/fix`, (r) =>
    r.fulfill({
      json: {
        fix: {
          kind: "journal",
          reasoning:
            "Petty Cash is −994.17 and no other bank account has the money: the owner most likely paid personally, so the entry credits Shareholder Loan.",
          date: "2026-06-03",
          narration: "Owner funded Petty Cash",
          lines: [
            {
              account: "acc-1000",
              code: "1000",
              label: "1000 · Petty Cash",
              debit: "994.17",
              credit: "0.00",
              description: "",
            },
            {
              account: "acc-2900",
              code: "2900",
              label: "2900 · Shareholder Loan",
              debit: "0.00",
              credit: "994.17",
              description: "",
            },
          ],
          recode: null,
          alternatives: [],
        },
      },
    }),
  );
  await page.route(`${API}/assurance/heatmap*`, (r) =>
    r.fulfill({
      json: {
        from: "2025-11-27",
        to: "2026-11-26",
        time_zone: "America/Toronto",
        total: 4,
        days: [{ date: "2026-07-26", count: 4 }],
        people: [{ id: "u-dana", name: "Dana Lee", count: 4, last: "2026-07-26T10:00:00-04:00" }],
      },
    }),
  );
}

test.use({ viewport: { width: 1440, height: 900 } });

test("gap-59 gap-36: every teardown issue is a finding group, counted on the nav", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto(`/o/${ORG}/accounting/assurance`);
  for (const rule of TEARDOWN_RULES) {
    await expect(page.locator(`[data-rule-group="${rule}"]`), rule).toBeVisible();
  }
  await expect(page.locator('[data-rule-group="NEG_CASH"]')).toContainText("−994.17");
  await expect(page.locator('[data-rule-group="JOURNAL_TO_CASH"] [data-finding]')).toHaveCount(2);
  const nav = page.getByRole("navigation", { name: "Main" });
  const attention = TEARDOWN_SUMMARY.open.critical + TEARDOWN_SUMMARY.open.warning;
  const accounting = nav.getByRole("link", {
    name: new RegExp(`Accounting.*${attention} assurance findings need attention`),
  });
  await expect(accounting.locator("[data-nav-badge]")).toHaveAttribute(
    "data-nav-badge",
    String(attention),
  );
});

test("gap-53: the negative cash comes with its correcting draft journal", async ({ page }) => {
  await mockApi(page);
  await page.goto(`/o/${ORG}/accounting/assurance`);
  await page
    .locator('[data-rule-group="NEG_CASH"]')
    .getByRole("button", { name: "Propose fix" })
    .click();
  const drawer = page.getByRole("dialog", { name: "Proposed fix" });
  await expect(drawer.locator("[data-fix-reasoning]")).toContainText("credits Shareholder Loan");
  await expect(drawer.getByLabel("Debit, line 1")).toHaveValue("994.17");
  await expect(drawer.getByLabel("Credit, line 2")).toHaveValue("994.17");
  await expect(drawer.locator("[data-fix-totals]")).toContainText("Balanced");
  await expect(drawer).toContainText("nothing is posted until you post it yourself");
});

test("gap-59: the dormant administrator stands out on the Activity tab", async ({ page }) => {
  await mockApi(page);
  await page.goto(`/o/${ORG}/accounting/assurance?tab=activity`);
  await expect(page.getByRole("img", { name: /4 actions from/ })).toBeVisible();
  const people = page.locator("[data-heatmap-people]");
  await expect(people.locator('[data-person="u-dana"]')).toContainText("Dana Lee");
  await expect(people.locator('[data-person="u-dana"]')).toContainText("Jul");
});
