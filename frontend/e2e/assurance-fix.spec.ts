import { expect, test, type Page } from "@playwright/test";

import { TEARDOWN_FINDINGS, TEARDOWN_SUMMARY } from "../src/accounting/assurance/fixtures";
import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * K-09-T22 — proposed-fix drawer: the reasoning and the proposed entry as an editable draft
 * journal grid (account, debit, credit, description; totals and the out-of-balance message;
 * Create draft journal disabled until it balances). The edited lines are sent, and the draft
 * created from the drawer appears in the journals Draft tab. Server side:
 * backend/tests/test_assurance_fixes.py, test_assurance_api.py.
 */
const ORG = "refined";
const API = `**/api/v1/o/${ORG}`;
const DRAFT_ID = "d0d0d0d0-0000-4000-8000-000000000001";
const PETTY = "10001000-0000-4000-8000-000000000001";
const LOAN = "29002900-0000-4000-8000-000000000002";
const CHEQUING = "10101010-0000-4000-8000-000000000003";

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

const line = (id: string, label: string, debit: string, credit: string) => ({
  account: id,
  code: label.slice(0, 4),
  label,
  debit,
  credit,
  description: "",
});

const FIX = {
  kind: "journal",
  reasoning:
    "Petty Cash fell to −994.17 on 15 Jun 2026 and no other bank account can cover it: the owner most likely paid personally, so the entry credits Shareholder Loan.",
  date: "2026-06-03",
  narration: "Owner funded Petty Cash",
  lines: [
    line(PETTY, "1000 · Petty Cash", "994.17", "0.00"),
    line(LOAN, "2900 · Shareholder Loan", "0.00", "994.17"),
  ],
  recode: null,
  alternatives: [
    {
      kind: "journal",
      reasoning: "Transfer from Chequing, which has enough money.",
      date: "2026-06-03",
      narration: "Transfer to Petty Cash",
      lines: [
        line(PETTY, "1000 · Petty Cash", "994.17", "0.00"),
        line(CHEQUING, "1010 · Chequing", "0.00", "994.17"),
      ],
      recode: null,
      alternatives: [],
    },
  ],
};

async function mockApi(page: Page) {
  const sent: Record<string, unknown>[] = [];
  const drafts: Record<string, unknown>[] = [];
  const journalQueries: string[] = [];
  await mockCsrf(page);
  await page.route(`${API}/assurance/`, (r) => r.fulfill({ json: TEARDOWN_SUMMARY }));
  await page.route(`${API}/assurance/findings*`, (r) =>
    r.fulfill({ json: { count: TEARDOWN_FINDINGS.length, findings: TEARDOWN_FINDINGS } }),
  );
  await page.route(`${API}/assurance/findings/neg-cash/fix`, (r) => {
    if (r.request().method() !== "POST") return r.fulfill({ json: { fix: FIX } });
    const body = jsonBody(r);
    sent.push(body);
    drafts.push({
      id: DRAFT_ID,
      number: "",
      date: body.date,
      type: "manual",
      journal_type: "adjusting",
      journal_type_label: "Adjusting",
      status: "draft",
      narration: body.narration,
      total: "994.17",
      lines: 2,
      source: null,
      book_scope: "both",
      auto_reverse_on: null,
      reversal_of: null,
      reversed_by: null,
    });
    return r.fulfill({
      status: 201,
      json: {
        draft: { id: DRAFT_ID, status: "draft" },
        finding: { ...TEARDOWN_FINDINGS[0], fix_entry: DRAFT_ID },
      },
    });
  });
  await page.route(`${API}/accounts?*`, (r) =>
    r.fulfill({
      json: {
        count: 3,
        results: [
          account(PETTY, "1000", "Petty Cash", "asset", "bank"),
          account(CHEQUING, "1010", "Chequing", "asset", "bank"),
          account(LOAN, "2900", "Shareholder Loan", "liability", "current_liability"),
        ],
      },
    }),
  );
  await page.route(`${API}/journals?*`, (r) => {
    const status = new URL(r.request().url()).searchParams.get("status") ?? "";
    journalQueries.push(status);
    const rows = status.split(",").includes("draft") ? drafts : [];
    return r.fulfill({ json: { results: rows, count: rows.length, next_offset: null } });
  });
  return { sent, journalQueries };
}

test.use({ viewport: { width: 1440, height: 900 } });

test("the drawer's edited draft appears in the journals Draft tab", async ({ page }) => {
  const { sent, journalQueries } = await mockApi(page);
  await page.goto(`/o/${ORG}/accounting/assurance`);
  await page
    .locator('[data-rule-group="NEG_CASH"]')
    .getByRole("button", { name: "Propose fix" })
    .click();

  const drawer = page.getByRole("dialog", { name: "Proposed fix" });
  await expect(drawer.locator("[data-fix-reasoning]")).toContainText("credits Shareholder Loan");
  await expect(drawer.locator("[data-fix-lines] tbody tr")).toHaveCount(2);
  await expect(drawer.getByRole("combobox", { name: "Account, line 2" })).toHaveValue(
    /Shareholder Loan/,
  );
  await expect(drawer.getByLabel("Narration")).toHaveValue("Owner funded Petty Cash");
  const create = drawer.getByRole("button", { name: "Create draft journal" });
  await expect(create).toBeEnabled();
  await expectAccessible(page);

  // Editing a side unbalances the entry: Create waits until it balances again.
  await drawer.getByLabel("Credit, line 2").fill("900.00");
  await expect(drawer.locator("[data-fix-totals]")).toContainText("Out of balance by $94.17");
  await expect(create).toBeDisabled();
  await drawer.getByLabel("Credit, line 2").fill("994.17");
  await expect(drawer.locator("[data-fix-totals]")).toContainText("Balanced");
  await drawer.getByLabel("Description, line 1").fill("Receipts in the petty cash box");
  await drawer.getByLabel("Narration").fill("Owner funded Petty Cash (June)");
  await create.click();

  await expect(drawer.getByRole("status")).toContainText("Draft journal created");
  expect(sent).toEqual([
    {
      date: "2026-06-03",
      narration: "Owner funded Petty Cash (June)",
      lines: [
        {
          account: PETTY,
          debit: "994.17",
          credit: "0",
          description: "Receipts in the petty cash box",
        },
        { account: LOAN, debit: "0", credit: "994.17", description: "" },
      ],
    },
  ]);
  await expect(drawer.getByRole("link", { name: "Open the draft" })).toHaveAttribute(
    "href",
    `/o/${ORG}/accounting/journals/${DRAFT_ID}`,
  );

  await drawer.getByRole("link", { name: "See it in Journals › Draft" }).click();
  await expect(page).toHaveURL(new RegExp(`/o/${ORG}/accounting/journals\\?tab=draft$`));
  await expect(page.getByRole("tab", { name: "Draft" })).toHaveAttribute("aria-selected", "true");
  const row = page.locator(`[data-journal-row="${DRAFT_ID}"]`);
  await expect(row).toContainText("Owner funded Petty Cash (June)");
  await expect(row).toContainText("Draft");
  await expect(row).toContainText("$994.17");
  expect(journalQueries).toContain("draft");
  await expectAccessible(page);
});

test("another option loads into the grid", async ({ page }) => {
  const { sent } = await mockApi(page);
  await page.goto(`/o/${ORG}/accounting/assurance`);
  await page
    .locator('[data-rule-group="NEG_CASH"]')
    .getByRole("button", { name: "Propose fix" })
    .click();
  const drawer = page.getByRole("dialog", { name: "Proposed fix" });
  await drawer.getByRole("button", { name: "Use this option" }).click();
  await expect(drawer.getByRole("combobox", { name: "Account, line 2" })).toHaveValue(/Chequing/);
  await expect(drawer.getByLabel("Narration")).toHaveValue("Transfer to Petty Cash");
  await drawer.getByRole("button", { name: "Create draft journal" }).click();
  await expect(drawer.getByRole("status")).toContainText("Draft journal created");
  expect((sent[0]?.lines as { account: string }[]).map((l) => l.account)).toEqual([
    PETTY,
    CHEQUING,
  ]);
});
